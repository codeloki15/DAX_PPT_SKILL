#!/usr/bin/env python3
"""DAX deck builder - single CLI entry point for the Data Axle PPT skill.

Every subcommand prints ONE JSON object to stdout and exits non-zero on error,
so a host agent can parse the result without scraping prose.

    dax.py chart      --id rev --type column --categories ... --series ...
    dax.py exhibit    --type timeline --data '{"items":[...]}'
    dax.py profile    --file sales.csv
    dax.py aggregate  --file sales.csv --group-by region --agg revenue:sum
    dax.py verify     --slide 3
    dax.py preview    --title "Deck title"
    dax.py open       [--no-browser]
    dax.py notes      --slide 3 [--set "..."]
    dax.py export     --title "Deck title" [--output path.pptx]
    dax.py list
    dax.py reset      [--yes]
    dax.py doctor

--workspace (or $DAX_PPT_WORKSPACE) selects the deck directory; it defaults to
./dax_workspace. Pass it explicitly when building more than one deck so
concurrent decks never overwrite each other's slides.
"""

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paths  # noqa: E402


def emit(payload, exit_code=None):
    """Print one JSON object and exit. Non-zero exit when the payload errored."""
    print(json.dumps(payload, indent=2, default=str))
    if exit_code is None:
        exit_code = 1 if (isinstance(payload, dict) and
                          (payload.get("error") or payload.get("status") == "error")) else 0
    sys.exit(exit_code)


def _parse_series(values):
    """--series 'Name:1,2,3' (repeatable) -> [{name, values}]."""
    series = []
    for raw in values or []:
        if ":" not in raw:
            emit({"error": f"--series must look like 'Name:1,2,3' (got {raw!r})"})
        name, _, nums = raw.partition(":")
        try:
            parsed = [float(n) for n in nums.split(",") if n.strip() != ""]
        except ValueError:
            emit({"error": f"--series values must all be numbers (got {nums!r})"})
        series.append({"name": name.strip(), "values": parsed})
    return series


def _load_json_arg(value, flag):
    """Accept inline JSON or @path/to/file.json."""
    if value is None:
        return None
    try:
        if value.startswith("@"):
            with open(value[1:], "r", encoding="utf-8") as f:
                return json.load(f)
        return json.loads(value)
    except (OSError, json.JSONDecodeError) as e:
        emit({"error": f"{flag} is not valid JSON: {e}"})


# =============================================================================
# Subcommands
# =============================================================================

def cmd_chart(args):
    from charts import create_chart
    series = _parse_series(args.series)
    if args.series_json:
        series = _load_json_arg(args.series_json, "--series-json")
    emit(create_chart(
        chart_id=args.id,
        chart_type=args.type,
        categories=[c.strip() for c in args.categories.split(",")] if args.categories else [],
        series=series,
        title=args.title,
        colors=[c.strip() for c in args.colors.split(",")] if args.colors else None,
        number_format=args.number_format,
        totals=[int(t) for t in args.totals.split(",")] if args.totals else None,
    ))


def cmd_exhibit(args):
    from exhibits import create_exhibit
    emit(create_exhibit(args.type, _load_json_arg(args.data, "--data") or {}))


def cmd_profile(args):
    from data_tools import read_data_file
    try:
        emit(read_data_file(args.file, sheet_name=args.sheet))
    except (ValueError, OSError) as e:
        emit({"error": f"{type(e).__name__}: {e}"})


def cmd_aggregate(args):
    from data_tools import aggregate_data
    metrics = []
    for raw in args.agg or []:
        if ":" not in raw:
            emit({"error": f"--agg must look like 'column:sum' (got {raw!r}). "
                           "Valid aggs: sum, mean, median, min, max, count, nunique"})
        col, _, fn = raw.partition(":")
        metrics.append({"column": col.strip(), "agg": fn.strip()})
    if not metrics:
        emit({"error": "--agg is required, e.g. --agg revenue:sum"})
    try:
        emit(aggregate_data(
            file_path=args.file,
            metrics=metrics,
            group_by=[g.strip() for g in args.group_by.split(",")] if args.group_by else None,
            filters=_load_json_arg(args.filters, "--filters"),
            sort_by=args.sort_by,
            ascending=args.ascending,
            top_n=args.top_n,
            add_share_pct=args.share,
            sheet_name=args.sheet,
        ))
    except (ValueError, KeyError, OSError) as e:
        emit({"error": f"{type(e).__name__}: {e}"})


def cmd_verify(args):
    from verify import screenshot_slide
    result = screenshot_slide(args.slide)
    if isinstance(result, dict) and result.get("image_path"):
        result["next_step"] = ("Read the image at image_path and LOOK at it: fix any "
                               "overflow, then check for a dead band above the footer.")
    emit(result)


def cmd_preview(args):
    from deck import build_preview
    emit(build_preview(args.title, total_slides=args.slides))


def cmd_open(args):
    from deck import open_preview
    result = open_preview(no_browser=args.no_browser)
    if result.get("editable"):
        result["note"] = ("The edit server is running. Slide files are now SHARED STATE: "
                          "re-read a slide before editing it. This process must stay alive "
                          "to keep serving the preview.")
        print(json.dumps(result, indent=2, default=str))
        if not args.no_browser or args.serve:
            print("\nServing. Press Ctrl+C to stop.", file=sys.stderr)
            try:
                import time
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                print("Stopped.", file=sys.stderr)
        sys.exit(0)
    emit(result)


def cmd_notes(args):
    from edit_server import read_notes, write_notes
    from deck import slide_path
    if not os.path.exists(slide_path(args.slide)):
        emit({"error": f"Slide {args.slide} not found"})
    if args.set is not None:
        emit(write_notes(args.slide, args.set))
    emit({"status": "ok", "slide_number": args.slide, "notes": read_notes(args.slide)})


def cmd_export(args):
    from deck import export_pptx
    emit(export_pptx(args.title, output=args.output))


def cmd_list(args):
    from deck import list_slides
    emit(list_slides())


def cmd_reset(args):
    if not args.yes:
        emit({"error": "Refusing to wipe the workspace without --yes",
              "would_delete": paths.RESETTABLE_DIRS})
    removed = []
    for d in paths.RESETTABLE_DIRS:
        if os.path.isdir(d):
            shutil.rmtree(d)
            removed.append(d)
    paths.ensure_directories()
    emit({"status": "reset", "removed": removed,
          "kept": paths.FINAL_OUTPUTS_DIR,
          "note": "Exported decks in final_outputs were kept."})


def cmd_doctor(args):
    """Check that every dependency the skill needs is actually present."""
    report = {"status": "ok", "workspace": paths.WORKSPACE_DIR, "checks": {}, "problems": []}

    def check(name, ok, detail, fix=None):
        report["checks"][name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            report["problems"].append({"check": name, "detail": detail, "fix": fix})

    check("python", True, sys.version.split()[0])

    for mod, fix in (("pptx", "pip install python-pptx"),
                     ("pandas", "pip install pandas"),
                     ("openpyxl", "pip install openpyxl"),
                     ("playwright", "pip install playwright")):
        try:
            __import__(mod)
            check(mod, True, "importable")
        except ImportError as e:
            check(mod, False, str(e), fix)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            version = b.version
            b.close()
        check("chromium", True, version)
    except Exception as e:
        check("chromium", False, f"{type(e).__name__}: {e}",
              "playwright install chromium")

    for asset in ("live_preview_template.html", "editor.js",
                  "native_export.js", "chart_renderer.js"):
        p_ = os.path.join(paths.TEMPLATES_DIR, asset)
        check(f"asset:{asset}", os.path.exists(p_), p_,
              "Re-install the skill; assets/templates/ is incomplete.")

    if report["problems"]:
        report["status"] = "error"
    emit(report, exit_code=1 if report["problems"] else 0)


# =============================================================================
# Parser
# =============================================================================

def build_parser():
    p = argparse.ArgumentParser(prog="dax.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", help="Deck workspace directory (default ./dax_workspace "
                                       "or $DAX_PPT_WORKSPACE)")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("chart", help="Create a native chart spec")
    c.add_argument("--id", required=True)
    c.add_argument("--type", required=True,
                   choices=["column", "bar", "line", "area", "pie", "doughnut",
                            "column_stacked", "bar_stacked", "waterfall"])
    c.add_argument("--categories", help="Comma-separated category labels")
    c.add_argument("--series", action="append", metavar="NAME:v1,v2",
                   help="Repeatable. e.g. --series 'Revenue:12,18,25'")
    c.add_argument("--series-json", help="Full series array as JSON or @file.json")
    c.add_argument("--title")
    c.add_argument("--colors", help="Comma-separated 6-digit hex, semantic use only")
    c.add_argument("--number-format", dest="number_format")
    c.add_argument("--totals", help="Waterfall only: comma-separated total indices")
    c.set_defaults(func=cmd_chart)

    e = sub.add_parser("exhibit", help="Build a brand-styled exhibit")
    e.add_argument("--type", required=True,
                   choices=["timeline", "process_flow", "funnel", "matrix_2x2",
                            "harvey_table", "kpi_row"])
    e.add_argument("--data", required=True, help="JSON payload, or @file.json")
    e.set_defaults(func=cmd_exhibit)

    pr = sub.add_parser("profile", help="Profile a CSV/TSV/Excel file")
    pr.add_argument("--file", required=True)
    pr.add_argument("--sheet")
    pr.set_defaults(func=cmd_profile)

    ag = sub.add_parser("aggregate", help="Compute figures from a data file")
    ag.add_argument("--file", required=True)
    ag.add_argument("--sheet")
    ag.add_argument("--group-by", dest="group_by", help="Comma-separated columns")
    ag.add_argument("--agg", action="append", metavar="COL:FN", required=True,
                    help="Repeatable. e.g. --agg revenue:sum. "
                         "Aggs: sum, mean, median, min, max, count, nunique")
    ag.add_argument("--filters", help='JSON array, or @file.json. e.g. '
                                      '\'[{"column":"year","op":">=","value":2024}]\'. '
                                      'Ops: == != > >= < <= in contains')
    ag.add_argument("--sort-by", dest="sort_by", help="Output column, e.g. revenue_sum")
    ag.add_argument("--ascending", action="store_true", help="Sort ascending (default descending)")
    ag.add_argument("--top-n", dest="top_n", type=int)
    ag.add_argument("--share", action="store_true",
                    help="Add a <metric>_share_pct column (percent of total)")
    ag.set_defaults(func=cmd_aggregate)

    v = sub.add_parser("verify", help="Screenshot a slide and check overflow")
    v.add_argument("--slide", type=int, required=True)
    v.set_defaults(func=cmd_verify)

    pv = sub.add_parser("preview", help="Build the live preview page")
    pv.add_argument("--title", required=True)
    pv.add_argument("--slides", type=int, help="Only include slides up to this number")
    pv.set_defaults(func=cmd_preview)

    op = sub.add_parser("open", help="Serve the preview and open a browser")
    op.add_argument("--no-browser", dest="no_browser", action="store_true")
    op.add_argument("--serve", action="store_true", help="Keep serving after opening")
    op.set_defaults(func=cmd_open)

    nt = sub.add_parser("notes", help="Read or write speaker notes")
    nt.add_argument("--slide", type=int, required=True)
    nt.add_argument("--set", help="Write these notes instead of reading")
    nt.set_defaults(func=cmd_notes)

    ex = sub.add_parser("export", help="Export to PPTX")
    ex.add_argument("--title", required=True)
    ex.add_argument("--output", help="Explicit .pptx path (default final_outputs/)")
    ex.set_defaults(func=cmd_export)

    ls = sub.add_parser("list", help="List slides in the workspace")
    ls.set_defaults(func=cmd_list)

    rs = sub.add_parser("reset", help="Wipe slides/charts/screenshots")
    rs.add_argument("--yes", action="store_true", help="Required. This deletes files.")
    rs.set_defaults(func=cmd_reset)

    dr = sub.add_parser("doctor", help="Check dependencies are installed")
    dr.set_defaults(func=cmd_doctor)

    return p


def main():
    args = build_parser().parse_args()
    # Resolve the workspace BEFORE importing any engine module, so none of them
    # bind a stale SLIDES_DIR / CHARTS_DIR at import time.
    paths.set_workspace(args.workspace or paths.WORKSPACE_DIR)
    args.func(args)


if __name__ == "__main__":
    main()
