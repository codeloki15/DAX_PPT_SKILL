"""Deck assembly: slide listing, live preview build, and PPTX export.

Ported from the original agent's functions.py, with the agent loop, the
conversational scaffolding and the API-key-gated image tools removed. What
remains is the deterministic engine:

    list_slides()            - enumerate slide_NNN.html in the workspace
    build_preview()          - stitch standalone slides into live_preview.html
    open_preview()           - serve it over http://127.0.0.1 and open a browser
    export_pptx()            - Playwright + python-pptx -> editable PPTX

Export pipeline (the part that must not drift):
  1. slides are standalone 1280x720 HTML files
  2. build_preview() stitches them into one page with Chart.js specs injected
  3. Playwright loads that page and records where every .chart-embed and
     <table> sits, as FRACTIONS of its slide, then removes them from the DOM
  4. the in-page dom-to-pptx export turns the remaining HTML into editable
     PowerPoint text, leaving holes where the charts and tables were
  5. python-pptx fills those holes with NATIVE charts and tables at the exact
     recorded positions, and writes speaker notes into the notes field

Step 3 removes the node rather than hiding it: `visibility:hidden` leaves the
element occupying layout, so dom-to-pptx rasterises the surrounding exhibit
panel and drops a blank picture over the native chart.
"""

import base64
import json
import os
import re
import subprocess
import webbrowser
from datetime import datetime
from typing import Any, Dict, List, Optional

import paths
from paths import ensure_directories
from charts import (
    load_all_chart_specs, insert_native_charts, insert_native_tables,
    insert_speaker_notes,
)
from edit_server import (
    start_edit_server, read_notes, list_slide_numbers, save_deck_title,
)

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

SLIDE_RE = re.compile(r"slide_(\d{3})\.html$")
NOTES_STRIP_RE = re.compile(r"<!--\s*SPEAKER_NOTES\s*.*?-->", re.DOTALL)


# =============================================================================
# Template + asset loading
# =============================================================================

def load_template(template_name: str) -> str:
    """Load a template asset that ships with the skill."""
    with open(os.path.join(paths.TEMPLATES_DIR, template_name), "r", encoding="utf-8") as f:
        return f.read()


def image_to_base64(image_path: str) -> Optional[str]:
    """Convert a local image file to a base64 data URL."""
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        ext = os.path.splitext(image_path)[1].lower()
        mime_type = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
        }.get(ext, "image/png")
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{b64_data}"
    except Exception:
        return None


def convert_local_images_to_base64(html_content: str) -> str:
    """Inline local image references so the preview is self-contained."""

    def resolve_relative_path(relative_path: str) -> str:
        return os.path.join(paths.IMAGES_DIR, os.path.basename(relative_path))

    patterns = [
        (r'src=["\']file://([^"\']+)["\']', "src", False),
        (r'url\(["\']?file://([^"\')\s]+)["\']?\)', "url", False),
        (r'src=["\'](/[^"\']+\.(png|jpg|jpeg|gif|webp|svg))["\']', "src", False),
        (r'url\(["\']?(/[^"\')\s]+\.(png|jpg|jpeg|gif|webp|svg))["\']?\)', "url", False),
        (r"url\(['\"]?(\.\.?/images/[^'\")\s]+)['\"]?\)", "url", True),
        (r'src=["\']?(\.\.?/images/[^"\'>\s]+)["\']?', "src", True),
    ]

    result = html_content
    for pattern, attr_type, is_relative in patterns:
        def make_replacer(attr, relative):
            def replace_with_base64(match):
                file_path = match.group(1)
                if relative:
                    file_path = resolve_relative_path(file_path)
                b64 = image_to_base64(file_path)
                if b64:
                    return f'src="{b64}"' if attr == "src" else f'url("{b64}")'
                return match.group(0)
            return replace_with_base64
        result = re.sub(pattern, make_replacer(attr_type, is_relative), result,
                        flags=re.IGNORECASE)
    return result


def extract_style_content(html_content: str) -> str:
    """Extract CSS from the slide's <style> block."""
    if "<style>" in html_content and "</style>" in html_content:
        start = html_content.find("<style>") + len("<style>")
        return html_content[start:html_content.find("</style>")].strip()
    return ""


def extract_body_content(html_content: str) -> str:
    """Extract the slide's <body> contents."""
    if "<body>" in html_content and "</body>" in html_content:
        start = html_content.find("<body>") + len("<body>")
        return html_content[start:html_content.find("</body>")].strip()
    return html_content


# =============================================================================
# Slide enumeration
# =============================================================================

def slide_path(slide_number: int) -> str:
    return os.path.join(paths.SLIDES_DIR, f"slide_{slide_number:03d}.html")


def list_slides() -> Dict[str, Any]:
    """List every slide in the workspace, with its action title."""
    ensure_directories()
    slides = []
    for num in list_slide_numbers():
        path = slide_path(num)
        title = ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            # Design-system slides carry the finding in .action; fall back to <title>.
            m = (re.search(r'<div class="action"[^>]*>(.*?)</div>', content, re.DOTALL)
                 or re.search(r"<title>(.*?)</title>", content, re.DOTALL))
            if m:
                title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        except OSError:
            pass
        slides.append({"slide_number": num, "path": path, "title": title})
    return {"status": "ok", "count": len(slides), "slides": slides}


# =============================================================================
# Live preview
# =============================================================================

def build_preview(title: str, total_slides: Optional[int] = None) -> Dict[str, Any]:
    """Stitch the standalone slide files into the live preview page.

    Iterates the slide numbers actually present rather than range(1, n+1), so a
    gap in numbering cannot silently drop a slide out of the deck.
    """
    ensure_directories()
    template = load_template("live_preview_template.html")

    numbers = list_slide_numbers()
    if total_slides is not None:
        numbers = [n for n in numbers if n <= total_slides]
    if not numbers:
        return {"error": f"No slides found in {paths.SLIDES_DIR}. Write slide_001.html first."}

    slides_content = ""
    for position, i in enumerate(numbers, start=1):
        with open(slide_path(i), "r", encoding="utf-8") as f:
            content = f.read()

        content = convert_local_images_to_base64(content)
        style_content = extract_style_content(content)
        body_content = extract_body_content(content)

        # Notes live in an HTML comment in the file; they belong in the notes
        # box, not inside the rendered slide.
        notes_text = read_notes(i)
        body_content = NOTES_STRIP_RE.sub("", body_content)

        scoped_style = f"<style>/* Slide {i} */\n{style_content}</style>" if style_content else ""

        slides_content += f'''
            <div class="slide-card" data-slide-number="{i}">
                <div class="slide-card-header">
                    <span class="slide-badge">Slide {position}</span>
                    <span class="slide-filename">slide_{i:03d}.html</span>
                </div>
                <div class="slide-viewport">
                    <div class="slide-frame">
                        <div class="slide-content" data-slide-number="{i}">
                            {scoped_style}
                            {body_content}
                        </div>
                    </div>
                </div>
                <script type="application/json" class="slide-notes-data">{json.dumps(notes_text)}</script>
            </div>
'''

    topic_slug = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_")[:50]

    preview_html = template.replace("{{topic}}", title)
    preview_html = preview_html.replace("{{slide_count}}", str(len(numbers)))
    preview_html = preview_html.replace("{{slides_content}}", slides_content)
    preview_html = preview_html.replace("{{topic_slug}}", topic_slug)

    # Inject stored chart specs so the preview renders live Chart.js charts in
    # every .chart-embed. "</" is escaped so a stray string in a spec cannot
    # terminate the <script> block.
    chart_specs_json = json.dumps(load_all_chart_specs()).replace("</", "<\\/")
    preview_html = preview_html.replace("{{chart_specs}}", chart_specs_json)
    preview_html = preview_html.replace("{{chart_renderer}}", load_template("chart_renderer.js"))
    preview_html = preview_html.replace("{{native_export_js}}", load_template("native_export.js"))
    preview_html = preview_html.replace("{{editor_js}}", load_template("editor.js"))

    preview_path = os.path.join(paths.SLIDES_DIR, "live_preview.html")
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(preview_html)

    # Remember the title so the edit server can rebuild this page after edits.
    save_deck_title(title)

    return {"status": "created", "path": preview_path, "total_slides": len(numbers)}


def open_preview(no_browser: bool = False) -> Dict[str, Any]:
    """Serve the preview over http://127.0.0.1 and open it in a browser.

    Serving over http rather than file:// is what makes edits persistable: a
    file:// page cannot write back to disk, and the editor degrades to
    read-only.
    """
    preview_path = os.path.join(paths.SLIDES_DIR, "live_preview.html")
    if not os.path.exists(preview_path):
        return {"error": f"Preview not found: {preview_path}. Run `dax.py preview` first."}

    server = start_edit_server()
    url = server.get("url")
    editable = url is not None
    if not editable:
        url = f"file://{os.path.abspath(preview_path)}"

    browser = "none"
    if not no_browser:
        chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
        ]
        browser = "default"
        for chrome_path in chrome_paths:
            if os.path.exists(chrome_path):
                subprocess.Popen([chrome_path, url],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                browser = "Chrome"
                break
        else:
            webbrowser.open(url)

    result = {"status": "opened", "path": preview_path, "browser": browser,
              "url": url, "editable": editable}
    if not editable:
        result["warning"] = (f"Edit server unavailable ({server.get('error')}); "
                             "the preview is read-only and edits will not persist.")
    return result


# =============================================================================
# PPTX export
# =============================================================================

def generate_timestamped_filename(title: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9\s]", "", title).strip()
    clean = re.sub(r"\s+", "_", clean)[:30] or "Presentation"
    return f"{clean}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"


# Records each chart's position as a fraction of its slide, then removes the
# placeholder. Removing (not hiding) is deliberate - see module docstring.
_EXTRACT_CHARTS_JS = """
() => {
    const placements = [];
    document.querySelectorAll('.slide-content').forEach((sc, domIndex) => {
        const scRect = sc.getBoundingClientRect();
        if (!scRect.width || !scRect.height) return;
        sc.querySelectorAll('.chart-embed[data-chart-id]').forEach(el => {
            const r = el.getBoundingClientRect();
            placements.push({
                dom_index: domIndex,
                chart_id: el.dataset.chartId,
                x: (r.left - scRect.left) / scRect.width,
                y: (r.top - scRect.top) / scRect.height,
                w: r.width / scRect.width,
                h: r.height / scRect.height,
            });
            const panel = el.closest('.exh');
            if (panel) {
                panel.style.border = 'none';
                panel.style.background = 'none';
                panel.style.boxShadow = 'none';
            }
            const spacer = document.createElement('div');
            spacer.style.width = r.width + 'px';
            spacer.style.height = r.height + 'px';
            el.replaceWith(spacer);
        });
    });
    return placements;
}
"""

# dom-to-pptx flattens a <table> into one picture, so capture the cells and
# rebuild them as a native PowerPoint table instead.
_EXTRACT_TABLES_JS = """
() => {
    const out = [];
    document.querySelectorAll('.slide-content').forEach((sc, domIndex) => {
        const scRect = sc.getBoundingClientRect();
        if (!scRect.width || !scRect.height) return;
        sc.querySelectorAll('table').forEach(tbl => {
            const r = tbl.getBoundingClientRect();
            if (!r.width || !r.height) return;

            const headEls = tbl.querySelectorAll('thead th, thead td');
            const headers = Array.from(headEls).map(e => e.innerText.trim());
            if (!headers.length) return;

            const aligns = Array.from(headEls).map(e =>
                getComputedStyle(e).textAlign === 'right' ? 'r' : 'l');

            const rows = Array.from(tbl.querySelectorAll('tbody tr')).map(tr =>
                Array.from(tr.querySelectorAll('td, th')).map(td => td.innerText.trim()));
            if (!rows.length) return;

            out.push({
                dom_index: domIndex,
                headers: headers,
                rows: rows,
                aligns: aligns,
                x: (r.left - scRect.left) / scRect.width,
                y: (r.top - scRect.top) / scRect.height,
                w: r.width / scRect.width,
                h: r.height / scRect.height,
            });

            const spacer = document.createElement('div');
            spacer.style.width = r.width + 'px';
            spacer.style.height = r.height + 'px';
            tbl.replaceWith(spacer);
        });
    });
    return out;
}
"""


def export_pptx(title: str, output: Optional[str] = None) -> Dict[str, Any]:
    """Export the deck to PPTX with editable text, native charts and tables."""
    ensure_directories()

    preview_path = os.path.join(paths.SLIDES_DIR, "live_preview.html")
    if not os.path.exists(preview_path):
        return {"status": "error", "exported": False,
                "error": "Live preview not found. Run `dax.py preview` first."}

    slides_info = list_slides()
    if slides_info["count"] == 0:
        return {"status": "error", "exported": False, "error": "No slides found to export"}

    if not PLAYWRIGHT_AVAILABLE:
        return {"status": "error", "exported": False,
                "error": "Playwright not installed. Run: pip install playwright && "
                         "playwright install chromium"}

    if output:
        output_path = os.path.abspath(output)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        filename = os.path.basename(output_path)
    else:
        filename = generate_timestamped_filename(title)
        output_path = os.path.join(paths.FINAL_OUTPUTS_DIR, filename)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            page.goto(f"file://{os.path.abspath(preview_path)}")
            page.wait_for_load_state("networkidle")
            page.wait_for_selector(".slide-content", timeout=10000)

            chart_placements = page.evaluate(_EXTRACT_CHARTS_JS)
            table_placements = page.evaluate(_EXTRACT_TABLES_JS)

            # #export-btn only toggles the dropdown; the PPTX option is inside.
            page.click("#export-btn")
            with page.expect_download(timeout=120000) as download_info:
                page.click("#export-pptx")
            download_info.value.save_as(output_path)

            browser.close()

        if not os.path.exists(output_path):
            return {"status": "error", "exported": False,
                    "error": "Export file was not created"}

        result: Dict[str, Any] = {
            "status": "success",
            "exported": True,
            "filename": filename,
            "output_path": output_path,
            "slides_exported": slides_info["count"],
        }

        # Fill the holes left in the DOM with native, editable PowerPoint parts.
        if chart_placements:
            result["native_charts"] = insert_native_charts(output_path, chart_placements)
        if table_placements:
            result["native_tables"] = insert_native_tables(output_path, table_placements)

        # Speaker notes are keyed by POSITION in the deck, which must match the
        # dom_index the placements use. Both now derive from list_slide_numbers(),
        # so a gap in slide numbering can no longer misalign them.
        notes_by_index = {}
        for i, num in enumerate(list_slide_numbers()):
            text = read_notes(num)
            if text:
                notes_by_index[i] = text
        if notes_by_index:
            result["speaker_notes"] = insert_speaker_notes(output_path, notes_by_index)

        result["file_size_bytes"] = os.path.getsize(output_path)
        return result

    except Exception as e:
        return {"status": "error", "exported": False,
                "error": f"Export failed: {type(e).__name__}: {e}"}
