"""Local HTTP server that lets the live preview write edits back to disk.

The preview used to be opened over file://, where a page physically cannot
persist anything - "Changes saved." was a lie and every edit died on reload.
This server gives the page a real save path so the browser and the agent share
one source of truth: the slide files in workspace/slides/.

Endpoints (all JSON, same-origin only):
  GET  /                        -> the live preview page
  POST /api/slide/<n>           -> replace slide n's <body> content
  POST /api/slide/<n>/notes     -> set slide n's speaker notes
  POST /api/deck/reorder        -> reorder / delete slides by number
  POST /api/deck/duplicate      -> duplicate a slide
  POST /api/deck/insert         -> insert a blank slide from a layout
  GET  /api/chart/<id>          -> read a chart spec
  POST /api/chart/<id>          -> update a chart spec (categories/series)
  POST /api/verify/<n>          -> re-render slide n and report overflow

Bound to 127.0.0.1 only. It serves the workspace, so it is a local editing
tool - do not expose it to a network.
"""

import json
import os
import re
import shutil
import threading
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from typing import Any, Dict, Optional, Tuple

from paths import SLIDES_DIR, CHARTS_DIR, ensure_directories

MAX_BODY_BYTES = 12 * 1024 * 1024  # generous: slides carry base64 images

# Speaker notes live in an HTML comment so the slide file stays standalone.
NOTES_RE = re.compile(r"<!--\s*SPEAKER_NOTES\s*(.*?)\s*-->", re.DOTALL)
BODY_RE = re.compile(r"(<body[^>]*>)(.*)(</body>)", re.DOTALL | re.IGNORECASE)


# =============================================================================
# Slide file helpers
# =============================================================================

DECK_META_PATH = os.path.join(SLIDES_DIR, "deck_meta.json")


def save_deck_title(title: str) -> None:
    """Remember the deck title so the server can regenerate the preview."""
    try:
        with open(DECK_META_PATH, "w", encoding="utf-8") as f:
            json.dump({"title": title}, f)
    except OSError:
        pass


def _deck_title() -> str:
    try:
        with open(DECK_META_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("title") or "Presentation"
    except (OSError, json.JSONDecodeError):
        return "Presentation"


def slide_path(n: int) -> str:
    return os.path.join(SLIDES_DIR, f"slide_{n:03d}.html")


def list_slide_numbers() -> list:
    if not os.path.isdir(SLIDES_DIR):
        return []
    nums = []
    for name in os.listdir(SLIDES_DIR):
        m = re.fullmatch(r"slide_(\d{3})\.html", name)
        if m:
            nums.append(int(m.group(1)))
    return sorted(nums)


def read_notes(n: int) -> str:
    path = slide_path(n)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        m = NOTES_RE.search(f.read())
    return _unescape_comment(m.group(1)) if m else ""


def _escape_comment(text: str) -> str:
    """Keep arbitrary note text from terminating the HTML comment."""
    return text.replace("--", "&#45;&#45;").replace(">", "&gt;")


def _unescape_comment(text: str) -> str:
    return text.replace("&#45;&#45;", "--").replace("&gt;", ">")


def write_notes(n: int, notes: str) -> Dict[str, Any]:
    path = slide_path(n)
    if not os.path.exists(path):
        return {"error": f"Slide {n} not found"}

    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    block = f"<!-- SPEAKER_NOTES {_escape_comment(notes)} -->"
    if NOTES_RE.search(html):
        html = NOTES_RE.sub(lambda _: block, html, count=1)
    elif "</body>" in html:
        html = html.replace("</body>", f"{block}\n</body>", 1)
    else:
        html += "\n" + block

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return {"status": "saved", "slide_number": n}


def save_slide_body(n: int, body_html: str) -> Dict[str, Any]:
    """Replace the slide's body content, preserving <head>, styles and notes."""
    path = slide_path(n)
    if not os.path.exists(path):
        return {"error": f"Slide {n} not found"}

    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    notes_match = NOTES_RE.search(html)
    notes_block = notes_match.group(0) if notes_match else ""

    if not BODY_RE.search(html):
        return {"error": f"Slide {n} has no <body> element to update"}

    new_body = body_html
    if notes_block and "SPEAKER_NOTES" not in new_body:
        new_body = new_body + "\n" + notes_block

    updated = BODY_RE.sub(lambda m: m.group(1) + "\n" + new_body + "\n" + m.group(3),
                          html, count=1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated)
    return {"status": "saved", "slide_number": n, "bytes": len(updated)}


def _renumber(order: list) -> Dict[str, Any]:
    """Rewrite slide files so they run 1..N in the given order of old numbers.

    Two-phase rename through temp names so overlapping numbers never collide.
    """
    tmp_paths = []
    for old in order:
        src = slide_path(old)
        if not os.path.exists(src):
            return {"error": f"Slide {old} not found"}
        tmp = src + ".reorder_tmp"
        shutil.move(src, tmp)
        tmp_paths.append(tmp)

    # Anything not in `order` is being deleted.
    for leftover in list_slide_numbers():
        try:
            os.remove(slide_path(leftover))
        except OSError:
            pass

    for i, tmp in enumerate(tmp_paths, start=1):
        shutil.move(tmp, slide_path(i))

    return {"status": "saved", "slides": len(tmp_paths)}


def reorder_slides(order: list) -> Dict[str, Any]:
    existing = set(list_slide_numbers())
    if not order:
        return {"error": "order must be a non-empty list of slide numbers"}
    if len(set(order)) != len(order):
        return {"error": "order contains duplicate slide numbers"}
    unknown = [n for n in order if n not in existing]
    if unknown:
        return {"error": f"unknown slide numbers: {unknown}"}
    return _renumber(list(order))


def _splice_new_slide(after: int, html: str) -> Dict[str, Any]:
    """Insert `html` as a new slide after slide number `after` (0 = first).

    Existing slides are moved through temp names so numbering never collides,
    then everything is renumbered 1..N in the final order.
    """
    nums = list_slide_numbers()
    if after != 0 and after not in nums:
        return {"error": f"Slide {after} not found"}

    staging = os.path.join(SLIDES_DIR, "__slide_staging.tmp")
    with open(staging, "w", encoding="utf-8") as f:
        f.write(html)

    order = ["__NEW__"] if after == 0 else []
    for num in nums:
        order.append(num)
        if num == after:
            order.append("__NEW__")

    tmp_paths = []
    try:
        for item in order:
            if item == "__NEW__":
                tmp = os.path.join(SLIDES_DIR, f"__new_{len(tmp_paths)}.tmp")
                shutil.copy(staging, tmp)
            else:
                tmp = slide_path(item) + f".__mv_{len(tmp_paths)}.tmp"
                shutil.move(slide_path(item), tmp)
            tmp_paths.append(tmp)
    finally:
        if os.path.exists(staging):
            os.remove(staging)

    for i, tmp in enumerate(tmp_paths, start=1):
        shutil.move(tmp, slide_path(i))

    return {"status": "saved", "slides": len(tmp_paths), "inserted_at": after + 1}


def duplicate_slide(n: int) -> Dict[str, Any]:
    nums = list_slide_numbers()
    if n not in nums:
        return {"error": f"Slide {n} not found"}
    with open(slide_path(n), "r", encoding="utf-8") as f:
        content = f.read()
    return _splice_new_slide(n, content)


def read_slide_html(n: int) -> Dict[str, Any]:
    """Full HTML of one slide - used for copy/paste between positions."""
    path = slide_path(n)
    if not os.path.exists(path):
        return {"error": f"Slide {n} not found"}
    with open(path, "r", encoding="utf-8") as f:
        return {"status": "ok", "slide_number": n, "html": f.read()}


def paste_slide(after: int, html: str) -> Dict[str, Any]:
    """Insert a previously copied slide after slide `after`."""
    if not isinstance(html, str) or "<" not in html:
        return {"error": "html (a full slide document) is required"}
    return _splice_new_slide(after, html)


BLANK_LAYOUTS = {
    "title_content": """<div class="slide-container">
  <div class="kicker">SECTION</div>
  <div class="action">New slide - replace this with the finding this slide proves</div>
  <div class="rule"></div>
  <div class="body">
    <p class="lead">Supporting context goes here.</p>
  </div>
  <div class="foot"><span>Exhibit &mdash;</span><span>Data Axle</span></div>
</div>""",
    "section_break": """<div class="slide-container" style="justify-content:center;">
  <div class="kicker">SECTION</div>
  <div class="action" style="font-size:38px;">Section title</div>
  <div class="rule"></div>
  <div class="foot"><span></span><span>Data Axle</span></div>
</div>""",
    "title_slide": """<div class="slide-container" style="justify-content:center;">
  <div class="kicker">DATA AXLE</div>
  <div class="action" style="font-size:42px;line-height:1.15;">Presentation title</div>
  <div class="rule"></div>
  <p class="lead" style="font-size:15px;">Subtitle or audience &nbsp;|&nbsp; Date</p>
</div>""",
    "two_content": """<div class="slide-container">
  <div class="kicker">SECTION</div>
  <div class="action">The finding this slide proves</div>
  <div class="rule"></div>
  <div class="body">
    <div style="display:flex;gap:18px;flex:1;min-height:0;">
      <div class="exh" style="flex:1;display:flex;flex-direction:column;">
        <div class="exh-t">EXHIBIT &mdash; | LEFT PANEL</div>
        <ul class="c"><li>First point</li><li>Second point</li></ul>
      </div>
      <div class="exh" style="flex:1;display:flex;flex-direction:column;">
        <div class="exh-t">EXHIBIT &mdash; | RIGHT PANEL</div>
        <ul class="c"><li>First point</li><li>Second point</li></ul>
      </div>
    </div>
  </div>
  <div class="foot"><span>Exhibit &mdash;</span><span>Data Axle</span></div>
</div>""",
    "table": """<div class="slide-container">
  <div class="kicker">SECTION</div>
  <div class="action">The finding this table proves</div>
  <div class="rule"></div>
  <div class="body">
    <div class="exh" style="flex:1;">
      <div class="exh-t">EXHIBIT &mdash; | COMPARISON</div>
      <table>
        <thead><tr><th>Dimension</th><th>Option A</th><th>Option B</th></tr></thead>
        <tbody>
          <tr><td><b>Row one</b></td><td>&mdash;</td><td>&mdash;</td></tr>
          <tr><td><b>Row two</b></td><td>&mdash;</td><td>&mdash;</td></tr>
          <tr><td><b>Row three</b></td><td>&mdash;</td><td>&mdash;</td></tr>
        </tbody>
      </table>
    </div>
  </div>
  <div class="foot"><span>Exhibit &mdash;</span><span>Data Axle</span></div>
</div>""",
    "blank": """<div class="slide-container">
  <div class="body"></div>
</div>""",
}

# Human-facing names for the layout gallery.
LAYOUT_LABELS = {
    "title_slide": "Title slide",
    "title_content": "Title and content",
    "two_content": "Two content panels",
    "table": "Comparison table",
    "section_break": "Section header",
    "blank": "Blank",
}


def insert_slide(after: int, layout: str = "title_content") -> Dict[str, Any]:
    """Insert a new slide after slide `after` (0 = at the beginning)."""
    if layout not in BLANK_LAYOUTS:
        return {"error": f"unknown layout '{layout}'. Valid: {sorted(BLANK_LAYOUTS)}"}

    nums = list_slide_numbers()
    if after != 0 and after not in nums:
        return {"error": f"Slide {after} not found"}

    # Reuse an existing slide's <head> so the new slide inherits the design system.
    head = ""
    if nums:
        with open(slide_path(nums[0]), "r", encoding="utf-8") as f:
            src = f.read()
        m = re.search(r"<head[^>]*>.*?</head>", src, re.DOTALL | re.IGNORECASE)
        head = m.group(0) if m else ""

    new_html = (f"<!DOCTYPE html>\n<html lang=\"en\">{head}<body>\n"
                f"{BLANK_LAYOUTS[layout]}\n</body></html>")

    return _splice_new_slide(after, new_html)


# =============================================================================
# Version history (durable undo)
# =============================================================================

HISTORY_DIR = os.path.join(SLIDES_DIR, ".history")
MAX_SNAPSHOTS = 40


def snapshot_deck(label: str) -> Dict[str, Any]:
    """Copy the current slide files into a timestamped history folder.

    Taken before every destructive operation, so a user can roll the whole
    deck back even after closing the tab (in-memory undo dies with the page).
    """
    import time

    nums = list_slide_numbers()
    if not nums:
        return {"status": "skipped", "reason": "no slides"}

    os.makedirs(HISTORY_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    dest = os.path.join(HISTORY_DIR, stamp)
    os.makedirs(dest, exist_ok=True)

    for n in nums:
        shutil.copy(slide_path(n), os.path.join(dest, f"slide_{n:03d}.html"))
    with open(os.path.join(dest, "label.txt"), "w", encoding="utf-8") as f:
        f.write(label)

    # Trim oldest snapshots
    snaps = sorted(d for d in os.listdir(HISTORY_DIR)
                   if os.path.isdir(os.path.join(HISTORY_DIR, d)))
    for old in snaps[:-MAX_SNAPSHOTS]:
        shutil.rmtree(os.path.join(HISTORY_DIR, old), ignore_errors=True)

    return {"status": "ok", "snapshot": stamp, "label": label, "slides": len(nums)}


def list_history() -> Dict[str, Any]:
    if not os.path.isdir(HISTORY_DIR):
        return {"status": "ok", "versions": []}
    dirs = [x for x in os.listdir(HISTORY_DIR)
            if os.path.isdir(os.path.join(HISTORY_DIR, x))]
    versions = []
    for d in sorted(dirs, reverse=True):
        label_path = os.path.join(HISTORY_DIR, d, "label.txt")
        label = ""
        if os.path.exists(label_path):
            with open(label_path, "r", encoding="utf-8") as f:
                label = f.read().strip()
        count = len([f for f in os.listdir(os.path.join(HISTORY_DIR, d))
                     if f.startswith("slide_")])
        versions.append({"id": d, "label": label, "slides": count})
    return {"status": "ok", "versions": versions}


def restore_snapshot(snapshot_id: str) -> Dict[str, Any]:
    if not re.fullmatch(r"[0-9\-]{1,32}", snapshot_id):
        return {"error": "invalid snapshot id"}
    src = os.path.join(HISTORY_DIR, snapshot_id)
    if not os.path.isdir(src):
        return {"error": f"snapshot '{snapshot_id}' not found"}

    snapshot_deck("before restore")

    for n in list_slide_numbers():
        try:
            os.remove(slide_path(n))
        except OSError:
            pass

    restored = 0
    for name in sorted(os.listdir(src)):
        if name.startswith("slide_") and name.endswith(".html"):
            shutil.copy(os.path.join(src, name), os.path.join(SLIDES_DIR, name))
            restored += 1

    return {"status": "restored", "snapshot": snapshot_id, "slides": restored}


# =============================================================================
# Chart spec editing
# =============================================================================

def read_chart(chart_id: str) -> Dict[str, Any]:
    from charts import load_chart_spec
    spec = load_chart_spec(chart_id)
    if spec is None:
        return {"error": f"chart '{chart_id}' not found"}
    return {"status": "ok", "spec": spec}


def update_chart(chart_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update a stored chart spec's data, re-validating through create_chart."""
    from charts import load_chart_spec, create_chart

    spec = load_chart_spec(chart_id)
    if spec is None:
        return {"error": f"chart '{chart_id}' not found"}

    merged = {
        "chart_id": chart_id,
        "chart_type": payload.get("type", spec["type"]),
        "categories": payload.get("categories", spec["categories"]),
        "series": payload.get("series", spec["series"]),
        "title": payload.get("title", spec.get("title")),
        "colors": payload.get("colors", spec.get("colors")),
        "number_format": payload.get("number_format", spec.get("number_format")),
    }
    if merged["chart_type"] == "waterfall":
        merged["totals"] = payload.get("totals", spec.get("totals") or [])

    result = create_chart(**merged)
    if "error" in result:
        return result
    return {"status": "saved", "chart_id": chart_id, "spec": load_chart_spec(chart_id)}


# =============================================================================
# HTTP handler
# =============================================================================

class EditRequestHandler(SimpleHTTPRequestHandler):
    """Serves the preview and handles the edit API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SLIDES_DIR, **kwargs)

    def log_message(self, fmt, *args):
        pass  # keep the agent's console clean

    # -- helpers ----------------------------------------------------------
    def _send_json(self, payload: Dict[str, Any], status: int = 200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return None, "invalid Content-Length"
        if length <= 0:
            return None, "empty request body"
        if length > MAX_BODY_BYTES:
            return None, f"request body exceeds {MAX_BODY_BYTES} bytes"
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8")), None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return None, f"invalid JSON: {e}"

    def _guard_local(self) -> bool:
        """Only accept same-origin browser requests from this machine."""
        host = (self.client_address[0] if self.client_address else "")
        if host not in ("127.0.0.1", "::1"):
            self._send_json({"error": "forbidden"}, 403)
            return False
        return True

    def _serve_preview(self):
        """Regenerate the preview from the current slide files and serve it."""
        try:
            # Imported lazily: deck imports edit_server, so a module-level
            # import here would be circular.
            from deck import build_preview
            title = _deck_title()
            build_preview(title)
            path = os.path.join(SLIDES_DIR, "live_preview.html")
            with open(path, "rb") as f:
                body = f.read()
        except Exception as e:
            body = (f"<h1>Preview error</h1><pre>{type(e).__name__}: {e}</pre>").encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    # -- routes -----------------------------------------------------------
    def do_GET(self):
        if self.path in ("/", "/index.html", "/live_preview.html"):
            # Rebuild from the slide files so saved edits are always reflected.
            # The stored live_preview.html is a snapshot; serving it directly
            # would show stale content after an edit.
            return self._serve_preview()

        m = re.fullmatch(r"/api/chart/([A-Za-z0-9_\-]{1,40})", self.path)
        if m:
            if not self._guard_local():
                return
            return self._send_json(read_chart(m.group(1)))

        if self.path == "/api/deck":
            if not self._guard_local():
                return
            nums = list_slide_numbers()
            return self._send_json({
                "status": "ok",
                "slides": [{"number": n, "notes": read_notes(n)} for n in nums],
            })

        if self.path == "/api/layouts":
            if not self._guard_local():
                return
            return self._send_json({
                "status": "ok",
                "layouts": [{"id": k, "label": LAYOUT_LABELS.get(k, k)}
                            for k in ["title_slide", "title_content", "two_content",
                                      "table", "section_break", "blank"]],
            })

        if self.path == "/api/history":
            if not self._guard_local():
                return
            return self._send_json(list_history())

        m = re.fullmatch(r"/api/slide/(\d+)/html", self.path)
        if m:
            if not self._guard_local():
                return
            return self._send_json(read_slide_html(int(m.group(1))))

        return super().do_GET()

    def do_POST(self):
        if not self._guard_local():
            return

        payload, err = self._read_json()
        if err:
            return self._send_json({"error": err}, 400)

        try:
            result = self._route_post(payload)
        except Exception as e:  # never take the server down on a bad edit
            return self._send_json({"error": f"{type(e).__name__}: {e}"}, 500)

        if result is None:
            return self._send_json({"error": f"unknown endpoint {self.path}"}, 404)
        status = 400 if "error" in result else 200
        return self._send_json(result, status)

    def _route_post(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        m = re.fullmatch(r"/api/slide/(\d+)", self.path)
        if m:
            body = payload.get("body_html")
            if not isinstance(body, str):
                return {"error": "body_html (string) is required"}
            return save_slide_body(int(m.group(1)), body)

        m = re.fullmatch(r"/api/slide/(\d+)/notes", self.path)
        if m:
            notes = payload.get("notes", "")
            if not isinstance(notes, str):
                return {"error": "notes must be a string"}
            return write_notes(int(m.group(1)), notes)

        if self.path == "/api/deck/reorder":
            order = payload.get("order")
            if not isinstance(order, list):
                return {"error": "order (list of slide numbers) is required"}
            snapshot_deck(payload.get("label") or "before reorder")
            return reorder_slides([int(x) for x in order])

        if self.path == "/api/deck/duplicate":
            snapshot_deck("before duplicate")
            return duplicate_slide(int(payload.get("slide_number", 0)))

        if self.path == "/api/deck/insert":
            snapshot_deck("before add slide")
            return insert_slide(int(payload.get("after", 0)),
                                payload.get("layout", "title_content"))

        if self.path == "/api/deck/paste":
            snapshot_deck("before paste")
            return paste_slide(int(payload.get("after", 0)), payload.get("html", ""))

        if self.path == "/api/history/restore":
            return restore_snapshot(str(payload.get("snapshot_id", "")))

        m = re.fullmatch(r"/api/chart/([A-Za-z0-9_\-]{1,40})", self.path)
        if m:
            return update_chart(m.group(1), payload)

        m = re.fullmatch(r"/api/verify/(\d+)", self.path)
        if m:
            from verify import screenshot_slide
            result = screenshot_slide(int(m.group(1)))
            result.pop("image_path", None)  # the browser only needs the findings
            return result

        return None


# =============================================================================
# Server lifecycle
# =============================================================================

_server: Optional[ThreadingHTTPServer] = None
_thread: Optional[threading.Thread] = None


def start_edit_server(port: int = 0) -> Dict[str, Any]:
    """Start (or return the already-running) local edit server."""
    global _server, _thread

    ensure_directories()

    if _server is not None:
        return {"status": "already_running", "url": server_url(), "port": _server.server_port}

    try:
        _server = ThreadingHTTPServer(("127.0.0.1", port), EditRequestHandler)
    except OSError as e:
        return {"error": f"could not start edit server: {e}"}

    _server.daemon_threads = True
    _thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _thread.start()
    return {"status": "started", "url": server_url(), "port": _server.server_port}


def server_url() -> Optional[str]:
    if _server is None:
        return None
    return f"http://127.0.0.1:{_server.server_port}/live_preview.html"


def stop_edit_server() -> Dict[str, Any]:
    global _server, _thread
    if _server is None:
        return {"status": "not_running"}
    _server.shutdown()
    _server.server_close()
    _server = None
    _thread = None
    return {"status": "stopped"}
