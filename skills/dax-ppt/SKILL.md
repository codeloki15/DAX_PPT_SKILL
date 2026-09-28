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
pip install playwright python-pptx pandas openpyxl pillow
playwright install chromium
```

**Locating the CLI.** `scripts/dax.py` sits next to this SKILL.md, so resolve it
relative to this file rather than to the working directory — when this skill is
installed as a plugin it does not live under the project you are working in.
Set it once and reuse it:

```bash
DAX="python3 /absolute/path/to/skills/dax-ppt/scripts/dax.py"
$DAX doctor                                      # verifies the install
```

`doctor` exits non-zero and names the fix for anything missing. Run it first if
anything behaves unexpectedly.

## The workflow

All commands take `--workspace DIR`. **Always pass it explicitly** — it decides
where slides, charts and exports live, and it is what keeps two decks from
overwriting each other. Point it at the user's project (not at the skill
directory), set it once per deck, and reuse it.

### 1. Understand the ask before building

Establish, asking the user only for what you cannot infer:

- **Topic and the argument** — what the deck must convince someone of
- **Audience** — board, client, internal team; it sets the altitude
- **Slide count** — 8-15 is typical; more needs a reason
- **Data** — a CSV/Excel path, or figures they supply. No data is a red flag:
  read "Never invent numbers" below before proceeding.

Then **write the storyline first**, as a plain list, and show the user:

- the **cover** title
- each **topic** name (a topic divider opens each one)
- under each topic, the **action titles** of its content slides

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

### 3. Start every slide from a layout

Never write a slide's frame or CSS by hand. Start it from a house layout. The
layout carries the stylesheet, the Data Axle headline, the margins and the
footer, which is what makes every slide in the deck match:

```bash
dax.py --workspace WS slide new --slide 2 --layout narrative \
  --kicker "Market sizing | 2026" \
  --title "Three segments drive 80% of addressable demand" \
  --lead "Demand concentrates where data coverage is deepest." \
  --panel-title "Addressable demand by segment" --panel-subtitle "US\$ billions" \
  --source "Data Axle consumer file, Q2 2026" \
  --exhibit-label "Exhibit 2 | Addressable demand by segment" --deck "Growth plan"
```

| Layout | Use for |
|---|---|
| `narrative` | **Default.** Thesis, up to 3 iconed points and a takeaway on the left; one exhibit panel on the right |
| `exhibit` | Data-led: thesis, one full-width chart or table, takeaway |
| `comparison` | A vs B: thesis, two panels side by side, takeaway |
| `title` | **Slide 1, always.** Cover on the Data Axle dark background: DATA-AXLE kicker, title, date |
| `topic` | **Before each new topic.** Divider on the Data Axle light background: the topic name (2-7 words) |

The new slide contains dashed **slot** boxes ("Replace with the points
exhibit…"). Replace each one with the HTML from the builder it names (step 4).

Deck shape: **cover → topic → its content slides → topic → its content slides →
…** The dividers tell the audience a new topic is starting. Build them with
`slide new --layout title` and `--layout topic`; they need nothing else.

What makes a slide look professional rather than a text dump (the full contract
is in [references/design_system.md](references/design_system.md), **read it
before slide 1**):

- **One thesis line, at most three points, one exhibit panel, one takeaway.**
  Not more boxes and not more bullets.
- **Word budgets:** title 16 words, thesis 25, each point 28, takeaway 35, and
  **170 words of body copy per slide**. If it doesn't fit, cut words and move
  detail to the speaker notes. Never shrink the type.
- **Type floors:** running text at least 12px, nothing under 10px, and every
  word must pass contrast. brandBlue `#00A0DC` is for fills and lines; small blue
  text uses `#007BAD`.
- Every title is an **action title**: it states the finding, not the topic.
  Bad: "Revenue by region". Good: "Northeast and West drive 73% of revenue,
  concentrating renewal risk".
- **No outlined boxes around text, no icon fonts, no emoji, no gradients, no
  shadows.** Never use `<svg>` for anything carrying words, because it
  rasterises on export.

### 4. Fill the slots with the builders

**Points**: the left column's support. Each point gets a white glyph icon in a
navy circle:

```bash
dax.py --workspace WS exhibit --type points --data '{"items":[
  {"icon":"target","title":"Sharper targeting","text":"Match rates rose to **38%** after the refresh."},
  {"icon":"speed","title":"Faster activation","text":"Audiences reach channels in hours, not days."},
  {"icon":"filter","title":"Lower cost","text":"Cost per acquisition fell as waste dropped."}]}'
```

**Takeaway**: the "so what", pinned to the bottom:
`--type takeaway --data '{"text":"...","label":"Key takeaway"}'`

**Chart**: the exhibit panel's main content, for any quantitative display of 3+
points:

```bash
dax.py --workspace WS chart --id rev_by_region --type bar \
  --categories "Northeast,Midwest,South,West" \
  --series "FY25:14.9,9.8,18.1,13.2" --series "FY24:12.4,9.1,15.2,11.8" \
  --colors 12263F,A9B4C2
```

Paste its `embed_html` into the panel slot. Don't pass `--title`, because the
panel title already names the chart. `--colors 12263F,A9B4C2` means focus (navy)
vs context (grey). For diverging values, use `bar_stacked` with the negatives and
positives in two series. Types:
`column bar line area pie doughnut column_stacked bar_stacked waterfall`.
Details: [references/charts.md](references/charts.md).

**Scorecard**: a metric → status list, with the status coloured by state. Put
it under the chart, or on its own with `"fill": true` so it fills the panel:
`--type scorecard --data '{"columns":["Dimension","Status"],"rows":[{"label":"Coverage","status":"Ahead of plan","state":"positive"}]}'`

**Tables**: plain `<table>` with `<thead>` and `<tbody>`, 6 rows at most
(`class="roomy"` for a short table that should fill its panel). Mark
status with `<span class="dot pos"></span>`. Tables export as native PowerPoint
tables.

**Other exhibits**: `kpi_row timeline process_flow funnel matrix_2x2
harvey_table`. See [references/exhibits.md](references/exhibits.md). **Icons**:
`dax.py icon list --search …`. See [references/icons.md](references/icons.md).

Builders return inline-styled, brand-locked HTML. Paste it as returned. If a
builder reports `warnings` about the word budget, cut the text and rebuild.

### 5. Verify every slide, and actually look at it

```bash
dax.py --workspace WS verify --slide 1
```

This renders the slide headlessly at exactly 1280x720 and returns:

- **issues**: overflow past the frame, or an unfilled layout slot
- **warnings**: more than 170 words of body copy, running text under 12px, text
  under 10px, text below the contrast rule, a title longer than two lines, or
  **dead space** (an empty block bigger than 15% of the body)

Fix both kinds and re-verify. **Then read the returned `image_path` and look at
the screenshot.** The checks catch hard failures; only your eyes catch a cramped
panel, a dead band, or a slide that doesn't match its neighbours.

Do not build the preview until every slide verifies with no issues and no
warnings.

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
| `slide new --slide N --layout L ...` / `slide layouts` | Start a slide from a house layout |
| `chart --id ID --type T ...` | Create a native chart spec |
| `exhibit --type T --data JSON` | Build a brand-styled exhibit |
| `icon list [--search Q]` / `icon use NAME` | Find a bundled icon / tint it and get the `<img>` snippet |
| `verify --slide N` | Screenshot, overflow, word budget, text size and contrast checks |
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
- [icons.md](references/icons.md) — the bundled icon library: rules, patterns, catalogue

## Out of scope

Image generation and stock-photo/icon *search* are deliberately absent. The house
style is **HTML text and CSS only** — content is never an image, because images
export as flat pictures instead of editable text. Use exhibits and charts. The one
exception is the bundled icon library (`dax.py icon`): small glyphs that export as
pictures, which is acceptable only because they carry no words.
