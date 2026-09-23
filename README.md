# DAX_PPT_SKILL

An agent skill that builds **Data Axle presentations** — consulting-grade
1280x720 slides in the house style, exported to PowerPoint with **editable text,
native charts and native tables**.

It installs into Claude Code, OpenAI Codex, Cursor, Devin, Hermes, Kimi, Muse,
opencode, Pi, Gemini and Kiro from this one repository.

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

| Host | Manifest | Install |
|---|---|---|
| **Claude Code** | `.claude-plugin/` | `/plugin` → Marketplaces → add `https://github.com/codeloki15/DAX_PPT_SKILL`, then install `dax-ppt-skill` |
| **OpenAI Codex** | `.codex-plugin/`, `.agents/plugins/marketplace.json`, `AGENTS.md` | Add this repo as a Codex plugin marketplace, then install `dax-ppt-skill` |
| **Cursor** | `.cursor-plugin/` | No install-from-URL for individuals. Submit at cursor.com/marketplace/publish, import as a team marketplace (Teams/Enterprise), or copy the repo into `~/.cursor/plugins/local/dax-ppt-skill` and reload the window (copy, don't symlink) |
| **Kiro** | `plugin.json` (Agent Plugins format) | Powers panel → Add Custom Power → Import power from GitHub → this repo URL. Or copy `skills/dax-ppt` into `~/.kiro/skills/` |
| **Gemini CLI** | `gemini-extension.json` | `gemini extensions install https://github.com/codeloki15/DAX_PPT_SKILL` (skills load natively from `skills/`) |
| **opencode** | `.opencode/plugins/dax-ppt-skill.js` | Load the plugin, or copy `skills/dax-ppt` into `~/.config/opencode/skills/`. It also reads `~/.claude/skills/` |
| **Pi** | `package.json` → `pi.skills` | Install the repo as a Pi package |
| **Hermes** | `.hermes-plugin/` | `hermes plugins install codeloki15/DAX_PPT_SKILL`, then add `dax-ppt-skill` to `plugins.enabled` in `~/.hermes/config.yaml` |
| **Devin** | `.devin-plugin/` | Install the repo as a Devin plugin |
| **Kimi Code** | `.kimi-plugin/` | Install the repo as a Kimi plugin |
| **Muse** | `.muse-plugin/` | Add the repo as a Muse marketplace (Muse has no public spec; mirrors superpowers) |
| **Anything else** | `AGENTS.md` | Point the agent at `AGENTS.md` |

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

### Slash commands

Installed as a plugin, the skill adds commands for each stage of building a
deck. In Claude Code they are namespaced `/dax-ppt-skill:<command>`; Cursor
picks them up from `commands/` too. In agents without slash commands, just ask
for the same thing in plain words.

| Command | What it does | Why it matters |
|---|---|---|
| `/dax-ppt-skill:dax-ppt` | Loads the skill itself: the full workflow and brand rules | The base layer. Every command below builds on it; the agent also loads it on its own when you mention a deck |
| `/dax-ppt-skill:new <brief>` | Runs the whole build: brief → storyline → slides → verification → live preview | One command from idea to an editable preview, with every quality gate applied in order |
| `/dax-ppt-skill:outline <topic>` | Drafts the action titles only, for your sign-off | **The cheapest place to fix a deck.** The titles are the argument; agreeing on them first means no slides get rebuilt because the story was wrong |
| `/dax-ppt-skill:from-data <file.csv>` | Profiles a CSV/Excel file, finds what the data supports, proposes slides | Enforces **never invent numbers**: every figure comes from a pandas `aggregate` result, so the deck is safe to put in front of a client or board |
| `/dax-ppt-skill:revise <n> <change>` | Re-reads slide *n* from disk, edits it, re-verifies it | Browser edits and agent edits touch the same files. Re-reading first means your manual fixes are never overwritten. The preview's *Regenerate* button copies this command for you |
| `/dax-ppt-skill:check [n]` | Renders and **looks at** every slide, then audits it against the brand rules | Catches what reviewers catch: overflow, dead space, topic-label titles, off-brand colours, and text inside SVG, which would turn into an uneditable picture |
| `/dax-ppt-skill:preview [title]` | Builds and serves the live editable preview | Lets you edit text, chart data, notes and slide order in the browser, and saves those edits to the slide files |
| `/dax-ppt-skill:notes [n] [style]` | Writes speaker notes for every slide | Notes go into PowerPoint's real notes field, so the deck is ready to present, not just to read |
| `/dax-ppt-skill:export [title]` | Exports the `.pptx` and **checks** the native chart, table and notes counts | Proves the output is editable: a missing chart count means something exported as a flat picture, and the command fixes it before you ship |
| `/dax-ppt-skill:setup` | Installs dependencies and runs `dax.py doctor` | Turns "export failed" into a named, fixable problem before you start |

A typical session:

```
/dax-ppt-skill:setup
/dax-ppt-skill:from-data q3_sales.csv  board update on regional performance
/dax-ppt-skill:outline                  (approve or edit the titles)
/dax-ppt-skill:new                      (build, verify, open preview)
/dax-ppt-skill:revise 4 lead with the churn number, drop the table
/dax-ppt-skill:check
/dax-ppt-skill:notes
/dax-ppt-skill:export
```

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
commands/                     slash commands: new, outline, from-data, revise,
                              check, preview, notes, export, setup
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
