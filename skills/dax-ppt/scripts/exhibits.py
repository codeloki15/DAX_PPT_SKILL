"""Parameterized exhibit library - brand-compliant infographic components.

Each builder returns a self-contained block of inline-styled divs (never SVG,
never images) so the PPTX export keeps every word as editable text. The agent
fills these with content instead of hand-coding layout, which keeps exhibits
pixel-consistent across the deck.

Brand tokens (Data Axle): brandBlue #00A0DC, navy #12263F, black #221F20,
slate #3C4456, muted #5F6F82, rule #D4D9E0, light #F4F6F8,
positive #1F7A5C, warning #B07A16, negative #B3341F.

Text colours must pass 4.5:1 on white, so small text never uses brandBlue
(2.97:1) or the warning amber (3.72:1): it uses BLUE_TEXT and STATE_TEXT.
"""

import html
import re
from typing import Dict, Any, List, Tuple, Union

BRAND_BLUE = "#00A0DC"
NAVY = "#12263F"
BLACK = "#221F20"
SLATE = "#3C4456"
MUTED = "#5F6F82"      # 5.1:1 on white; the old #6A7C90 was 4.29:1
BLUE_TEXT = "#007BAD"  # brand blue for small text, 4.7:1 on white
RULE = "#D4D9E0"
LIGHT = "#F4F6F8"
STATE_COLORS = {"positive": "#1F7A5C", "warning": "#B07A16", "negative": "#B3341F"}   # fills, dots
STATE_TEXT = {"positive": "#1F7A5C", "warning": "#8F6212", "negative": "#B3341F", "neutral": "#3C4456"}
PANEL_TINT = "#EAF6FB"   # takeaway fill: a light tint of brandBlue

EXHIBIT_TYPES = ["points", "takeaway", "scorecard", "timeline", "process_flow", "funnel",
                 "matrix_2x2", "harvey_table", "kpi_row"]

# Word budgets. Above SOFT the builder warns; above HARD it refuses - a slide is not a memo.
BUDGETS = {"point": (28, 45), "takeaway": (35, 55), "point_title": (6, 10)}


def _esc(text: Any) -> str:
    return html.escape(str(text)) if text is not None else ""


def _rich(text: Any) -> str:
    """Escape, then allow **bold** for the one phrase a reader should catch."""
    return re.sub(r"\*\*(.+?)\*\*", rf'<b style="color:{BLACK};font-weight:600;">\1</b>', _esc(text))


def _words(text: Any) -> int:
    return len(re.sub(r"\*\*", "", str(text or "")).split())


def _budget(kind: str, text: Any, where: str, warnings: List[str]) -> None:
    soft, hard = BUDGETS[kind]
    n = _words(text)
    if n > hard:
        raise ValueError(f"{where} is {n} words; the limit is {hard} (aim for {soft}). Cut it - "
                         "the slide carries the claim, the speaker notes carry the detail.")
    if n > soft:
        warnings.append(f"{where} is {n} words; aim for {soft} or fewer.")


# =============================================================================
# Builders
# =============================================================================

def _build_timeline(data: Dict[str, Any]) -> str:
    """data: {items: [{label, title, description?}]} - horizontal milestone timeline."""
    items = data.get("items") or []
    if not 2 <= len(items) <= 7:
        raise ValueError("timeline needs 2-7 items: [{label, title, description?}]")

    cells = []
    for it in items:
        desc = (f'<div style="font-size:12px;line-height:1.45;color:{SLATE};margin-top:4px;">'
                f'{_esc(it.get("description"))}</div>') if it.get("description") else ""
        cells.append(f'''<div style="flex:1;min-width:0;padding:0 8px;">
  <div style="font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:{BLUE_TEXT};font-weight:700;margin-bottom:6px;">{_esc(it.get("label"))}</div>
  <div style="width:10px;height:10px;background:{BRAND_BLUE};border-radius:50%;margin-bottom:10px;position:relative;z-index:1;"></div>
  <div style="font-size:13px;font-weight:600;color:{NAVY};line-height:1.35;">{_esc(it.get("title"))}</div>
  {desc}
</div>''')

    return f'''<div style="position:relative;padding-top:2px;">
  <div style="position:absolute;left:12px;right:12px;top:29px;height:2px;background:{RULE};"></div>
  <div style="display:flex;">{"".join(cells)}</div>
</div>'''


def _build_process_flow(data: Dict[str, Any]) -> str:
    """data: {steps: [{title, description?}], emphasize?: [indices]} - boxed steps with arrows."""
    steps = data.get("steps") or []
    if not 2 <= len(steps) <= 6:
        raise ValueError("process_flow needs 2-6 steps: [{title, description?}]")
    emphasize = set(data.get("emphasize") or [])

    parts = []
    for i, step in enumerate(steps):
        if i:
            parts.append(f'<div style="flex:0 0 auto;align-self:center;color:{MUTED};'
                         f'font-size:18px;padding:0 8px;">&#8594;</div>')
        border = f"1.5px solid {BRAND_BLUE}" if i in emphasize else "1px solid #E1E6EC"
        desc = (f'<div style="font-size:12.5px;line-height:1.5;color:{SLATE};padding:12px 14px 14px;">'
                f'{_esc(step.get("description"))}</div>') if step.get("description") else ""
        parts.append(f'''<div style="flex:1;min-width:0;border:{border};background:#fff;">
  <div style="background:{NAVY};color:#fff;font-size:13px;font-weight:600;padding:9px 14px;">
    <span style="color:{BRAND_BLUE};font-weight:700;margin-right:6px;">{i + 1}</span>{_esc(step.get("title"))}
  </div>
  {desc}
</div>''')

    return f'<div style="display:flex;align-items:stretch;">{"".join(parts)}</div>'


def _build_funnel(data: Dict[str, Any]) -> str:
    """data: {stages: [{label, value?}]} - centered funnel with narrowing bars."""
    stages = data.get("stages") or []
    if not 2 <= len(stages) <= 6:
        raise ValueError("funnel needs 2-6 stages: [{label, value?}]")

    n = len(stages)
    rows = []
    for i, stage in enumerate(stages):
        width = 100 - (i * (55 / max(n - 1, 1)))  # 100% narrowing to 45%
        # Last stage gets the accent; earlier stages step through navy tints.
        bg = BRAND_BLUE if i == n - 1 else NAVY
        opacity = 1 if i == n - 1 else round(0.45 + 0.55 * (i + 1) / n, 2)
        value = (f'<span style="font-weight:700;margin-left:10px;">{_esc(stage.get("value"))}</span>'
                 if stage.get("value") is not None else "")
        rows.append(f'''<div style="display:flex;justify-content:center;">
  <div style="width:{width:.0f}%;background:{bg};opacity:{opacity};color:#fff;font-size:12.5px;
    padding:8px 14px;margin-bottom:5px;display:flex;justify-content:space-between;align-items:center;">
    <span>{_esc(stage.get("label"))}</span>{value}
  </div>
</div>''')
    return f'<div>{"".join(rows)}</div>'


def _build_matrix_2x2(data: Dict[str, Any]) -> str:
    """data: {x_axis: {low, high}, y_axis: {low, high}, quadrants: [TL, TR, BL, BR
    as {title, items?: [..]}], highlight?: index} - classic 2x2."""
    quads = data.get("quadrants") or []
    if len(quads) != 4:
        raise ValueError("matrix_2x2 needs exactly 4 quadrants (TL, TR, BL, BR): [{title, items?}]")
    x_axis = data.get("x_axis") or {}
    y_axis = data.get("y_axis") or {}
    highlight = data.get("highlight")

    cells = []
    for i, q in enumerate(quads):
        border = f"1.5px solid {BRAND_BLUE}" if i == highlight else f"1px solid {RULE}"
        bg = "#fff" if i == highlight else LIGHT
        items = "".join(
            f'<li style="padding-left:13px;position:relative;margin-bottom:4px;font-size:12px;'
            f'line-height:1.4;color:{SLATE};">'
            f'<span style="position:absolute;left:0;top:5px;width:5px;height:5px;background:{BRAND_BLUE};"></span>'
            f'{_esc(item)}</li>'
            for item in (q.get("items") or [])
        )
        item_list = f'<ul style="list-style:none;padding:0;margin:6px 0 0;">{items}</ul>' if items else ""
        cells.append(f'''<div style="border:{border};background:{bg};padding:10px 12px;min-height:0;overflow:hidden;">
  <div style="font-size:13px;font-weight:600;color:{NAVY};">{_esc(q.get("title"))}</div>
  {item_list}
</div>''')

    axis_label = f"font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:{MUTED};font-weight:700;"
    return f'''<div style="display:flex;height:100%;min-height:0;">
  <div style="display:flex;flex-direction:column;justify-content:space-between;align-items:flex-end;padding:0 8px 22px 0;">
    <div style="{axis_label}">{_esc(y_axis.get("high", "High"))}</div>
    <div style="{axis_label}">{_esc(y_axis.get("low", "Low"))}</div>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;min-width:0;">
    <div style="flex:1;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:6px;min-height:0;">
      {"".join(cells)}
    </div>
    <div style="display:flex;justify-content:space-between;padding:6px 2px 0;">
      <div style="{axis_label}">{_esc(x_axis.get("low", "Low"))}</div>
      <div style="{axis_label}">{_esc(x_axis.get("high", "High"))}</div>
    </div>
  </div>
</div>'''


def _build_harvey_table(data: Dict[str, Any]) -> str:
    """data: {columns: [..], rows: [{label, scores: [0-4 per column]}]} -
    comparison table with harvey-ball glyphs (0=empty .. 4=full)."""
    columns = data.get("columns") or []
    rows = data.get("rows") or []
    if not columns or not rows:
        raise ValueError("harvey_table needs columns: [..] and rows: [{label, scores: [0-4, ..]}]")

    glyphs = {0: "○", 1: "◔", 2: "◑", 3: "◕", 4: "●"}  # ○◔◑◕●
    th = (f'text-align:center;font-size:10px;letter-spacing:.09em;text-transform:uppercase;'
          f'color:{MUTED};font-weight:700;padding:7px 10px;border-bottom:1.5px solid {NAVY};')
    header = f'<th style="{th}text-align:left;"></th>' + "".join(
        f'<th style="{th}">{_esc(c)}</th>' for c in columns)

    body_rows = []
    for r in rows:
        scores = r.get("scores") or []
        if len(scores) != len(columns):
            raise ValueError(f"row '{r.get('label')}' has {len(scores)} scores for {len(columns)} columns")
        cells = "".join(
            f'<td style="text-align:center;padding:7px 10px;border-bottom:1px solid {RULE};'
            f'font-size:15px;color:{BRAND_BLUE};line-height:1;">'
            f'{glyphs.get(int(s), glyphs[0])}</td>'
            for s in scores
        )
        body_rows.append(
            f'<tr><td style="padding:7px 10px;border-bottom:1px solid {RULE};font-size:12.5px;'
            f'color:{BLACK};font-weight:600;">{_esc(r.get("label"))}</td>{cells}</tr>')

    legend = (f'<div style="font-size:10px;color:{MUTED};margin-top:7px;">'
              f'<span style="color:{BRAND_BLUE};">●</span> Full &nbsp;'
              f'<span style="color:{BRAND_BLUE};">◑</span> Partial &nbsp;'
              f'<span style="color:{BRAND_BLUE};">○</span> None</div>')
    return (f'<table style="width:100%;border-collapse:collapse;"><thead><tr>{header}</tr></thead>'
            f'<tbody>{"".join(body_rows)}</tbody></table>{legend}')


def _build_kpi_row(data: Dict[str, Any]) -> str:
    """data: {kpis: [{value, label, delta?, state?: positive|warning|negative}]} - stat tiles."""
    kpis = data.get("kpis") or []
    if not 2 <= len(kpis) <= 5:
        raise ValueError("kpi_row needs 2-5 kpis: [{value, label, delta?, state?}]")

    tiles = []
    for k in kpis:
        state = k.get("state")
        delta_color = STATE_TEXT.get(state, MUTED)
        delta = (f'<div style="font-size:12px;font-weight:600;color:{delta_color};margin-top:4px;">'
                 f'{_esc(k.get("delta"))}</div>') if k.get("delta") else ""
        tiles.append(f'''<div style="flex:1;min-width:0;background:{LIGHT};border-top:3px solid {NAVY};padding:14px 16px;">
  <div style="font-size:30px;font-weight:600;color:{NAVY};line-height:1.1;font-variant-numeric:tabular-nums;">{_esc(k.get("value"))}</div>
  <div style="font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:{MUTED};font-weight:600;margin-top:6px;">{_esc(k.get("label"))}</div>
  {delta}
</div>''')
    return f'<div style="display:flex;gap:12px;">{"".join(tiles)}</div>'


def _build_points(data: Dict[str, Any]) -> Tuple[str, List[str]]:
    """data: {items: [{title, text, icon?}]} - 2-4 points, each a navy circle holding a
    white icon (or its number), a short heading and one or two lines of text."""
    from icons import use_icon
    items = data.get("items") or []
    if not 2 <= len(items) <= 4:
        raise ValueError("points needs 2-4 items: [{title, text, icon?}] - 3 is the norm")
    warnings: List[str] = []
    blocks = []
    for i, it in enumerate(items, 1):
        if not it.get("title") or not it.get("text"):
            raise ValueError(f"point {i} needs both title and text")
        _budget("point_title", it["title"], f"point {i} title", warnings)
        _budget("point", it["text"], f"point {i} text", warnings)
        mark = f'<span style="color:#fff;font-size:15px;font-weight:600;">{i}</span>'
        if it.get("icon"):
            r = use_icon(it["icon"], size=18, color="white")
            if r.get("error"):
                raise ValueError(f"point {i}: {r['error']} Closest: {r.get('closest')}")
            if r.get("style") != "glyph":
                raise ValueError(f"point {i}: icon '{it['icon']}' is a colour illustration; points need a "
                                 "glyph icon (dax.py icon list shows the style of each)")
            mark = (f'<img src="../images/{r["path"].rsplit("/", 1)[-1]}" alt="" '
                    f'style="width:18px;height:18px;display:block;">')
        blocks.append(f'''<div style="display:flex;gap:14px;align-items:flex-start;">
  <div style="width:38px;height:38px;border-radius:50%;background:{NAVY};display:flex;align-items:center;justify-content:center;flex:0 0 auto;">{mark}</div>
  <div style="min-width:0;padding-top:1px;">
    <div style="font-size:16px;font-weight:600;color:{NAVY};line-height:1.3;margin-bottom:3px;">{_esc(it["title"])}</div>
    <div style="font-size:13.5px;line-height:1.5;color:{SLATE};">{_rich(it["text"])}</div>
  </div>
</div>''')
    # flex:1 + space-evenly: the points fill the column above the takeaway instead of
    # leaving a dead band between them.
    return (f'<div style="flex:1;display:flex;flex-direction:column;justify-content:space-evenly;gap:14px;'
            f'min-height:0;margin-bottom:16px;">{"".join(blocks)}</div>',
            warnings)


def _build_takeaway(data: Dict[str, Any]) -> Tuple[str, List[str]]:
    """data: {text, label?} - the "so what", pinned to the bottom of its column."""
    text = data.get("text")
    if not text:
        raise ValueError("takeaway needs text (and optionally label, default 'Key takeaway')")
    warnings: List[str] = []
    _budget("takeaway", text, "takeaway text", warnings)
    label = data.get("label") or "Key takeaway"
    return (f'''<div style="margin-top:auto;background:{PANEL_TINT};border-left:4px solid {BRAND_BLUE};padding:12px 16px;">
  <div style="font-size:10.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{NAVY};margin-bottom:4px;">{_esc(label)}</div>
  <div style="font-size:13.5px;line-height:1.5;color:{BLACK};">{_rich(text)}</div>
</div>''', warnings)


def _build_scorecard(data: Dict[str, Any]) -> str:
    """data: {rows: [{label, status, state?}], columns?: [left, right], fill?: bool} - a compact
    metric -> status list. state: positive | warning | negative | neutral (colours the status).
    fill: true spreads the rows over the whole panel - use it when the scorecard is the
    panel's only content, so the panel has no dead space."""
    rows = data.get("rows") or []
    if not 2 <= len(rows) <= 7:
        raise ValueError("scorecard needs 2-7 rows: [{label, status, state?}]")
    cols = data.get("columns") or ["Metric", "Status"]
    if len(cols) != 2:
        raise ValueError("scorecard columns must be two headings: [left, right]")
    head = (f'<div style="display:flex;justify-content:space-between;gap:16px;padding:0 0 6px;'
            f'{"margin-top:10px;" if data.get("fill") else ""}'
            f'border-bottom:1.5px solid {NAVY};font-size:10px;font-weight:600;letter-spacing:.07em;'
            f'text-transform:uppercase;color:{MUTED};"><span>{_esc(cols[0])}</span><span>{_esc(cols[1])}</span></div>')
    body = []
    for r in rows:
        state = r.get("state") or "neutral"
        if state not in STATE_TEXT:
            raise ValueError(f"state '{state}' must be one of positive, warning, negative, neutral")
        grow = "flex:1 1 0;max-height:68px;align-items:center;" if data.get("fill") else "align-items:baseline;"
        body.append(f'<div style="display:flex;justify-content:space-between;{grow}gap:16px;'
                    f'padding:7px 0;border-bottom:1px solid #E1E6EC;">'
                    f'<span style="color:{SLATE};">{_esc(r.get("label"))}</span>'
                    f'<span style="color:{STATE_TEXT[state]};font-weight:600;text-align:right;">{_esc(r.get("status"))}</span></div>')
    size = "font-size:13.5px;flex:1;display:flex;flex-direction:column;min-height:0;" if data.get("fill") else "font-size:12.5px;"
    return f'<div style="{size}line-height:1.35;">{head}{"".join(body)}</div>'


_BUILDERS = {
    "points": _build_points,
    "takeaway": _build_takeaway,
    "scorecard": _build_scorecard,
    "timeline": _build_timeline,
    "process_flow": _build_process_flow,
    "funnel": _build_funnel,
    "matrix_2x2": _build_matrix_2x2,
    "harvey_table": _build_harvey_table,
    "kpi_row": _build_kpi_row,
}


def create_exhibit(exhibit_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Build a brand-compliant exhibit; returns HTML to paste into a slide body."""
    if exhibit_type not in _BUILDERS:
        return {"error": f"Unknown exhibit_type '{exhibit_type}'. Valid: {EXHIBIT_TYPES}"}
    if not isinstance(data, dict):
        return {"error": "data must be an object - see the tool description for each type's shape"}
    try:
        built: Union[str, Tuple[str, List[str]]] = _BUILDERS[exhibit_type](data)
    except (ValueError, TypeError, KeyError) as e:
        return {"error": f"{exhibit_type}: {e}"}
    html_block, warnings = built if isinstance(built, tuple) else (built, [])
    where = {"points": "the layout's points slot (left column)",
             "takeaway": "the layout's takeaway slot; it pins itself to the bottom",
             "scorecard": "the exhibit panel, under a chart or on its own"}.get(
                 exhibit_type, "an exhibit panel or the main column")
    out = {
        "status": "created",
        "exhibit_type": exhibit_type,
        "html": html_block,
        "usage": f"Replace {where} with this html. It is inline-styled and self-contained; do not restyle it.",
    }
    if warnings:
        out["warnings"] = warnings
    return out
