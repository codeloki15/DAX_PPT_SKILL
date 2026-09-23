# Live preview and browser editing

How the user edits slides in a browser while you work on the same files, and what that obliges you to do.

## The concurrency rule — read this first

Once the preview is served, `slide_NNN.html` files are **shared mutable state**. The browser tab holds a DOM snapshot taken at page load and writes the whole `<body>` back on autosave. There is no ETag, no `If-Match`, no mtime check, no lock — `save_slide_body()` is a plain truncate-and-write (`edit_server.py:141`).

Consequences, in order of how often they bite:

1. **Re-read a slide immediately before editing it.** If you rewrite `slide_003.html` from a stale copy, you clobber the user's browser edits. If the user's tab autosaves after you wrote, their stale DOM clobbers *you*.
2. **If the user says they fixed something in the browser, believe them.** Re-read the file. Do not regenerate the slide from your own earlier draft — that discards their work silently.
3. **Prefer surgical edits** (targeted `Edit` on the changed element) over rewriting a whole slide file.
4. **Structural ops are safer than they look:** reorder / duplicate / insert / paste each take a `.history` snapshot server-side and force a full `location.reload()` in the browser, so the tab re-syncs from disk. Text and chart edits do neither.
5. After you write a slide the user has open, tell them to reload the tab. Nothing pushes your change to their page.

The `dax.py open` JSON says this too:

```json
"note": "The edit server is running. Slide files are now SHARED STATE: re-read a slide before editing it. This process must stay alive to keep serving the preview."
```

## 1. Build then serve

Two separate steps. `preview` writes a file; `open` serves it.

| Command | Does |
|---|---|
| `dax.py --workspace WS preview --title "Q3 Review"` | Stitches every `slide_NNN.html` into `WS/slides/live_preview.html`, inlines local images as base64, injects chart specs + `chart_renderer.js` + `native_export.js` + `editor.js`, and saves the title to `WS/slides/deck_meta.json`. Returns `{"status":"created","path":...,"total_slides":N}`. |
| `dax.py --workspace WS open [--serve] [--no-browser]` | Starts the edit server on `127.0.0.1:<ephemeral>`, opens Chrome (or the default browser) at the URL, then **blocks forever** serving. |

```bash
dax.py --workspace WS preview --title "Q3 Review"
dax.py --workspace WS open --serve
```

**`open` blocks.** `cmd_open` (dax.py:156-164) loops `time.sleep(3600)` until Ctrl+C when the server came up and either `--serve` or a browser launch happened. The HTTP server thread is a **daemon thread** — it dies the instant the process exits. So:

```bash
# run it in the background, keep the handle
dax.py --workspace WS open --serve &
```

Or launch it with a background-capable tool. Do not run it in the foreground and then wait on it — you will never get your turn back.

`preview --slides N` limits the build to slides numbered `<= N`. With no slides at all, `preview` errors: `No slides found in <dir>. Write slide_001.html first.` `open` errors if `live_preview.html` is missing: `Preview not found: <path>. Run 'dax.py preview' first.`

**You rarely need to re-run `preview`.** `GET /` regenerates the page from the current slide files on every hit (`_serve_preview`, edit_server.py:513), reading the title back from `deck_meta.json`. A browser reload picks up whatever is on disk. Re-run `preview` only to change the title or after a `reset`. Export, however, reads the *stored* `live_preview.html` over `file://` — so **always re-run `preview` before `export`**.

## 2. What the user can do in the browser

| Feature | How | Persists to |
|---|---|---|
| Text editing | Click **Edit Text** in the toolbar → every text leaf in **every** slide becomes `contenteditable`. Click and type. | `POST /api/slide/<n>` → the slide file's `<body>` |
| Save | `Ctrl/Cmd+S` (immediate), or **2500 ms** debounced autosave after the last keystroke | same |
| Formatting toolbar | Floating bar on text selection: bold / italic / underline, A−/A+ font size, 5 brand swatches (`#12263F` navy, `#00A0DC` brand blue, `#1F7A5C` positive, `#B3341F` negative, `#3C4456` body), align left/center/right, clear formatting | inline styles in the saved body |
| Undo / redo | `Ctrl/Cmd+Z` / `Ctrl/Cmd+Shift+Z` or `Ctrl/Cmd+Y`. **In-memory only**, `MAX_UNDO = 60`, lost on reload — and every structural op reloads. | nothing |
| Chart data editing | **Edit data** button on any `.chart-embed` → spreadsheet grid: one row per category, one column per series, editable series names, plus a chart-type `<select>`. Save → reload. | `POST /api/chart/<id>` → `WS/charts/<id>.json` |
| New slide | `Ctrl/Cmd+M` or **New** → layout gallery (6 layouts, below) | `POST /api/deck/insert` → a new `slide_NNN.html` |
| Copy / cut / paste slide | `Ctrl/Cmd+C` / `Ctrl/Cmd+X` / `Ctrl/Cmd+V` (only when no text is selected and focus is not in a text field) | `POST /api/deck/paste`, clipboard held in `sessionStorage['pptmk-clipboard']` |
| Duplicate | `Ctrl/Cmd+D` or **Duplicate** | `POST /api/deck/duplicate` |
| Reorder | Drag thumbnails in the left rail, or Move up / Move down | `POST /api/deck/reorder` → files renamed `slide_001..N` |
| Delete | **Delete slide** — implemented as "reorder to the surviving set"; anything absent from `order` is `os.remove`d | `POST /api/deck/reorder` |
| Right-click menu | On a slide card or thumbnail: New slide, Duplicate, Cut, Copy, Paste, Move up, Move down, Edit speaker notes, Present from here, Delete slide | as above |
| Version history | **History** button → snapshot list, newest first, each with a **Restore** | `WS/slides/.history/` |
| Speaker notes | Collapsible **Speaker notes** box under each slide card. **900 ms** debounce. | `POST /api/slide/<n>/notes` → `<!-- SPEAKER_NOTES ... -->` in the slide file |

Chart-grid caveats: the grid **cannot add or remove rows or series** — it maps over the existing spec shape. A blank or non-numeric cell becomes `0` (`parseFloat(cell.value) || 0`). The save re-runs the full `create_chart()` validator, so a mismatched count or a pie with two series comes back as a 400 with the validator's own error text.

Post-save, the browser fires `POST /api/verify/<n>` per saved slide and paints an **"Overflows 720px"** badge on the card header when overflow is detected. It is advisory and silently absent if Playwright is not installed.

## 3. Edits land in the same files you wrote

`bodyHtmlOf(card)` clones `.slide-content`, strips the preview-only `<style>`, removes every `contenteditable` attribute, drops rendered `<canvas>` from chart embeds and removes `[data-editor-ui]` nodes, then POSTs `clone.innerHTML.trim()` as `body_html`.

Server side, `save_slide_body(n, body_html)`:

```python
BODY_RE = re.compile(r"(<body[^>]*>)(.*)(</body>)", re.DOTALL | re.IGNORECASE)
```

- `<head>`, the slide's own `<style>` block and the design system **survive** — only the region between the body tags is replaced.
- The existing `<!-- SPEAKER_NOTES ... -->` block is captured and re-appended if the incoming body does not already carry one.
- No `<body>` in the file → `{"error": "Slide N has no <body> element to update"}` (HTTP 400).
- Missing file → `{"error": "Slide N not found"}`.

So: no separate "browser edits" store. The user's changes are in `WS/slides/slide_NNN.html`, which is exactly the file you `Read` and `Edit`.

Chart edits are the one exception: the slide HTML holds only `<div class="chart-embed" data-chart-id="...">`. The spec JSON at `WS/charts/<id>.json` is the single source of truth, and it drives both the preview render and the native PPTX chart.

## 4. http:// vs file:// — why serving matters

One flag decides everything, set purely from the URL scheme:

```js
window.__editorHasServer = (location.protocol === 'http:' || location.protocol === 'https:');
```

Opened as `file://`, the page degrades to read-only and says so:

| Over `http://127.0.0.1` | Over `file://` |
|---|---|
| Status pill: *All changes saved* | Status pill: **Read-only (no edit server)**, warn tone |
| Autosave + `Ctrl/Cmd+S` write to disk | `saveAll()` toasts *"Opened without the edit server - changes cannot be saved"* and returns false |
| Chart editor opens | Toast: *"Chart editing needs the edit server"* |
| Copy / paste / new slide / history work | Toasts: *"Copying slides needs the edit server"*, *"Pasting slides needs the edit server"*, *"Adding slides needs the edit server"*, *"History needs the edit server"* |
| Notes → slide file | Notes → `localStorage` only |
| — | `body.no-edit-server` dims the Save and New buttons |

Text editing, the format bar and in-memory undo still *work* over `file://` — they just never reach disk. That is the trap: it looks editable.

`dax.py open` handles the choice for you. `open_preview()` calls `start_edit_server()`; if the bind fails it falls back to `file://<abspath>` and the JSON reports:

```json
{
  "status": "opened",
  "url": "file:///.../slides/live_preview.html",
  "editable": false,
  "warning": "Edit server unavailable (<reason>); the preview is read-only and edits will not persist."
}
```

**`"editable": false` means the user's browser edits will be lost.** Do not tell them to go edit in the browser. Surface the `warning`, fix the cause (usually a port bind failure or a stale process), and re-run `open`. When `editable` is false, `cmd_open` exits immediately instead of blocking.

## 5. Security posture

- Bound to `127.0.0.1` only: `ThreadingHTTPServer(("127.0.0.1", port), EditRequestHandler)`.
- Every `/api/*` route (all GETs and all POSTs) is gated by `_guard_local()`, which rejects any `client_address[0]` outside `("127.0.0.1", "::1")` with `403 {"error": "forbidden"}`.
- Request bodies capped at `MAX_BODY_BYTES = 12 MB` (slides carry base64 images).
- Responses carry `Cache-Control: no-store`. No CORS headers, no `PUT`, no `DELETE`.
- Port defaults to `0` — an OS-assigned ephemeral port, printed in the `url` field.
- Non-API GETs fall through to static file serving rooted at `WS/slides/`, which includes `.history/`. This is a local editing tool. **Do not expose it to a network or a tunnel.**

## 6. Version history (durable undo)

```
WS/slides/.history/<YYYYmmdd-HHMMSS-mmm>/
    slide_001.html
    slide_002.html
    label.txt
```

**When snapshots are taken** — only before structural POSTs, with these exact labels:

| Operation | Label |
|---|---|
| `/api/deck/reorder` (incl. delete, move up/down) | the request's `label`, else `"before reorder"` |
| `/api/deck/duplicate` | `"before duplicate"` |
| `/api/deck/insert` | `"before add slide"` |
| `/api/deck/paste` | `"before paste"` |
| `/api/history/restore` | `"before restore"` |

**Text edits and chart edits take NO snapshot.** Version history covers deck structure, not content. In-memory undo (`MAX_UNDO = 60`) is the only recovery for typed text, and it dies on reload.

**Restore:** validates the id against `re.fullmatch(r"[0-9\-]{1,32}", snapshot_id)`, snapshots the current deck first, deletes every live `slide_NNN.html`, then copies the snapshot's slides back. Returns `{"status":"restored","snapshot":id,"slides":N}`. The browser confirms first: *"Restore this version? The current deck is snapshotted first."*

**Retention:** `MAX_SNAPSHOTS = 40`. Older directories are `rmtree`d on each new snapshot. `snapshot_deck` returns `{"status":"skipped","reason":"no slides"}` on an empty deck.

`.history/` lives inside `WS/slides/`. `dax.py reset --yes` deletes it along with everything else.

## 7. The 6 blank layouts

From `BLANK_LAYOUTS` / `LAYOUT_LABELS`, served by `GET /api/layouts` in this fixed order:

| id | Gallery label | Contents |
|---|---|---|
| `title_slide` | Title slide | Centred kicker "DATA AXLE", 42px action, rule, subtitle lead |
| `title_content` | Title and content | Kicker, action, rule, `.body` with a `p.lead`, footer |
| `two_content` | Two content panels | Two flexed `.exh` panels, each with an `.exh-t` header and a `ul.c` |
| `table` | Comparison table | One `.exh` with a 3-column `thead`/`tbody` table |
| `section_break` | Section header | Centred kicker + 38px action + rule, footer |
| `blank` | Blank | `.slide-container` with an empty `.body` |

An unknown id returns `{"error": "unknown layout '<x>'. Valid: [...]"}`.

`insert_slide` **reuses the `<head>` of slide 1** (`slide_path(nums[0])`) so the new slide inherits the design system CSS. Inserting into an empty deck produces a head-less, unstyled slide — write `slide_001.html` yourself first.

## 8. After the user edits — agent checklist

```bash
# 1. See what exists now (order and numbering may have changed)
dax.py --workspace WS list

# 2. Re-read every slide you intend to touch, from disk
#    (Read WS/slides/slide_003.html — do not reuse your earlier draft)

# 3. Re-verify anything they changed; hand-typed text overflows
dax.py --workspace WS verify --slide 3

# 4. Notes may have changed too
dax.py --workspace WS notes --slide 3

# 5. Rebuild the preview ONLY to change the title, or before export
dax.py --workspace WS preview --title "Q3 Review"

# 6. Export reads the stored live_preview.html — step 5 is mandatory first
dax.py --workspace WS export --title "Q3 Review"
```

Points to hold on to:

- Slide **numbers shift** after any insert, delete, paste or reorder. Re-run `list` before addressing a slide by number.
- `verify` returns `image_path` — **read the image and look at it**. Overflow detection catches the 720px case, not an ugly one.
- The browser's overflow badge is advisory; your own `verify` run is the check that counts.
- If the user restored a version, every slide on disk changed. Treat all your cached content as stale.
- You do not need to stop the server to export; `export_pptx` loads the preview file directly over `file://` in headless Chromium.
