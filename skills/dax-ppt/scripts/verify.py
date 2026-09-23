"""Visual verification - render a slide headlessly and check it for overflow.

screenshot_slide() returns the PNG path plus programmatic overflow findings;
the agent loop attaches the image to the tool result so the model can SEE the
slide and self-critique layout (dead space, cramped exhibits, overflow).
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

    return {
        "status": "ok",
        "slide_number": slide_number,
        "image_path": image_path,
        "overflow_detected": bool(issues),
        "issues": issues,
        "message": ("Overflow detected - fix the slide and re-verify." if issues else
                    "No overflow. LOOK at the attached screenshot: check for dead space above "
                    "the footer, cramped exhibits, and inconsistent styling before moving on."),
    }
