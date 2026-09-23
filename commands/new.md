---
description: Start a new Data Axle deck end to end - brief, storyline, slides, verification, preview
argument-hint: <topic, audience, slide count, data file - any you know>
---

Build a new Data Axle presentation. Brief from the user: $ARGUMENTS

Follow the `dax-ppt` skill exactly (load it now if it is not already loaded). The CLI is
`python3 "${CLAUDE_PLUGIN_ROOT}/skills/dax-ppt/scripts/dax.py"`; if that path does not exist,
use the `scripts/dax.py` that sits next to the skill's SKILL.md.

1. Pin down topic, the argument the deck must make, audience, slide count and data source.
   Infer what you can from the brief; ask only for what is genuinely missing.
2. Pick one workspace for this deck (default `./dax_workspace`) and pass `--workspace` on every call.
3. If there is a data file, `profile` it and `aggregate` every figure you will show. Never invent numbers.
4. Write the action titles first as a numbered list and get the user's agreement before building.
5. Build each slide from the skeleton in references/design_system.md, using `chart` and `exhibit`
   instead of hand-drawn geometry.
6. `verify` every slide and actually look at each screenshot. Fix and re-verify until clean.
7. `preview`, then `open --serve` in the background, and tell the user the preview is editable.

Stop after the preview. Export only when the user asks (`/dax-ppt-skill:export`).
