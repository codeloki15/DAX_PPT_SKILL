# Data Axle presentation design system

The brand contract for every slide. Read it before slide 1. A slide that breaks
these rules looks off-brand next to the others, even if it's fine on its own.

Tool names refer to `dax.py` subcommands: `slide`, `chart`, `exhibit`, `icon`,
`profile`, `aggregate`, `verify`.

---

## The look

A white 1280x720 slide with the **Data Axle headline**: a blue kicker, a navy
action title and a 2px navy rule. Below it is a calm body:

- one **thesis line** in large, light type
- up to **three iconed points**
- **one exhibit panel**: light grey with a navy top rule
- a **takeaway** pinned to the bottom

Then a **source line** and the **Data Axle footer**.

Clean decks come from hierarchy and restraint:

- big type for the claim
- few, short words for the support
- one exhibit
- no outlined boxes

A slide is not a memo. When content doesn't fit, cut words. Never shrink type,
and never add a second panel.

## Start every slide from a layout

Never hand-write the page frame or the CSS. Start each slide from a house
layout. It carries the stylesheet, the headline, the margins and the footer, so
every slide in the deck matches.

```bash
dax.py --workspace WS slide layouts
dax.py --workspace WS slide new --slide 2 --layout narrative \
  --kicker "Market sizing | 2026" \
  --title "Three segments drive 80% of addressable demand" \
  --lead "Demand concentrates where data coverage is deepest." \
  --panel-title "Addressable demand by segment" --panel-subtitle "US\$ billions, 2026" \
  --source "Data Axle consumer file, Q2 2026" \
  --exhibit-label "Exhibit 2 | Addressable demand by segment" --deck "Growth plan"
```

| Layout | Use for |
|---|---|
| `narrative` | **The default content slide.** Thesis, up to 3 iconed points and a takeaway on the left; one exhibit panel on the right |
| `exhibit` | A data-led slide: thesis, one full-width chart or table, takeaway |
| `comparison` | A vs B, before/after, two segments: thesis, two panels side by side, takeaway |
| `title` | Deck cover |
| `section` | Section divider |
| `blank` | Headline and footer only. Use it only when nothing above fits |

The new file contains dashed **slot** boxes, for example "Replace with the points
exhibit". Replace each one with the HTML the named builder returns. `verify`
reports any slot or "Replace with" text still on the slide.

### Anatomy of `narrative`

```
KICKER | SECTION LABEL                                         (10.5px, blue text)
The action title states the finding, one line if possible      (27px, navy, 600)
────────────────────────────────────────────────────────────── (2px navy rule)
Thesis: one sentence of context, large and light     ┌━━━━━━━━━━━━━━━━━━━━━━━━━┐
                                                      │  Panel title            │
 (●) Point heading                                    │  units / scale          │
     One or two lines of support, one **bold** fact   │  [ chart ]              │
 (●) Point heading                                    │                         │
     One or two lines                                 │  scorecard or table     │
 (●) Point heading                                    │                         │
     One or two lines                                 │                         │
 ▌ KEY TAKEAWAY                                       │                         │
 ▌ The implication, one or two lines                  └─────────────────────────┘
Source: where every figure comes from                          (10px, muted)
──────────────────────────────────────────────────────────────
Exhibit 1 | what it shows                       Data Axle | Deck title | 3
```

## Type scale

| Element | Size / weight | Colour |
|---|---|---|
| Kicker | 10.5px / 700, uppercase, .14em tracking | blue text `#007BAD` |
| Action title | 27px / 600 | navy `#12263F` |
| Thesis (`.lead`) | 18px / 300 | black `#221F20` |
| Point heading | 16px / 600 | navy |
| Point text, takeaway | 13.5px / 400, line-height 1.5 | slate `#3C4456` / black |
| Panel title | 13.5px / 600, centred | black |
| Panel subtitle (units) | 11px | muted `#5F6F82` |
| Table cells, scorecard | 12.5px | slate |
| Table headers, labels | 10–10.5px / 600, uppercase | muted |
| Source line, footer | 10px | muted |

**Floors:** running text is never under 12px, and nothing is under 10px.
`verify` warns on both.

Typeface: **Poppins** throughout. The layouts already load it. Don't load other
fonts, Tailwind or icon fonts.

## Colour

| Token | Hex | Use |
|---|---|---|
| navy | `#12263F` | Action title, rules, panel top rule, icon circles, focus chart series |
| brandBlue | `#00A0DC` | **Fills and lines only:** takeaway rule, cover rule, chart series. Never small text (2.97:1) |
| blue text | `#007BAD` | Kickers and any small blue text (4.7:1) |
| black | `#221F20` | Thesis, bold facts, takeaway text |
| slate | `#3C4456` | Body copy, table cells |
| muted | `#5F6F82` | Labels, units, table headers, source, footer (5.1:1) |
| rule | `#D4D9E0` | Hairlines |
| light | `#F4F6F8` | The exhibit panel fill |
| tint | `#EAF6FB` | Takeaway fill |
| positive / warning / negative | `#1F7A5C` / `#B07A16` / `#B3341F` | **State only**: status dots, scorecard status |
| warning text | `#8F6212` | Warning status as text (the fill amber is 3.72:1) |

**Contrast rule:** text must reach 4.5:1 against its background, or 3:1 at 24px+
or bold at 18.66px+. `verify` checks every word.

Semantic colours carry state only, never decoration. Colour a status by what it
*means*: dominant or on track is positive, at risk is warning, failing is
negative.

## Word budgets

| Element | Budget |
|---|---|
| Action title | 16 words, one line preferred, never more than two |
| Thesis | 25 words |
| Points | at most 3. Heading 6 words; text **28 words** (the builder refuses over 45) |
| Takeaway | 35 words (refused over 55) |
| Table | 6 rows x 4 columns |
| **Body copy per slide** | **170 words.** `verify` warns above this |

Detail that doesn't fit belongs in the speaker notes (`dax.py notes --set`), not
on the slide.

## The action title rule

Every title states the **finding**, not the topic. A reader should be able to
follow the whole argument from the titles alone, in order.

  BAD  (topic label):  "Revenue by region"
  GOOD (action title): "Northeast and West drive 73% of revenue, concentrating renewal risk"

  BAD:  "Opposition landscape"
  GOOD: "After Bihar, the NDA outscores a fragmented opposition on every capability"

No trailing period. Keep it to one line where you can; a two-line title eats
the body's space.

## Components

Paste each builder's HTML into its layout slot. The builders are inline-styled
and brand-locked, so don't restyle them.

**Points**: the iconed support for the thesis. Each point gets a white glyph
icon in a navy circle; with no icon, the circle shows its number.

```bash
dax.py --workspace WS exhibit --type points --data '{"items":[
  {"icon":"target","title":"Sharper targeting","text":"Match rates rose to **38%** after the identity refresh."},
  {"icon":"speed","title":"Faster activation","text":"Audiences now reach channels in hours, not days."},
  {"icon":"filter","title":"Lower cost","text":"Cost per acquisition fell as waste dropped."}]}'
```

The icons must be glyph icons (see `dax.py icon list`). Use `**bold**` for the one
fact a reader should catch.

**Takeaway**: the "so what", pinned to the bottom of its column.
`--data '{"text":"...","label":"Key takeaway"}'`. Label options: *Key takeaway*,
*Implication*, *Forecast*, *Recommendation*.

**Scorecard**: a compact metric → status list with semantic status colours. It
suits a panel on its own or under a chart.
`--data '{"columns":["Dimension","Status"],"rows":[{"label":"Coverage","status":"Ahead of plan","state":"positive"}]}'`

**Chart**: the exhibit panel's main content. See [charts.md](charts.md).
- The panel title names the chart, so don't pass `chart --title`.
- **Focus vs context:** colour the subject navy and the comparison grey with
  `--colors 12263F,A9B4C2`.
- **Diverging values** (lean, variance, net change): use `bar_stacked` with two
  series, one holding the negatives and one the positives, zeros elsewhere. Pass
  `--colors A9B4C2,12263F`.

**Table**: plain `<table>` with `<thead>` and `<tbody>`, 6 rows at most. It
exports as a native PowerPoint table. Mark status with a dot before the text:
`<span class="dot pos"></span>Low`. The classes are `pos`, `warn`, `neg` and
`neutral`.

**KPI row, timeline, process flow, funnel, 2x2, harvey table**: see
[exhibits.md](exhibits.md). Place them in a panel, or in the left column instead
of points.

## Build everything as HTML, never as images

All slide content is real HTML text and CSS. The exporter turns HTML text into
native, editable PowerPoint text, but it rasterises `<svg>` into a flat picture.
So:

- Build diagrams from styled `<div>`s, never `<svg>`, and never images of text.
- Build tables as `<table>`, charts with `dax.py chart`, and KPI figures as text.
- Icons are the one exception: the bundled glyphs via the points exhibit or
  `dax.py icon`. They carry no words, so exporting them as pictures loses
  nothing.

## Never invent numbers

Every figure comes from the user or from `profile`/`aggregate` on their data.
If a figure isn't available, show an em dash `—` and note that it's to be
populated. Never fabricate rates, percentages, revenue or counts.

## The user can edit slides in the browser

Once the preview is served, the user can edit text, formatting, chart data,
notes and slide order, and those edits are written back to the slide files. Slide
files are shared state: re-read a slide before editing it.

## Verify every slide

`dax.py verify --slide N` renders the slide at 1280x720 and returns:

- **issues** (hard failures): overflow past the frame, or an unfilled layout slot
- **warnings** (house style): body copy over 170 words, running text under 12px,
  text under 10px, and text below the contrast rule

Fix both, re-verify, then **read the screenshot and look at it**. Check for dead
space, cramped panels, and styling that differs from the other slides.

## Critical rules

1. Every slide starts from a layout (`dax.py slide new`). Never hand-write the frame or the CSS.
2. Every title is an action title: the finding, 16 words or fewer.
3. One thesis line, at most three points, one exhibit panel, one takeaway.
4. Stay within the word budgets. Cut words; never shrink type below the floors.
5. Brand tokens only. brandBlue is a fill and line colour, never small text.
6. Semantic colours convey state only.
7. No outlined boxes around text, no icon fonts, no emoji, no gradients, no shadows.
8. HTML text only. No `<svg>` carrying words, no images of content.
9. Quantitative data goes through `dax.py chart`, and figures come from data.
10. Every slide passes `verify` with no issues and no warnings before the preview is built.

## Class reference (for hand edits)

`house.css` is embedded in every layout-built slide, and every rule is scoped to
`.slide-container`.

| Class | Element |
|---|---|
| `.kicker`, `.action`, `.rule` | Headline |
| `.content` (`.stack` for vertical layouts), `.col-main`, `.col-side`, `.cols` | Body grid |
| `.lead` | Thesis line |
| `.panel`, `.panel-t`, `.panel-s` | Exhibit panel, its title and units line |
| `.chart-embed` | Chart placeholder (from `dax.py chart`) |
| `table`, `th`, `td`, `.num`, `.dot.pos/.warn/.neg/.neutral` | Tables |
| `.src`, `.foot` | Source line, footer |
| `.cover`, `.cover-title`, `.cover-rule`, `.cover-sub`, `.sec-num` | Title and section slides |
| `.slot` | Unfilled layout slot (must not survive) |
