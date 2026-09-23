# Exhibit Library

Six parameterized, brand-locked infographic builders invoked via `dax.py exhibit`; each returns inline-styled HTML you paste verbatim into a slide body.

## Command surface

```
dax.py exhibit --type {timeline|process_flow|funnel|matrix_2x2|harvey_table|kpi_row} \
               --data '{...}' [--workspace DIR]
```

- `--type` and `--data` are both **required**. `--type` is an argparse `choices` list — an unknown name exits **2** with argparse usage text, not JSON.
- `--data` takes inline JSON or `@file.json`. Malformed JSON → exit 1, `{"error": "--data is not valid JSON: ..."}`. Use `@file.json` for anything with quotes or newlines.
- Success prints one JSON object and exits 0:

```json
{
  "status": "created",
  "exhibit_type": "kpi_row",
  "html": "<div style=\"display:flex;gap:10px;\">…",
  "usage": "Paste the html into the slide's .body (typically inside an .exh panel with an .exh-t caption). It is inline-styled and self-contained; do not restyle it."
}
```

- Validation failure prints `{"error": "<type>: <message>"}` and exits **1**. The `html` key is absent — never paste an error payload.
- `exhibit` is stateless: it writes nothing to the workspace and needs no prior `preview`.

## Type index

| type | data key it reads | count rule | optional keys |
|---|---|---|---|
| `timeline` | `items` | 2–7 | `description` per item |
| `process_flow` | `steps` | 2–6 | `description` per step; `emphasize` |
| `funnel` | `stages` | 2–6 | `value` per stage |
| `matrix_2x2` | `quadrants` | exactly 4 | `items` per quadrant; `x_axis`, `y_axis`, `highlight` |
| `harvey_table` | `columns` + `rows` | ≥1 each | — |
| `kpi_row` | **`kpis`** (not `items`) | 2–5 | `delta`, `state` |

---

## timeline

Horizontal milestone rail: uppercase blue label, blue dot on a grey rule, navy title, optional description.

```
{"items": [{"label": str, "title": str, "description"?: str}]}
```

| | |
|---|---|
| Count | `2 <= len(items) <= 7` |
| Error | `timeline: timeline needs 2-7 items: [{label, title, description?}]` |

```bash
dax.py exhibit --type timeline --data '{"items":[
  {"label":"Q1 2025","title":"Data ingest live","description":"Three source feeds onboarded"},
  {"label":"Q2 2025","title":"Identity graph rebuild"},
  {"label":"Q3 2025","title":"Activation pilot"}]}'
```

Gotchas
- Cells are `flex:1` — equal width regardless of text length. 7 items is narrow; prefer ≤5 with descriptions.
- `description` is gated on truthiness; omit it rather than passing `""`.
- Items must be **objects**. `{"items":["Q1","Q2"]}` raises an uncaught `AttributeError: 'str' object has no attribute 'get'` (traceback on stderr, exit 1, no JSON).

---

## process_flow

Row of boxed steps joined by a `&#8594;` arrow glyph. Navy header bar per step with an auto-numbered blue index.

```
{"steps": [{"title": str, "description"?: str}], "emphasize"?: [int]}
```

| | |
|---|---|
| Count | `2 <= len(steps) <= 6` |
| Error | `process_flow: process_flow needs 2-6 steps: [{title, description?}]` |

```bash
dax.py exhibit --type process_flow --data '{"steps":[
  {"title":"Ingest","description":"Client file lands in S3"},
  {"title":"Match","description":"Resolve to Data Axle ID"},
  {"title":"Enrich"},
  {"title":"Activate","description":"Push to DSP"}],"emphasize":[1]}'
```

Gotchas
- **`emphasize` must be 0-based JSON integers.** Tested as `if i in emphasize` against `int`. `"emphasize": ["1"]` matches nothing and silently produces no highlight — verified. Emphasized steps get `1.5px solid #00A0DC` instead of `1px solid #D4D9E0`.
- Step numbers render from `i + 1`. Do **not** write `"1. Ingest"` in `title` — you get "1 1. Ingest".

---

## funnel

Centered bars narrowing 100% → 45%, navy with a rising opacity ramp; the **last** stage is brand blue at full opacity.

```
{"stages": [{"label": str, "value"?: any}]}
```

| | |
|---|---|
| Count | `2 <= len(stages) <= 6` |
| Error | `funnel: funnel needs 2-6 stages: [{label, value?}]` |

```bash
dax.py exhibit --type funnel --data '{"stages":[
  {"label":"Addressable universe","value":"48M"},
  {"label":"Matched records","value":"31M"},
  {"label":"Qualified audience","value":"9.4M"},
  {"label":"Converted","value":"212K"}]}'
```

Gotchas
- Order **top-of-funnel → converted**. The emphasis is hardcoded to the last stage; a reversed list emphasizes the wrong end.
- No width, color or opacity options exist. Width is `100 - i * (55 / max(n-1, 1))`; n=4 → 100/82/63/45%.
- `value` is gated on `is not None`, so `"value": 0` **does** render (unlike `kpi_row`'s `delta`).

---

## matrix_2x2

CSS-grid 2×2 with axis labels down the left and across the bottom.

```
{"quadrants": [{"title": str, "items"?: [str]}, x4],
 "x_axis"?: {"low": str, "high": str},
 "y_axis"?: {"low": str, "high": str},
 "highlight"?: int}
```

| | |
|---|---|
| Count | `len(quadrants) == 4` exactly |
| Error | `matrix_2x2: matrix_2x2 needs exactly 4 quadrants (TL, TR, BL, BR): [{title, items?}]` |

```bash
dax.py exhibit --type matrix_2x2 --data '{
  "x_axis":{"low":"Low reach","high":"High reach"},
  "y_axis":{"low":"Low intent","high":"High intent"},
  "quadrants":[
    {"title":"Nurture","items":["Long sales cycle"]},
    {"title":"Invest","items":["Priority segment","Highest LTV"]},
    {"title":"Deprioritize"},
    {"title":"Harvest","items":["Retarget only"]}],
  "highlight":1}'
```

Gotchas
- Quadrant order is row-major **TL, TR, BL, BR**. Index 1 is top-right.
- **`highlight` must be a 0-based integer** (`i == highlight`). `"highlight": "1"` silently highlights nothing — verified. Highlighted = `1.5px solid #00A0DC` + `#fff`; others = `1px solid #D4D9E0` + `#F4F6F8`.
- `x_axis`/`y_axis` are optional; missing keys fall back to the literals `"High"` / `"Low"`.
- `items` entries are **plain strings**, not objects.
- The root div is `height:100%;min-height:0`. It collapses to zero height in a plain div — the `.exh` wrapper must be a flex column with real height (see *Placement*).

---

## harvey_table

Comparison table with Unicode harvey-ball glyphs plus a fixed legend row.

```
{"columns": [str], "rows": [{"label": str, "scores": [int]}]}
```

| | |
|---|---|
| Count | `columns` and `rows` both non-empty |
| Error (empty) | `harvey_table: harvey_table needs columns: [..] and rows: [{label, scores: [0-4, ..]}]` |
| Error (width) | `harvey_table: row 'Vendor B' has 1 scores for 2 columns` |

Glyph map: `0 ○` · `1 ◔` · `2 ◑` · `3 ◕` · `4 ●`

```bash
dax.py exhibit --type harvey_table --data '{
  "columns":["Coverage","Accuracy","Refresh rate"],
  "rows":[{"label":"Data Axle","scores":[4,4,3]},
          {"label":"Vendor B","scores":[2,3,1]},
          {"label":"Vendor C","scores":[1,2,2]}]}'
```

Gotchas
- `len(scores)` must equal `len(columns)` **per row**; the error names the offending row's label.
- **Scores are not range-validated.** Lookup is `glyphs.get(int(s), glyphs[0])`, so an out-of-range score silently clamps to the *empty* ball, not the full one: `9` → `○`, `-1` → `○` (verified). Keep scores in 0–4.
- Floats truncate via `int()`: `2.7` → `◑`.
- A non-numeric score is caught cleanly: `harvey_table: invalid literal for int() with base 10: 'bad'`.
- The legend (`● Full  ◑ Partial  ○ None`) is always appended and cannot be suppressed. The first header cell is an empty `<th>` for the row-label column.
- Glyphs are literal non-ASCII. Under a non-UTF-8 locale set `PYTHONIOENCODING=utf-8`.

---

## kpi_row

Row of stat tiles: big navy tabular-nums value, uppercase muted label, optional colored delta.

```
{"kpis": [{"value": any, "label": str, "delta"?: str,
           "state"?: "positive"|"warning"|"negative"}]}
```

| | |
|---|---|
| Count | `2 <= len(kpis) <= 5` |
| Error | `kpi_row: kpi_row needs 2-5 kpis: [{value, label, delta?, state?}]` |

```bash
dax.py exhibit --type kpi_row --data '{"kpis":[
  {"value":"94.2%","label":"Match rate","delta":"+3.1 pts YoY","state":"positive"},
  {"value":"$1.8M","label":"Incremental revenue","delta":"+12%","state":"positive"},
  {"value":"11 days","label":"Time to activate","delta":"+4 days","state":"negative"}]}'
```

Gotchas
- **The key is `kpis`, not `items`.** `{"items":[...]}` reads as zero kpis and fails with the 2-5 error — verified.
- `state` must be exactly `positive` | `warning` | `negative`. Any other value (including `"good"`, `"up"`, `"success"`) silently falls back to muted `#6A7C90` — no error raised.
- `state` only colors the **delta line**. With no `delta`, `state` has zero visible effect.
- `delta` is gated on truthiness, so `"delta": 0` or `""` renders nothing. Pass `"0.0 pts"` as a string.
- Tiles are `flex:1` and already carry the `.exh` chrome inline (`1px solid #D4D9E0`, `border-top:3px solid #12263F`, white). Placing a kpi_row inside another `.exh` panel double-frames it — put it bare in `.body`.

---

## The HTML is brand-locked — paste, never restyle

Every builder emits **100% inline `style=` attributes and zero class names**. Nothing depends on the slide stylesheet, and nothing in the deck CSS can override it.

Do:
- Copy the `html` string from the JSON result into the slide body **byte-for-byte**.

Do not:
- Add classes, wrap in a styled span, or edit any `style=` value.
- Swap colors "to match the section" — the tokens below are the brand palette and are the only colors these builders emit.
- Hand-edit the markup to add a row/step beyond the count limits.

To change content, re-run `dax.py exhibit` with different `--data`.

### Brand tokens the builders use

| Constant | Hex | Used for |
|---|---|---|
| `BRAND_BLUE` | `#00A0DC` | timeline labels + dots, step index, last funnel bar, emphasis borders, bullet squares, harvey glyphs |
| `NAVY` | `#12263F` | titles, step header bars, funnel bars, kpi values, kpi top border, harvey header rule |
| `BLACK` | `#221F20` | harvey row labels (only use) |
| `SLATE` | `#3C4456` | body/description text, quadrant bullets |
| `MUTED` | `#6A7C90` | axis labels, kpi labels, harvey headers, flow arrows, default delta color |
| `RULE` | `#D4D9E0` | timeline rail, borders, table row rules |
| `LIGHT` | `#F4F6F8` | non-highlighted matrix quadrant fill (only use) |
| state `positive` | `#1F7A5C` | kpi delta |
| state `warning` | `#B07A16` | kpi delta |
| state `negative` | `#B3341F` | kpi delta |

Plus literal `#fff` for step/tile/highlight backgrounds.

### Why div-only: PPTX text fidelity

These builders emit divs, `<table>` (harvey) and `<ul>/<li>` (matrix) — and **never `<svg>`, `<img>`, `<canvas>` or `data:` URIs**. This is an export constraint, not a style preference: the HTML→PPTX converter turns HTML text into native, editable PowerPoint text runs, but **rasterizes any `<svg>` into a flat picture**. A flowchart drawn with divs exports as editable text runs and zero pictures; the same diagram as inline SVG exports as fewer runs plus uneditable images.

That is why the connectors are the text arrow `&#8594;`, the harvey balls are Unicode glyphs, and every line, box and fill is a CSS border or background. The client can retype any word in PowerPoint.

---

## Placement

Paste into the slide's `.body`, normally inside an `.exh` panel with an `.exh-t` caption. Those two classes live in the deck stylesheet (see `references/design_system.md`), **not** in the exhibit HTML.

```html
<div class="body">
  <div class="exh" style="flex:1;display:flex;flex-direction:column;">
    <div class="exh-t">EXHIBIT 2 | ACTIVATION PATH</div>
    <!-- html from dax.py exhibit, verbatim -->
  </div>
</div>
```

- `matrix_2x2` **requires** that flex-column wrapper with real height, or it collapses.
- `kpi_row` already has tile chrome — place it directly in `.body`, no `.exh` panel.
- Caption convention: `EXHIBIT N | TITLE IN CAPS`.

## When to hand-build instead

Use `dax.py exhibit` whenever one of the six covers the layout — it is faster, brand-exact and consistent across the deck.

Hand-build inline-styled divs **only** when no type fits: org charts, maps, Gantt/swimlanes, nested or 3×3 grids, radial diagrams, before/after splits.

If you hand-build:
- Inline styles only, from the token table above.
- Divs/tables/lists only — no SVG, no images, or the export loses editable text.
- Match the type sizes in use here: 9.5–10px uppercase labels, 10.5px body, 11.5–12px titles.

Never hand-build to dodge a count limit. 8 milestones is not a 7-item timeline plus one — split the slide or cut.
