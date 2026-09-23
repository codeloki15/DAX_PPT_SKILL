"""DAX_PPT_SKILL - Hermes Agent plugin.

Registers the shared skill core (skills/dax-ppt/SKILL.md) with Hermes. Hermes
loads this directory as the plugin, so the skill sits one level up.
"""

from pathlib import Path


def register(ctx):
    here = Path(__file__).resolve().parent
    for cand in (here.parent / "skills" / "dax-ppt" / "SKILL.md",
                 here / "skills" / "dax-ppt" / "SKILL.md"):
        if cand.is_file():
            ctx.register_skill("dax-ppt", cand)
            return
    raise RuntimeError(
        "dax-ppt-skill: skills/dax-ppt/SKILL.md not found; reinstall with "
        "`hermes plugins install codeloki15/DAX_PPT_SKILL`"
    )
