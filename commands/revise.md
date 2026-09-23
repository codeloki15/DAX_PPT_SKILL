---
description: Revise one slide with an instruction - re-reads it first, since browser edits may have changed it
argument-hint: <slide number> <what to change>
---

Revise a slide. Request: $ARGUMENTS
The first token is the slide number; the rest is the instruction.

Follow the `dax-ppt` skill. CLI: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/dax-ppt/scripts/dax.py"`
(or the `scripts/dax.py` next to the skill's SKILL.md). Use the workspace already in use for this
deck; if unsure, run `list` against `./dax_workspace`.

1. Re-read `slides/slide_NNN.html` from disk now. The user may have edited it in the live preview;
   never work from an earlier copy.
2. Make the change with a targeted edit. Keep the design system: action title, kicker, navy rule,
   footer, brand tokens only, no SVG text, no invented numbers. New data goes through `aggregate`
   and `chart`, not hand-typed values.
3. `verify --slide N` and look at the screenshot. Fix and re-verify until clean.
4. Rebuild with `preview --title "<deck title>"` so an open browser picks it up on refresh.

Report what changed in one or two lines.
