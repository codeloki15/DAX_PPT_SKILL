# DAX_PPT_SKILL

Builds Data Axle presentations: consulting-grade 1280x720 HTML slides that export
to PowerPoint with **editable text, native charts and native tables**.

This file is the entry point for agents that read `AGENTS.md` (OpenAI Codex,
Cursor, Devin, Kimi, Gemini, opencode, Pi and others). The skill itself is
runtime-neutral.

## Read this first

**[skills/dax-ppt/SKILL.md](skills/dax-ppt/SKILL.md) is the single source of
truth.** Read it and follow it verbatim whenever the user asks for a deck,
slides, a presentation, a PowerPoint or a `.pptx`. This file adds nothing to it
and never overrides it.

Before writing slide 1, also read
[skills/dax-ppt/references/design_system.md](skills/dax-ppt/references/design_system.md)
— the Data Axle brand contract.

## Setup

```bash
pip install playwright python-pptx pandas openpyxl
playwright install chromium
python3 skills/dax-ppt/scripts/dax.py doctor
```

`doctor` verifies every dependency and names the fix for anything missing.

## CLI cheat sheet

One entry point. Every command prints one JSON object and exits non-zero on
error. `--workspace` is always explicit — it is what keeps two decks apart.

Paths below are relative to this repository. If the skill is installed elsewhere
(as a plugin, or under `~/.claude/skills/`), resolve `dax.py` against the
installed `skills/dax-ppt/` directory and point `--workspace` at the user's
project.

```bash
D="python3 skills/dax-ppt/scripts/dax.py --workspace ./mydeck"

$D profile   --file sales.csv                      # columns, dtypes, ranges
$D aggregate --file sales.csv --group-by region \
             --agg revenue:sum --sort-by revenue_sum --share
$D chart     --id rev --type column \
             --categories "NE,MW,S,W" --series "FY25:14.9,9.8,18.1,13.2"
$D exhibit   --type kpi_row --data '{"kpis":[{"value":"38%","label":"Lift"}]}'
# ... write slide_001.html, slide_002.html, ... into ./mydeck/slides/
$D verify    --slide 1                             # screenshot + overflow check
$D preview   --title "Deck title"
$D open      --serve                               # live, user-editable preview
$D export    --title "Deck title"                  # -> final_outputs/*.pptx
```

## The rules that matter most

1. **Action titles.** Every slide title states the finding, not the topic. A
   reader must follow the whole argument from the titles alone.
2. **Never invent numbers.** Figures come from `profile`/`aggregate` or from the
   user. Missing figures render as `—`, never as a plausible guess.
3. **HTML text, never images.** No `<svg>` carrying words, no generated imagery —
   both rasterise and stop being editable in PowerPoint. Use `chart` and `exhibit`.
4. **Look at every slide.** Run `verify`, then actually read the returned PNG.
   The overflow check catches hard failures; only your eyes catch dead space and
   drift.
5. **Slide files are shared state.** Once the preview is open the user can edit
   the same files. Re-read a slide before editing it.

## Tool mapping

The skill's instructions are written generically. Map them to your runtime:

| Skill says | Use your runtime's |
|---|---|
| run `dax.py ...` | shell / terminal tool |
| read the screenshot at `image_path` | image-capable file read |
| write / edit a slide file | file write and edit tools |
| ask the user for deck parameters | interactive question tool, if available |
| track slide-by-slide progress | todo/task list, if available |

## Layout

```
skills/dax-ppt/
├── SKILL.md              the workflow — read this
├── scripts/dax.py        the only entry point; everything else is its engine
├── references/           design system, charts, exhibits, data, export, editing
└── assets/templates/     live preview, editor, native export, chart renderer
```
