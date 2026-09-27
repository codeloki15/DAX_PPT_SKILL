"""Bundled icon library for DAX slides.

Icons live in assets/icons/ with a manifest (icons.json). The agent never embeds
an icon straight from the library: `use_icon()` writes a copy into the deck
workspace's images/ directory - tinted to a brand token and downsampled - and
returns the <img> snippet to paste. The slide then references `../images/...`,
which is the path the preview inliner and the verify screenshot both resolve.

Styles in the manifest:
    glyph         one ink colour on transparent      -> tinted
    filled        ink plus a white knock-out (badge)  -> tinted, white preserved
    illustration  many colours                        -> copied as-is, never tinted
    logo          the Data Axle wordmark (SVG)        -> copied as-is, sized by height

Icons export to PPTX as pictures. That is acceptable only because they carry no
words - text always stays HTML so it remains editable.
"""

import json
import os
import re
import shutil
from typing import Any, Dict, List, Optional

import paths

ICONS_DIR = os.path.join(paths.SKILL_DIR, "assets", "icons")
MANIFEST = os.path.join(ICONS_DIR, "icons.json")

# Brand tokens an icon may be tinted to. Semantic colours carry state only.
BRAND_COLORS = {
    "navy": "12263F", "brandblue": "00A0DC", "black": "221F20", "slate": "3C4456",
    "muted": "6A7C90", "positive": "1F7A5C", "warning": "B07A16", "negative": "B3341F",
}
DEFAULT_COLOR = "navy"
MIN_SIZE, MAX_SIZE, DEFAULT_SIZE = 12, 96, 24
WHITE_THRESHOLD = 230   # luminance above this is treated as knock-out, not ink

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def load_manifest() -> List[Dict[str, Any]]:
    with open(MANIFEST, "r", encoding="utf-8") as f:
        return json.load(f)["icons"]


def find_icon(name: str) -> Optional[Dict[str, Any]]:
    name = name.strip().lower()
    for icon in load_manifest():
        if icon["name"] == name:
            return icon
    return None


def list_icons(query: Optional[str] = None) -> Dict[str, Any]:
    """List icons, optionally filtered by a term matched against name and tags."""
    icons = load_manifest()
    if query:
        q = query.strip().lower()
        icons = [i for i in icons if q in i["name"] or any(q in t for t in i["tags"])]
    return {
        "status": "ok",
        "count": len(icons),
        "icons": [{"name": i["name"], "style": i["style"], "tintable": i["tintable"],
                   "tags": i["tags"]} for i in icons],
        "usage": "dax.py icon use <name> --size 24 --color navy  -> writes the icon into the "
                 "workspace and returns the <img> snippet. glyph/filled icons are tinted; "
                 "illustration and logo keep their own colours.",
    }


def _resolve_color(value: str) -> Optional[str]:
    key = value.strip().lower().replace("_", "").replace("-", "")
    if key in BRAND_COLORS:
        return BRAND_COLORS[key]
    raw = value.strip().lstrip("#").upper()
    return raw if re.fullmatch(r"[0-9A-F]{6}", raw) else None


def _tint(src: str, dst: str, hex_color: str, px: int) -> None:
    """Recolour ink pixels to hex_color, keep white knock-outs white, keep alpha,
    then downsample to px x px."""
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    im = Image.open(src).convert("RGBA")
    alpha = im.getchannel("A")
    ink_mask = im.convert("L").point(lambda v: 255 if v < WHITE_THRESHOLD else 0)
    ink = Image.new("RGBA", im.size, (r, g, b, 255))
    white = Image.new("RGBA", im.size, (255, 255, 255, 255))
    out = Image.composite(ink, white, ink_mask)
    out.putalpha(alpha)
    out = out.resize((px, px), Image.LANCZOS)
    out.save(dst, "PNG", optimize=True)


def use_icon(name: str, size: int = DEFAULT_SIZE, color: Optional[str] = None) -> Dict[str, Any]:
    """Copy an icon into the workspace images/ dir (tinted if possible) and return
    the <img> snippet to paste into a slide."""
    icon = find_icon(name)
    if icon is None:
        hits = list_icons(name)["icons"][:5]
        return {"error": f"No icon named '{name}'. Try `dax.py icon list --search <term>`.",
                "closest": [h["name"] for h in hits]}

    try:
        size = int(size)
    except (TypeError, ValueError):
        return {"error": "size must be an integer number of CSS pixels"}
    if not MIN_SIZE <= size <= MAX_SIZE:
        return {"error": f"size must be between {MIN_SIZE} and {MAX_SIZE}px; slide icons are "
                         f"normally 20-32px"}

    paths.ensure_directories()
    src = os.path.join(ICONS_DIR, icon["file"])
    style = icon["style"]
    notes = []

    if style == "logo":
        dst_name = icon["file"]
        shutil.copy2(src, os.path.join(paths.IMAGES_DIR, dst_name))
        img = (f'<img src="../images/{dst_name}" alt="Data Axle" '
               f'style="height:{size}px;width:auto;display:block;">')
        if color:
            notes.append("The logo keeps its own brand colours; --color was ignored.")
        return {"status": "created", "name": icon["name"], "style": style,
                "path": os.path.join(paths.IMAGES_DIR, dst_name), "img_html": img,
                "usage": "Place in the footer's left span or on a title slide. Never recolour "
                         "or stretch it.", "notes": notes}

    if style == "illustration":
        dst_name = icon["file"]
        shutil.copy2(src, os.path.join(paths.IMAGES_DIR, dst_name))
        if color:
            notes.append("Illustration icons keep their own colours; --color was ignored. "
                         "Prefer a glyph icon if the slide must stay on the brand palette.")
        notes.append("Off-palette: use only when the user asked for this specific icon.")
        img = (f'<img src="../images/{dst_name}" alt="" '
               f'style="width:{size}px;height:{size}px;display:block;">')
        return {"status": "created", "name": icon["name"], "style": style,
                "path": os.path.join(paths.IMAGES_DIR, dst_name), "img_html": img, "notes": notes}

    # glyph / filled: tint to a brand token
    hex_color = _resolve_color(color or DEFAULT_COLOR)
    if hex_color is None:
        return {"error": f"Unknown color '{color}'. Use a brand token "
                         f"({', '.join(BRAND_COLORS)}) or a 6-digit hex."}
    if not PIL_AVAILABLE:
        return {"error": "Pillow is required to tint icons. Run: pip install pillow"}

    color_key = next((k for k, v in BRAND_COLORS.items() if v == hex_color), hex_color.lower())
    dst_name = f"icon-{icon['name']}-{color_key}-{size}.png"
    dst = os.path.join(paths.IMAGES_DIR, dst_name)
    _tint(src, dst, hex_color, size * 2)   # 2x raster so it stays crisp on export

    if color_key in ("positive", "warning", "negative"):
        notes.append(f"'{color_key}' is a semantic colour - it must signal state, never decorate.")
    img = (f'<img src="../images/{dst_name}" alt="" '
           f'style="width:{size}px;height:{size}px;display:block;flex:0 0 auto;">')
    return {
        "status": "created", "name": icon["name"], "style": style, "color": f"#{hex_color}",
        "size": size, "path": dst, "img_html": img,
        "usage": "Paste img_html next to the text it labels (a KPI value, a process step "
                 "title, an .exh-t caption). One icon per label, 20-32px, never decorative.",
        "notes": notes,
    }
