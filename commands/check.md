---
description: Quality-check every slide - render and look at each one, and audit it against the brand rules
argument-hint: [slide number, or blank for all]
---

Quality-check the deck. Scope: $ARGUMENTS (if blank: all slides)

Follow the `dax-ppt` skill. CLI: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/dax-ppt/scripts/dax.py"`
(or the `scripts/dax.py` next to the skill's SKILL.md). Use this deck's workspace.

For each slide (`list` gives them all):
1. `verify --slide N`. Record every issue (overflow, unfilled slots) and every warning (over 170
   body words, text under 12px, text under 10px, low contrast). Then look at the screenshot: dead
   space, cramped panels, and styling that drifts from the other slides.
2. Read the HTML and audit it:
   - the title is a finding, not a topic label
   - the slide was built from a house layout: kicker, 2px navy rule, source line and footer present
   - one thesis line, at most three points, one exhibit panel, one takeaway - no outlined text boxes
   - only brand tokens are used; semantic green/amber/red mark state only
   - no icon fonts, emoji, gradients or shadows; any icon is from the bundled library
     (`../images/icon-*.png` or the logo), 20-32px, brand-tinted, and labels something
   - no `<svg>` carrying text (it rasterises on export)
   - every number traces to user input or an `aggregate` result; unknowns are an em-dash
   - charts are `.chart-embed` placeholders inside a panel with real height; tables have `<thead>` and `<tbody>`

Finally read only the titles in order and say whether they make one argument.

Report a table: slide, issue, fix. Then fix everything, re-verify, and re-report until it is clean.
