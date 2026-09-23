---
description: Turn a CSV or Excel file into a data-grounded deck - profile, find the story, propose slides
argument-hint: <path to .csv/.xlsx> [what the deck is for]
---

Build a deck grounded in this data: $ARGUMENTS

Follow the `dax-ppt` skill. CLI: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/dax-ppt/scripts/dax.py"`
(or the `scripts/dax.py` next to the skill's SKILL.md).

1. `profile --file <path>` - report rows, columns, types, nulls and ranges in a short table.
2. Look for the story: run `aggregate` for the obvious cuts (group-bys, top-N, share of total,
   period over period). Every number you mention must come from an `aggregate` result. Remember that
   `--sort-by` takes the OUTPUT column name, e.g. `revenue_sum`.
3. Propose 3-5 findings the data actually supports, each with the aggregate command behind it, and
   note any cut the data cannot support.
4. Turn the findings the user picks into action titles (see `/dax-ppt-skill:outline`) and build the
   slides with `chart` specs fed directly from the aggregate output.

Never round, estimate or transcribe numbers by hand.
