---
description: Install and verify the skill's dependencies (Python packages, Chromium) with dax.py doctor
---

Set up the DAX PPT skill on this machine.

CLI: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/dax-ppt/scripts/dax.py"` (or the `scripts/dax.py` next
to the dax-ppt skill's SKILL.md).

1. Run `doctor`. If it reports `"status": "ok"`, say so and stop.
2. Otherwise show the user the missing pieces and the install commands:
   `pip install playwright python-pptx pandas openpyxl` and `playwright install chromium`.
   Ask before installing anything, then run them.
3. Run `doctor` again and report the result. If anything still fails, report its `fix` field
   verbatim.
