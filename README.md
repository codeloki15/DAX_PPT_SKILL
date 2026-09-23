# DAX_PPT_SKILL

An agent skill that builds **Data Axle presentations** — consulting-grade
1280x720 slides in the house style, exported to PowerPoint with **editable text,
native charts and native tables**.

It installs into Claude Code, OpenAI Codex, Cursor, Devin, Hermes, Kimi, Muse,
opencode, Pi and Gemini from this one repository.

---

## What it does

You describe the deck; the agent builds it. Under the hood:

| Capability | How |
|---|---|
| **House style** | Every slide is 1280x720 HTML on white, Poppins throughout, locked to the Data Axle palette with brandBlue `#00A0DC` as the single accent. |
| **Action titles** | Every title states the finding, not the topic — read the titles in order and you have the argument. |
| **Native charts** | `dax.py chart` stores a structured spec. It renders live with Chart.js in the preview and becomes a **real PowerPoint chart** on export — recipients can right-click → *Edit Data*. 9 types including waterfall. |
| **Native tables** | Plain `<table>` markup is rebuilt as a real PowerPoint table, so every cell stays editable text instead of a flattened picture. |
| **Real numbers** | `dax.py profile` / `aggregate` read CSV and Excel with pandas. Every figure traces back to a file; the agent never does arithmetic in its head. |
| **Exhibit library** | `dax.py exhibit` builds timelines, process flows, funnels, 2×2 matrices, harvey-ball tables and KPI rows — brand-styled, div-only, fully editable after export. |
| **Visual verification** | `dax.py verify` renders each slide headlessly, flags overflow programmatically, and hands the agent a screenshot to actually look at. |
| **Live editing** | The preview is served from `127.0.0.1`, so the user can edit text, formatting, chart data, notes and slide order in the browser — and those edits are written back to the same slide files. |

No API keys. The host agent is the loop; this package is the deterministic
engine it drives.

---

## Install

Clone the repo, then install the Python dependencies:

```bash
pip install -r requirements.txt
playwright install chromium
python3 skills/dax-ppt/scripts/dax.py doctor
```

`doctor` checks every dependency — including a real Chromium launch — and names
the fix for anything missing.

### Per host

| Host | How it finds the skill |
|---|---|
| **Claude Code** | `/plugin marketplace add .` then install `dax-ppt-skill`, or copy `skills/dax-ppt/` into `~/.claude/skills/`. `CLAUDE.md` also points at it. |
| **OpenAI Codex** | Reads `AGENTS.md` at the repo root. `.codex-plugin/plugin.json` declares `skills: ./skills/`. |
| **Cursor / Devin / Kimi / Muse / Hermes** | Each has its manifest in the matching `.<host>-plugin/` directory, all pointing at the same `skills/` tree. |
| **opencode** | `.opencode/plugins/dax-ppt-skill.js` |
| **Pi** | `package.json` → `pi.extensions` + `pi.skills` |
| **Gemini** | `gemini-extension.json` → `GEMINI.md` |
| **Anything else** | Point it at `AGENTS.md`. |

Every host reads the **same** `skills/dax-ppt/` core — the manifests are thin
pointers, so there are no copies to keep in sync.

---

## Use it

Just ask, in whatever host you installed it into:

> Build me a 10-slide deck on Q3 regional performance for the board, using
> `sales.csv`.

The agent profiles the data, drafts action titles for your approval, builds and
verifies each slide, opens the live preview for you to edit, and exports the
`.pptx`.

### Driving the CLI directly

```bash
D="python3 skills/dax-ppt/scripts/dax.py --workspace ./mydeck"

$D profile   --file sales.csv
$D aggregate --file sales.csv --group-by region --agg revenue:sum --share
$D chart     --id rev --type column --categories "NE,MW,S,W" \
             --series "FY25:14.9,9.8,18.1,13.2"
$D verify    --slide 1
$D preview   --title "Q3 regional performance"
$D open      --serve
$D export    --title "Q3 regional performance"
```

Every command prints one JSON object and exits non-zero on error.
`--workspace` keeps concurrent decks from overwriting each other.

---

## Layout

```
skills/dax-ppt/
├── SKILL.md                  the workflow the agent follows
├── scripts/
│   ├── dax.py                the only entry point
│   ├── deck.py               preview assembly + PPTX export
│   ├── charts.py             chart specs + native PPTX charts/tables/notes
│   ├── exhibits.py           the brand-styled exhibit library
│   ├── data_tools.py         CSV/Excel profiling and aggregation
│   ├── verify.py             headless screenshots + overflow detection
│   ├── edit_server.py        local server backing the editable preview
│   └── paths.py              workspace layout
├── references/               design system, charts, exhibits, data, export, editing
└── assets/templates/         live preview, editor, native export, chart renderer
```

### Export pipeline

Slides are standalone HTML → the preview stitches them together → Playwright
records where every chart and table sits *as a fraction of its slide* and removes
those nodes → the in-page `dom-to-pptx` export turns the remaining HTML into
editable PowerPoint text → `python-pptx` inserts native charts and tables at
exactly those positions and writes the speaker notes.

Removing the placeholder rather than hiding it is deliberate: a hidden element
still occupies layout, which makes the exporter rasterise the surrounding panel
and drop a blank picture over the native chart.

**Export requires network access** — the export page loads pinned CDN bundles
(`pptxgenjs@4.0.1`, `jszip@3.10.1`, `dom-to-pptx@2.1.1`, `chart.js@4.5.1`).

---

## Credits

Ported from the `PPT_Maker` agent into a runtime-neutral skill. The multi-host
plugin layout follows the pattern established by
[obra/superpowers](https://github.com/obra/superpowers).
