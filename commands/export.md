---
description: Export the deck to PPTX with editable text, native charts, native tables and speaker notes
argument-hint: [deck title] [--output path.pptx]
---

Export the deck to PowerPoint. Arguments: $ARGUMENTS

Follow the `dax-ppt` skill. CLI: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/dax-ppt/scripts/dax.py"`
(or the `scripts/dax.py` next to the skill's SKILL.md). Use this deck's workspace.

1. Re-read the slides - the user may have edited them in the preview - and `verify` any slide that
   changed since it was last verified.
2. `preview --title "<title>"` so the export includes the latest edits.
3. `export --title "<title>"` (add `--output` if the user gave a path). Export needs network access
   for its pinned CDN bundles.
4. Check the result: `native_charts.inserted` must list every chart id you created,
   `native_tables.inserted` must match the number of tables, and `speaker_notes.written` the number
   of slides with notes. A shortfall means a chart or table exported as a flat picture - find it,
   fix the slide, and export again (see references/export.md).

Report the file path, the slide count and the native chart, table and notes counts.
