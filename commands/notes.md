---
description: Write presenter speaker notes for every slide, exported into PowerPoint's notes field
argument-hint: [slide number, or blank for all] [tone or length]
---

Write speaker notes. Scope and style: $ARGUMENTS (if blank: all slides, about 60-120 words each)

Follow the `dax-ppt` skill. CLI: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/dax-ppt/scripts/dax.py"`
(or the `scripts/dax.py` next to the skill's SKILL.md). Use this deck's workspace.

For each slide: re-read it, then write notes that a presenter can speak from:
- open with the action title's claim in plain spoken words
- walk the exhibit: what to look at first, and the one number that proves the claim
- end with the bridge to the next slide's title

Only cite numbers that appear on the slide or come from `aggregate`. Save with
`notes --slide N --set "..."` and read back one slide to confirm it saved.
