# Export pipeline

How `dax.py export` turns HTML slides into a PPTX with editable text, native charts and native tables — and how to diagnose it when the deck comes back as pictures.

## ⚠ Export requires network access

The preview page loads six libraries from `cdn.jsdelivr.net` at export time. Headless Chromium must reach the network or `page.wait_for_load_state("networkidle")` stalls and the `.slide-content` wait fails 10s later. There is no vendored/offline fallback.

| Library | Pinned URL |
|---|---|
| PptxGenJS 4.0.1 | `https://cdn.jsdelivr.net/npm/pptxgenjs@4.0.1/dist/pptxgen.bundle.js` |
| JSZip 3.10.1 | `https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js` |
| dom-to-pptx 2.1.1 | `https://cdn.jsdelivr.net/npm/dom-to-pptx@2.1.1/dist/dom-to-pptx.bundle.js` |
| Chart.js 4.5.1 | `https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js` |
| html2canvas 1.4.1 | `…/html2canvas@1.4.1/dist/html2canvas.min.js` (PDF path only) |
| jsPDF 2.5.1 | `…/jspdf@2.5.1/dist/jspdf.umd.min.js` (PDF path only) |

Load order is load-bearing: PptxGenJS and JSZip must precede dom-to-pptx (`assets/templates/live_preview_template.html:2442-2452`).

## The pipeline

1. **Standalone slides.** `<workspace>/slides/slide_NNN.html`, each a self-contained 1280×720 page.
2. **`dax.py preview`** (`build_preview`, deck.py:164) stitches them. Per slide it inlines local images as base64, scopes the `<style>`, strips the `<!-- SPEAKER_NOTES … -->` comment out of the body, and wraps the body in `<div class="slide-content" data-slide-number="N">`. It injects all stored chart specs as `{{chart_specs}}` and writes `<workspace>/slides/live_preview.html`. Slide order comes from `list_slide_numbers()`, so a numbering gap (001, 002, 004) cannot desync anything.
3. **Playwright loads the preview** over `file://`, headless Chromium, `networkidle`, then `wait_for_selector(".slide-content", timeout=10000)` (deck.py:397-404).
4. **`_EXTRACT_CHARTS_JS`** (deck.py:293) walks each `.slide-content` by `domIndex` and, per `.chart-embed[data-chart-id]`, records `{dom_index, chart_id, x, y, w, h}` as **fractions 0..1** of the slide's bounding rect, clears the enclosing `.exh` panel's `border`/`background`/`boxShadow`, and **replaces the node** with a same-size `<div>` spacer.
5. **`_EXTRACT_TABLES_JS`** (deck.py:327) does the same for every `<table>`, additionally capturing `headers`, `rows` and `aligns`.
6. **In-page dom-to-pptx** runs via two clicks — `#export-btn` opens the dropdown, `#export-pptx` fires the export — and the download is saved with a 120 s timeout. Because the charts and tables are already gone from the DOM, the base deck is editable text with chart-shaped holes.
7. **python-pptx fills the holes.** `insert_native_charts` → `insert_native_tables` → `insert_speaker_notes`, each converting fractions to EMU against `prs.slide_width`/`slide_height` and each opening and saving the file independently.
8. **Notes** are read back from each slide's HTML comment, keyed 0-based by deck position, and written to `slides[idx].notes_slide.notes_text_frame.text`.

The chart *data* never crosses the JS→Python boundary: only placements do. Python re-loads each spec from `<workspace>/charts/{chart_id}.json` by id.

## Why the node is REMOVED, not hidden

`visibility:hidden` leaves the element occupying layout. dom-to-pptx then rasterises the surrounding exhibit panel and drops a **blank picture on top of the native chart** — the chart is technically in the file but invisible. `el.replaceWith(spacer)` removes it from the render tree while preserving the hole's exact dimensions (deck.py:22-24, 291-292).

Two consequences that are not optional:

- The chart must sit inside a `.exh` panel, because the extractor calls `el.closest('.exh')` to strip the panel's border/background/shadow. Without it, the panel chrome rasterises around the native chart.
- The class must be exactly `chart-embed` with a `data-chart-id` attribute. `create_chart` returns the correct markup in `embed_html` — paste it verbatim.

## DOM contract

| Requirement | Why |
|---|---|
| `.slide-content` wrapper | The unit of enumeration and the fraction denominator. **Supplied by `build_preview`, not the slide author** — do not write it into `slide_NNN.html`. |
| `.chart-embed[data-chart-id="id"]` | The only selector the chart extractor matches. Anything else rasterises. |
| Chart inside a `.exh` panel | `closest('.exh')` clears panel chrome; without it the border is baked into a picture. |
| `<table>` with a real `<thead>` | No `thead th, thead td` → `if (!headers.length) return;` → **skipped, rasterises**. |
| `<table>` with a real `<tbody>` | No `tbody tr` → `if (!rows.length) return;` → **skipped, rasterises**. |
| Non-zero rendered size | A `.slide-content` or `<table>` with zero width/height is skipped entirely. |
| No text inside `<svg>` | SVG rasterises to a flat picture; the words stop being editable. Build diagrams from styled `<div>`s. |

Right-alignment is derived per column from the **header** cell's computed `text-align`, and is only applied when `len(aligns) == n_cols`.

## Running it

```bash
# default: <workspace>/final_outputs/<Clean_Title>_YYYYMMDD_HHMMSS.pptx
dax.py --workspace ./dax_workspace export --title "Q3 Board Review"

# explicit path; parent dirs are created, the basename becomes `filename`
dax.py --workspace ./dax_workspace export --title "Q3 Board Review" \
       --output ~/Desktop/board_q3.pptx
```

`--output` is made absolute. Without it, `generate_timestamped_filename` strips non-alphanumerics, collapses whitespace to `_`, truncates to 30 chars (falling back to `Presentation` if empty) and appends the timestamp. `final_outputs/` lives under the workspace and is **kept** by `dax.py reset --yes`.

## Result JSON

Success:

```json
{
  "status": "success",
  "exported": true,
  "filename": "Q3_Board_Review_20260922_141203.pptx",
  "output_path": "/abs/path/dax_workspace/final_outputs/Q3_Board_Review_20260922_141203.pptx",
  "slides_exported": 12,
  "native_charts": { "inserted": ["rev_by_region", "arr_bridge"], "errors": [] },
  "native_tables": { "inserted": 3, "errors": [] },
  "speaker_notes": { "written": 12, "errors": [] },
  "file_size_bytes": 482913
}
```

| Key | Meaning |
|---|---|
| `status` / `exported` | `"success"` / `true`, or `"error"` / `false`. Exit code is non-zero on error. |
| `filename` | Basename of the written file. |
| `output_path` | Absolute path. |
| `slides_exported` | `list_slides()["count"]`, i.e. slides found — not slides verified. |
| `native_charts` | `{inserted: [chart_id, …], errors: [str, …]}`. **Present only if at least one `.chart-embed` was found.** |
| `native_tables` | `{inserted: int, errors: [str, …]}`. **Present only if at least one qualifying table was found.** |
| `speaker_notes` | `{written: int, errors: [str, …]}`. **Present only if at least one slide had notes.** |
| `file_size_bytes` | Size after all three insert passes. |

### Verifying the export

`status: "success"` is not sufficient — every insert pass fails soft. Check three counts:

1. `native_charts.inserted` must list **every** `chart_id` you created. A missing id means the spec was not found or the placeholder was not matched.
2. `native_tables.inserted` must equal your table count. A shortfall means a table was skipped for a missing `thead`/`tbody`.
3. `speaker_notes.written` must equal the number of slides you wrote notes for.
4. All three `errors` arrays must be empty. A **missing key entirely** is the loudest signal: no `native_charts` key at all means zero `.chart-embed` nodes were found in the whole deck.

## Triage

| Symptom | Cause | Fix |
|---|---|---|
| `"Live preview not found. Run \`dax.py preview\` first."` | `<workspace>/slides/live_preview.html` does not exist, or `--workspace` points elsewhere than the build did | Run `dax.py --workspace WS preview --title T` with the **same** workspace |
| `"No slides found to export"` | `list_slides()["count"] == 0` | Write `slide_001.html` into `<workspace>/slides/` |
| `"Playwright not installed. Run: pip install playwright && playwright install chromium"` | `from playwright.sync_api import sync_playwright` failed | `pip install playwright` |
| `Export failed: Error: Executable doesn't exist…` | Playwright installed, browser binary is not | `playwright install chromium`; confirm with `dax.py doctor` (`checks.chromium`) |
| Chart exported as a **picture** | Wrong class / missing `data-chart-id`, or not inside `.exh` | Paste `embed_html` from `dax.py chart` verbatim, inside a `.exh` panel |
| Chart **missing entirely** (blank space) | `native_charts.errors` has `"<id>: no stored spec found"` — `charts/<id>.json` absent (wrong workspace, or wiped by `reset`) | Re-run `dax.py chart --id <id> …` in the correct workspace, then `preview`, then `export` |
| Chart landed on the **wrong slide** | `"<id>: slide index N out of range (deck has M)"` — preview and deck disagree on slide count | Rebuild the preview, then export; never edit `live_preview.html` by hand |
| Chart too small / stretched | Size is floored at 1 in wide × 0.5 in tall; a `.chart-embed` with collapsed height records a tiny fraction | Give the placeholder real height (`style="flex:1;min-height:200px;"` inside a flex column) |
| Table exported as a **picture** | No `<thead>` header cells, or no `<tbody>` rows — the extractor `return`s silently | Use real `<thead><tr><th>…` and `<tbody><tr><td>…`; `native_tables.inserted` will then match |
| Notes missing | Notes live in the slide HTML as `<!-- SPEAKER_NOTES … -->`; absent, or you used the browser Export button | `dax.py notes --slide N --set "…"`, rebuild preview, export via `dax.py export` |
| Export timeout (~120 s) | `page.expect_download(timeout=120000)` elapsed — very large deck, or dom-to-pptx threw in-page | Split the deck, or open the preview in a real browser and watch the console |
| Hangs then `Timeout … waiting for selector ".slide-content"` | Offline: `networkidle` never settles because the CDN scripts cannot load | Restore network access. There is no offline mode |
| Charts render blank in the **preview** but export fine | Chart.js 4.5.1 did not load (CDN) | Same as above |
| `"Export file was not created"` | Download completed but nothing landed at `output_path` | Check write permission on `--output`'s directory |
| Any other `Export failed: <Type>: <msg>` | Everything inside the Playwright block is caught by one handler (deck.py:449) | The exception type is in the message; run `dax.py doctor` first |

Run `dax.py --workspace WS doctor` before blaming the deck: it checks `python-pptx`, `pandas`, `openpyxl`, `playwright`, a live Chromium launch, and the four template assets, and exits non-zero with a `problems` array.

## Two export paths

| | Browser Export button | `dax.py export` |
|---|---|---|
| Extraction | `NativeExport.extractAndStrip()` in JS, fractions × `SLIDE_W`/`SLIDE_H` (inches) | `page.evaluate` in deck.py, raw fractions 0..1 |
| Chart data | `window.CHART_SPECS` injected in the page | Re-read from `charts/<id>.json` |
| Native build | PptxGenJS overlay deck + JSZip OOXML merge | python-pptx `add_chart` / `add_table` |
| **Speaker notes** | **Not carried over at all** | Written to the native notes field |
| Output | Browser download, `<topic_slug>_presentation.pptx` | `final_outputs/` or `--output` |
| On failure | Toasts "Charts exported as images", still downloads | Returns `{"status":"error"}`, exits non-zero |

**The practical difference: the browser button drops speaker notes.** If the deck has notes, export with `dax.py export`. The browser button is for a quick look while iterating in the preview.
