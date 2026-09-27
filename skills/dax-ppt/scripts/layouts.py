"""Slide layouts: the page frames every slide starts from.

A layout is the house stylesheet (assets/templates/layouts/house.css) plus a body
fragment with {{slot}} markers. `new_slide()` fills the slots it is given, leaves
readable "Replace with ..." text in the rest, and writes slide_NNN.html. The
agent then pastes exhibits into the dashed slot boxes. `verify` reports any
"Replace with" text still on the slide.

Starting every slide from a layout is what keeps a deck consistent: headline,
margins, type sizes and footer are decided once, here, not per slide.
"""

import html
import os
from typing import Any, Dict, Optional

import paths

LAYOUT_DIR = os.path.join(paths.TEMPLATES_DIR, "layouts")

FONT_LINK = ('<link href="https://fonts.googleapis.com/css2?family=Poppins:ital,wght@'
             '0,300;0,400;0,500;0,600;0,700;1,400&display=swap" rel="stylesheet"/>')

LAYOUTS = {
    "narrative":  ("narrative.html",  "Thesis, up to 3 iconed points and a takeaway on the left; one exhibit panel on the right. The default content slide."),
    "exhibit":    ("exhibit.html",    "Thesis, one full-width exhibit (a large chart or table), takeaway. For data-led slides."),
    "comparison": ("comparison.html", "Thesis, two exhibit panels side by side, takeaway. For A vs B, before/after, two segments."),
    "title":      ("title.html",      "Deck cover: title, subtitle, date."),
    "section":    ("section.html",    "Section divider: number, section title, one line of framing."),
    "blank":      ("blank.html",      "Headline and footer only. Use only when no layout above fits."),
}

PLACEHOLDER = "Replace with"   # verify flags any text containing this

DEFAULTS = {
    "kicker": "Replace with a section label",
    "title": "Replace with the finding this slide proves, in 16 words or fewer",
    "lead": "Replace with one sentence of context, 25 words or fewer",
    "panel_title": "Replace with the exhibit title",
    "panel_subtitle": "",
    "left_title": "Replace with the left panel title",
    "right_title": "Replace with the right panel title",
    "subtitle": "Replace with the subtitle or audience",
    "source": "Replace with the source of every figure on this slide",
    "exhibit_label": "Replace with: Exhibit N | what the exhibit shows",
    "deck": "Replace with the deck title",
    "date": "",
    "stamp": "Confidential",
    "number": "01",
    "page": "",
}


def list_layouts() -> Dict[str, Any]:
    return {"status": "ok",
            "layouts": [{"name": k, "use_for": v[1]} for k, v in LAYOUTS.items()],
            "usage": "dax.py slide new --slide N --layout narrative --kicker ... --title ... "
                     "--lead ... --source ... --deck ..."}


def render(layout: str, slots: Optional[Dict[str, str]] = None, page: str = "") -> str:
    """Full standalone slide HTML for `layout`, with `slots` filled in."""
    fname = LAYOUTS[layout][0]
    with open(os.path.join(LAYOUT_DIR, "house.css"), "r", encoding="utf-8") as f:
        css = f.read()
    with open(os.path.join(LAYOUT_DIR, fname), "r", encoding="utf-8") as f:
        body = f.read()
    values = dict(DEFAULTS, page=page)
    for k, v in (slots or {}).items():
        if v is not None:
            values[k] = v
    for k, v in values.items():
        body = body.replace("{{" + k + "}}", html.escape(str(v), quote=False))
    title_text = values.get("title") or layout
    return ("<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"/>\n"
            "<meta content=\"width=device-width, initial-scale=1.0\" name=\"viewport\"/>\n"
            f"<title>{html.escape(title_text)}</title>\n{FONT_LINK}\n<style>\n{css}</style></head><body>\n"
            f"{body}</body></html>\n")


def new_slide(slide_number: int, layout: str, slots: Optional[Dict[str, str]] = None,
              force: bool = False) -> Dict[str, Any]:
    if layout not in LAYOUTS:
        return {"error": f"Unknown layout '{layout}'. Valid: {', '.join(LAYOUTS)}"}
    paths.ensure_directories()
    path = os.path.join(paths.SLIDES_DIR, f"slide_{slide_number:03d}.html")
    if os.path.exists(path) and not force:
        return {"error": f"{os.path.basename(path)} already exists. Pass --force to replace it, "
                         "or edit the existing file."}
    doc = render(layout, slots, page=str(slide_number))
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    remaining = sorted({k for k in DEFAULTS if DEFAULTS[k].startswith(PLACEHOLDER)
                        and "{{" + k + "}}" in open(os.path.join(LAYOUT_DIR, LAYOUTS[layout][0])).read()
                        and not (slots or {}).get(k)})
    return {
        "status": "created", "slide_number": slide_number, "layout": layout, "path": path,
        "unfilled_text_slots": remaining,
        "next_step": ("Open the file and replace each dashed .slot box with the exhibit HTML it names "
                      "(points, takeaway, chart embed, scorecard or table), and any remaining "
                      "'Replace with' text. Then run verify."),
    }
