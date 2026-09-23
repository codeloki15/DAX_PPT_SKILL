---
description: Build and open the live, editable browser preview of the deck
argument-hint: [deck title]
---

Open the live preview. Deck title: $ARGUMENTS (if blank: the title already used for this deck)

Follow the `dax-ppt` skill. CLI: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/dax-ppt/scripts/dax.py"`
(or the `scripts/dax.py` next to the skill's SKILL.md). Use this deck's workspace.

1. `preview --title "<title>"` to stitch the slides into the preview page.
2. `open --serve` in the background - the server must stay running to serve the page and save edits.
3. Give the user the URL and tell them: they can edit text, formatting, chart data, speaker notes
   and slide order in the browser, and edits are saved to the slide files.

From here on the slide files are shared state: re-read any slide before editing it. If the JSON
says `"editable": false`, the page opened read-only - say so and why.
