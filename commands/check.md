---
description: Quality-check every slide - render and look at each one, and audit it against the brand rules
argument-hint: [slide number, or blank for all]
---

Quality-check the deck. Scope: $ARGUMENTS (if blank: all slides)

Follow the `dax-ppt` skill. CLI: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/dax-ppt/scripts/dax.py"`
(or the `scripts/dax.py` next to the skill's SKILL.md). Use this deck's workspace.

For each slide (`list` gives them all):
1. `verify --slide N`, then look at the screenshot. Record overflow, dead space above the footer,
   cramped or stranded exhibits, and styling that drifts from the other slides.
2. Read the HTML and audit it:
   - the title is a finding, not a topic label
   - kicker, 2px navy rule and footer are present
   - only brand tokens are used; semantic green/amber/red mark state only
   - no icons, emoji, gradients, shadows, and no `<svg>` carrying text (it rasterises on export)
   - every number traces to user input or an `aggregate` result; unknowns are an em-dash
   - charts are `.chart-embed` placeholders inside a panel with real height; tables have `<thead>` and `<tbody>`

Finally read only the titles in order and say whether they make one argument.

Report a table: slide, issue, fix. Then fix everything, re-verify, and re-report until it is clean.
