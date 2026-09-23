"""Shared directory layout for a DAX deck workspace.

Every module resolves paths from here so the workspace stays consistent
regardless of the current working directory.

In the original agent this was fixed at import time. In the skill the host
agent drives several decks from one checkout, so the workspace is resolved in
this precedence order:

    1. set_workspace(path)      - explicit, set by every CLI entry point
    2. $DAX_PPT_WORKSPACE       - environment override
    3. $PPT_AGENT_WORKSPACE     - legacy name, kept for compatibility
    4. ./dax_workspace          - default, relative to the current directory

Because the engine modules (charts.py, verify.py, edit_server.py) read
CHARTS_DIR / SLIDES_DIR at call time rather than import time, set_workspace()
must be called before any of them run. `dax.py` does this for you.
"""

import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
TEMPLATES_DIR = os.path.join(SKILL_DIR, "assets", "templates")


def _default_workspace() -> str:
    env = os.environ.get("DAX_PPT_WORKSPACE") or os.environ.get("PPT_AGENT_WORKSPACE")
    if env:
        return os.path.abspath(env)
    return os.path.abspath(os.path.join(os.getcwd(), "dax_workspace"))


# Module-level names kept for compatibility with the original engine modules,
# which do `from paths import SLIDES_DIR`. set_workspace() rebinds them.
WORKSPACE_DIR = _default_workspace()
SLIDES_DIR = os.path.join(WORKSPACE_DIR, "slides")
IMAGES_DIR = os.path.join(WORKSPACE_DIR, "images")
CHARTS_DIR = os.path.join(WORKSPACE_DIR, "charts")
SCREENSHOTS_DIR = os.path.join(WORKSPACE_DIR, "screenshots")
FINAL_OUTPUTS_DIR = os.path.join(WORKSPACE_DIR, "final_outputs")

# Directories wiped by a reset (FINAL_OUTPUTS_DIR is deliberately kept).
RESETTABLE_DIRS = [SLIDES_DIR, IMAGES_DIR, CHARTS_DIR, SCREENSHOTS_DIR]


def set_workspace(path: str) -> str:
    """Point every workspace path at `path` and create the directories.

    Rebinds this module's globals AND pushes the new values into any engine
    module that already did `from paths import SLIDES_DIR`, so ordering of
    imports never silently leaves a module pointing at the old workspace.
    """
    global WORKSPACE_DIR, SLIDES_DIR, IMAGES_DIR, CHARTS_DIR
    global SCREENSHOTS_DIR, FINAL_OUTPUTS_DIR, RESETTABLE_DIRS

    WORKSPACE_DIR = os.path.abspath(path)
    SLIDES_DIR = os.path.join(WORKSPACE_DIR, "slides")
    IMAGES_DIR = os.path.join(WORKSPACE_DIR, "images")
    CHARTS_DIR = os.path.join(WORKSPACE_DIR, "charts")
    SCREENSHOTS_DIR = os.path.join(WORKSPACE_DIR, "screenshots")
    FINAL_OUTPUTS_DIR = os.path.join(WORKSPACE_DIR, "final_outputs")
    RESETTABLE_DIRS = [SLIDES_DIR, IMAGES_DIR, CHARTS_DIR, SCREENSHOTS_DIR]

    # Keep already-imported engine modules in sync. They bound these names at
    # import time via `from paths import ...`, so rebinding our own globals is
    # not enough on its own.
    import sys
    _names = ("WORKSPACE_DIR", "SLIDES_DIR", "IMAGES_DIR", "CHARTS_DIR",
              "SCREENSHOTS_DIR", "FINAL_OUTPUTS_DIR", "RESETTABLE_DIRS")
    for mod_name in ("charts", "verify", "edit_server", "deck", "data_tools"):
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        for name in _names:
            if hasattr(mod, name):
                setattr(mod, name, globals()[name])

    ensure_directories()
    return WORKSPACE_DIR


def ensure_directories() -> None:
    """Create all workspace directories."""
    for dir_path in [WORKSPACE_DIR, SLIDES_DIR, IMAGES_DIR, CHARTS_DIR,
                     SCREENSHOTS_DIR, FINAL_OUTPUTS_DIR]:
        os.makedirs(dir_path, exist_ok=True)
