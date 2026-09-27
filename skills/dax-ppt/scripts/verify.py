"""Visual verification - render a slide headlessly and check it.

screenshot_slide() returns the PNG path plus:
  issues    - hard failures: overflow past 1280x720, unfilled layout slots
  warnings  - house-style failures that make a slide read as a text dump:
              too many words, running text under 12px, text under 10px,
              text below WCAG contrast (4.5:1, or 3:1 for large text)
The agent then reads the PNG itself, so it can SEE the slide as well.
"""

import json
import os
from typing import Dict, Any

from paths import SLIDES_DIR, SCREENSHOTS_DIR, TEMPLATES_DIR, ensure_directories

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

SLIDE_W, SLIDE_H = 1280, 720
TOLERANCE = 2  # px of forgiveness for sub-pixel rounding

# Same pinned Chart.js the live preview loads - keeps the verified slide
# pixel-consistent with the preview and the exported deck.
CHARTJS_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js"

_METRICS_JS = """
() => {
  const container = document.querySelector('.slide-container') || document.body;
  const offenders = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    if (r.bottom > %(h)d + %(tol)d || r.right > %(w)d + %(tol)d) {
      if (offenders.length < 8) {
        offenders.push({
          tag: el.tagName.toLowerCase(),
          class: (el.className || '').toString().slice(0, 60),
          text: (el.textContent || '').trim().slice(0, 60),
          bottom: Math.round(r.bottom),
          right: Math.round(r.right),
        });
      }
    }
  }
  return {
    scrollHeight: container.scrollHeight,
    scrollWidth: container.scrollWidth,
    offenders,
  };
}
""" % {"h": SLIDE_H, "w": SLIDE_W, "tol": TOLERANCE}


# House-style limits. Measured against a reference deck: slides that read as
# "clean" kept running text >= 12px and body copy near 150 words.
BODY_WORD_BUDGET = 170
MIN_TEXT_PX = 10
MIN_BODY_PX = 12
PLACEHOLDER = "Replace with"

_QUALITY_JS = r"""
() => {
  const root = document.querySelector('.slide-container') || document.body;
  const rgb = s => { const m = (s || '').match(/rgba?\(([^)]+)\)/); if (!m) return null;
                     const p = m[1].split(',').map(parseFloat); return {r:p[0], g:p[1], b:p[2], a: p.length > 3 ? p[3] : 1}; };
  const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = c => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
  const ratio = (a, b) => { const A = lum(a), B = lum(b); return (Math.max(A, B) + 0.05) / (Math.min(A, B) + 0.05); };
  const bgOf = el => { for (let e = el; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor);
                        if (c && c.a > 0.5) return c; } return {r:255, g:255, b:255, a:1}; };
  const opacityOf = el => { let o = 1; for (let e = el; e; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };
  const out = [];
  const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = tw.nextNode())) {
    const el = n.parentElement;
    if (!el || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(el.tagName)) continue;
    const txt = n.textContent.replace(/\s+/g, ' ').trim();
    if (!txt) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const bg = bgOf(el), f = rgb(cs.color) || {r:0, g:0, b:0, a:1};
    const a = opacityOf(el) * f.a;
    const fg = {r: f.r * a + bg.r * (1 - a), g: f.g * a + bg.g * (1 - a), b: f.b * a + bg.b * (1 - a)};
    const zone = el.closest('.foot, .src') ? 'footer'
               : el.closest('.kicker, .action, .cover-title, .sec-num') ? 'headline'
               : (cs.textTransform === 'uppercase' || el.closest('th, .panel-s')) ? 'label' : 'body';
    out.push({text: txt.slice(0, 48), words: txt.split(' ').length, size: parseFloat(cs.fontSize),
              weight: parseInt(cs.fontWeight, 10) || 400, color: cs.color, contrast: ratio(fg, bg), zone});
  }
  return out;
}
"""


def _quality(runs):
    """Turn the text runs on a slide into (issues, warnings)."""
    issues, warnings = [], []

    held = [r for r in runs if PLACEHOLDER in r["text"]]
    for r in held[:4]:
        issues.append(f"Unfilled layout slot or placeholder text: '{r['text']}'")

    body_words = sum(r["words"] for r in runs if r["zone"] == "body")
    if body_words > BODY_WORD_BUDGET:
        warnings.append(f"Text-heavy: {body_words} words of body copy; the house budget is "
                        f"{BODY_WORD_BUDGET}. Cut prose (not exhibits) - move detail to speaker notes.")

    small = [r for r in runs if r["zone"] == "body" and r["size"] < MIN_BODY_PX]
    if small:
        warnings.append(f"Running text under {MIN_BODY_PX}px: {sum(r['words'] for r in small)} words "
                        f"(smallest {min(r['size'] for r in small):g}px), e.g. '{small[0]['text']}'. "
                        f"Raise it to 12.5-14px and cut words to make room.")

    tiny = [r for r in runs if r["size"] < MIN_TEXT_PX]
    if tiny:
        warnings.append(f"Text under the {MIN_TEXT_PX}px floor: {sum(r['words'] for r in tiny)} words "
                        f"(smallest {min(r['size'] for r in tiny):g}px), e.g. '{tiny[0]['text']}'.")

    groups = {}
    for r in runs:
        large = r["size"] >= 24 or (r["size"] >= 18.66 and r["weight"] >= 700)
        need = 3.0 if large else 4.5
        if r["contrast"] < need:
            key = (r["color"], round(r["contrast"], 2), need)
            g = groups.setdefault(key, {"words": 0, "sample": r["text"]})
            g["words"] += r["words"]
    for (color, ratio, need), g in sorted(groups.items(), key=lambda kv: -kv[1]["words"])[:4]:
        warnings.append(f"Low contrast: {g['words']} words in {color} at {ratio}:1 (needs {need}:1), "
                        f"e.g. '{g['sample']}'. Use slate #3C4456, muted #5F6F82 or blue text #007BAD.")
    return issues, warnings, body_words


def _render_charts(page) -> None:
    """Render .chart-embed placeholders in the standalone slide so the
    screenshot shows the chart exactly as the preview and export will.
    Best-effort: without network/specs the placeholder simply stays empty."""
    try:
        if page.locator(".chart-embed[data-chart-id]").count() == 0:
            return
        from charts import load_all_chart_specs
        specs_json = json.dumps(load_all_chart_specs())
        page.add_script_tag(url=CHARTJS_CDN)
        page.evaluate(f"window.CHART_SPECS = {specs_json};")
        with open(os.path.join(TEMPLATES_DIR, "chart_renderer.js"), "r", encoding="utf-8") as f:
            page.add_script_tag(content=f.read())
        page.wait_for_timeout(150)  # let Chart.js paint
    except Exception:
        pass


def screenshot_slide(slide_number: int) -> Dict[str, Any]:
    """Render slide_NNN.html at 1280x720, save a PNG, and report overflow."""
    ensure_directories()

    if not PLAYWRIGHT_AVAILABLE:
        return {"error": "Playwright not installed. Run: pip install playwright && playwright install chromium"}

    slide_path = os.path.join(SLIDES_DIR, f"slide_{slide_number:03d}.html")
    if not os.path.exists(slide_path):
        return {"error": f"Slide {slide_number} not found at {slide_path}"}

    image_path = os.path.join(SCREENSHOTS_DIR, f"slide_{slide_number:03d}.png")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": SLIDE_W, "height": SLIDE_H})
            page.goto(f"file://{os.path.abspath(slide_path)}")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(250)  # settle web fonts
            _render_charts(page)
            metrics = page.evaluate(_METRICS_JS)
            runs = page.evaluate(_QUALITY_JS)
            page.screenshot(path=image_path,
                            clip={"x": 0, "y": 0, "width": SLIDE_W, "height": SLIDE_H})
            browser.close()
    except Exception as e:
        return {"error": f"Screenshot failed: {e}"}

    issues = []
    if metrics["scrollHeight"] > SLIDE_H + TOLERANCE:
        issues.append(f"Vertical overflow: content is {metrics['scrollHeight']}px tall "
                      f"but the slide is {SLIDE_H}px - trim or condense")
    if metrics["scrollWidth"] > SLIDE_W + TOLERANCE:
        issues.append(f"Horizontal overflow: content is {metrics['scrollWidth']}px wide "
                      f"but the slide is {SLIDE_W}px")
    for o in metrics["offenders"]:
        issues.append(f"<{o['tag']} class='{o['class']}'> extends to bottom={o['bottom']} "
                      f"right={o['right']} ('{o['text']}')")

    overflow = bool(issues)
    slot_issues, warnings, body_words = _quality(runs)
    issues += slot_issues

    if issues:
        message = "Fix the issues below and re-verify."
    elif warnings:
        message = (f"No overflow, but {len(warnings)} house-style warning(s) - fix them and re-verify. "
                   "They are what makes a slide read as a text dump.")
    else:
        message = ("Clean. LOOK at the screenshot: check for dead space, cramped exhibits and "
                   "styling that differs from the other slides before moving on.")
    return {
        "status": "ok",
        "slide_number": slide_number,
        "image_path": image_path,
        "overflow_detected": overflow,
        "issues": issues,
        "warnings": warnings,
        "body_words": body_words,
        "message": message,
    }
