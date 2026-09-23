---
name: dax-ppt
description: Use when building, editing or exporting a Data Axle presentation, slide deck, or PowerPoint file - builds consulting-grade 1280x720 HTML slides in the Data Axle house style, charts and tables that export as NATIVE editable PowerPoint objects, a live browser preview the user can edit, and a .pptx export. Triggers on "deck", "slides", "presentation", "PowerPoint", "pptx", "board deck", "QBR", "client deck".
---

# Data Axle presentations

Build a deck as a set of standalone 1280x720 HTML slides, verify each one
visually, stitch them into a live preview the user can edit in the browser,
then export to PPTX with **editable text, native charts and native tables**.

**Why HTML and not python-pptx directly:** the export converts HTML text into
real PowerPoint text runs, and replaces chart/table placeholders with native
PowerPoint chart and table parts. The recipient can right-click a chart and
choose *Edit Data*. Build slides as HTML and this comes for free; hand-build
PPTX shapes and you lose it.

## Setup (once)

```bash
pip install playwright python-pptx pandas openpyxl
playwright install chromium
python3 skills/dax-ppt/scripts/dax.py doctor     # verifies all of the above
```

`doctor` exits non-zero and names the fix for anything missing. Run it first if
anything behaves unexpectedly.

## The workflow

All commands take `--workspace DIR`. **Always pass it explicitly** — it decides
where slides, charts and exports live, and it is what keeps two decks from
overwriting each other. Set it once per deck and reuse it.

### 1. Understand the ask before building

Establish, asking the user only for what you cannot infer:

- **Topic and the argument** — what the deck must convince someone of
- **Audience** — board, client, internal team; it sets the altitude
- **Slide count** — 8-15 is typical; more needs a reason
- **Data** — a CSV/Excel path, or figures they supply. No data is a red flag:
  read "Never invent numbers" below before proceeding.

Then **write the action titles first**, as a plain list, and show the user.
Titles are the argument; if they don't hold together, the deck won't either.
Get agreement on that list before building slides.

### 2. Ground every number in real data

```bash
dax.py --workspace WS profile   --file sales.csv
dax.py --workspace WS aggregate --file sales.csv --group-by region \
       --agg revenue:sum --sort-by revenue_sum --share
```

`profile` gives columns, dtypes, null counts and ranges. `aggregate` does the
arithmetic in pandas — group-bys, filters, top-N, percent-of-total.

**Never do arithmetic in your head, and never invent a figure.** Every number
on a slide traces back to a file or to something the user stated. If a figure
isn't available, render an em-dash `—` and note that it is to be populated.
Fabricated accuracy rates and revenue numbers are the fastest way to destroy
trust in a deck.

### 3. Build each slide as HTML

Write `WS/slides/slide_001.html`, `slide_002.html`, … with your normal file
tools. Copy the skeleton from
[references/design_system.md](references/design_system.md) — it defines the
required structure: `.kicker`, `.action`, the 2px navy rule, `.body`, `.foot`.

Non-negotiables (the full contract is in the design system reference):

- Exactly **1280x720**, white background, **Poppins** throughout
- Every title is an **action title** — it states the finding, not the topic.
  Bad: "Revenue by region". Good: "Northeast and West drive 73% of revenue,
  concentrating renewal risk in two regions"
- Brand tokens only: brandBlue `#00A0DC` (single accent), navy `#12263F`,
  black `#221F20`, slate `#3C4456`, muted `#6A7C90`, rule `#D4D9E0`,
  light `#F4F6F8`. Semantic green/amber/red carry **state only**, never decoration
- **No icons, no emoji, no gradients, no shadows, no dark backgrounds**
- **Never use `<svg>` for anything carrying words** — SVG rasterises into a flat
  picture on export. Build diagrams from styled `<div>`s so the text stays editable
- Content must **fill** the frame and must **never** overflow 720px

### 4. Use the builders instead of hand-coding

**Charts** — any quantitative display of 3+ points:

```bash
dax.py --workspace WS chart --id rev_by_region --type column \
  --categories "Northeast,Midwest,South,West" \
  --series "FY24:12.4,9.1,15.2,11.8" --series "FY25:14.9,9.8,18.1,13.2" \
  --title "Revenue by region"
```

It prints `embed_html` — paste that into a container with real height:

```html
<div class="exh" style="flex:1;display:flex;flex-direction:column;">
  <div class="exh-t">EXHIBIT 1 | REVENUE BY REGION</div>
  <div class="chart-embed" data-chart-id="rev_by_region" style="flex:1;min-height:200px;"></div>
</div>
```

Types: `column bar line area pie doughnut column_stacked bar_stacked waterfall`.
Never compute bar widths or percentages yourself. Details and the waterfall
convention: [references/charts.md](references/charts.md).

**Exhibits** — standard infographic structures:

```bash
dax.py --workspace WS exhibit --type kpi_row \
  --data '{"kpis":[{"value":"38%","label":"Match rate lift","state":"positive"}]}'
```

Types: `timeline process_flow funnel matrix_2x2 harvey_table kpi_row`. The
returned HTML is brand-styled and inline-styled — paste it, don't restyle it.
Exact input shapes: [references/exhibits.md](references/exhibits.md).

**Tables** stay as plain `<table>` markup — the exporter rebuilds them as native
PowerPoint tables automatically.

### 5. Verify every slide — actually look at it

```bash
dax.py --workspace WS verify --slide 1
```

This renders the slide headlessly at exactly 1280x720 and reports overflow
programmatically. **Then read the returned `image_path` with your image-reading
tool and look at the screenshot.** The overflow check catches hard failures; only
your eyes catch a diagram stranded in the top third, a cramped exhibit, or
styling that drifted from the other slides.

Fix and re-verify until clean. Do not build the preview from unverified slides.

### 6. Preview, and hand it to the user

```bash
dax.py --workspace WS preview --title "Deck title"
dax.py --workspace WS open --serve
```

`open --serve` starts a local server on 127.0.0.1 and opens the browser. The
server must **keep running** to serve the preview — run it in the background if
you need the shell back.

Served over http the user can edit text, formatting, chart data, notes and slide
order, and **those edits are written back to the slide files you are working
on**. Opened as `file://` it degrades to read-only.

> **Slide files are shared state.** Once the preview is open, re-read a slide
> before editing it — the user may have changed it. If they say they already
> fixed something, believe them and re-read rather than regenerating.

### 7. Export

```bash
dax.py --workspace WS export --title "Deck title"
```

Writes to `WS/final_outputs/` and reports how many native charts, native tables
and speaker notes were written. Verify that count matches what you built: if
`native_charts.inserted` is short, a placeholder was missing from a slide.

Speaker notes: `dax.py --workspace WS notes --slide 3 --set "..."` — they export
into PowerPoint's real notes field.

## Command reference

| Command | Purpose |
|---|---|
| `doctor` | Check dependencies; run this first when anything misbehaves |
| `profile --file F` | Profile a CSV/TSV/Excel file |
| `aggregate --file F --agg COL:FN` | Group, filter, top-N, percent-of-total |
| `chart --id ID --type T ...` | Create a native chart spec |
| `exhibit --type T --data JSON` | Build a brand-styled exhibit |
| `verify --slide N` | Screenshot + overflow check |
| `preview --title T` | Stitch slides into the live preview |
| `open [--serve]` | Serve the preview and open a browser |
| `notes --slide N [--set ...]` | Read or write speaker notes |
| `export --title T [--output P]` | Export to PPTX |
| `list` | List slides with their action titles |
| `reset --yes` | Wipe slides/charts/screenshots (keeps exports) |

Every command prints one JSON object and exits non-zero on error. Pass JSON
arguments inline or as `@path/to/file.json`.

## References

- [design_system.md](references/design_system.md) — the full brand contract, slide
  skeleton, and layout rules. **Read before slide 1.**
- [charts.md](references/charts.md) — chart spec schema, all 9 types, waterfall
- [exhibits.md](references/exhibits.md) — exact input shape for all 6 exhibits
- [data.md](references/data.md) — profile output and the aggregate grammar
- [export.md](references/export.md) — how the export works and how to triage it
- [browser_editing.md](references/browser_editing.md) — what the user can edit live

## Out of scope

Image generation and stock-photo/icon search are deliberately absent. The house
style is **HTML text and CSS only** — content is never an image, because images
export as flat pictures instead of editable text. Use exhibits and charts.
