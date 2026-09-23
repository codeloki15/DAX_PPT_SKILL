"""CSV / Excel ingestion and deterministic aggregation.

The agent must never compute figures "in its head" - these tools load real org
data and do the arithmetic in pandas, so every number on a slide traces back to
a file.
"""

import json
import os
from typing import Dict, Any, List, Optional

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

MAX_DATA_FILE_MB = 50
DATA_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xlsm", ".xls"}
VALID_AGGS = {"sum", "mean", "median", "min", "max", "count", "nunique"}
VALID_FILTER_OPS = {"==", "!=", ">", ">=", "<", "<=", "in", "contains"}


def _check_available() -> Optional[Dict[str, Any]]:
    if not PANDAS_AVAILABLE:
        return {"error": "pandas not installed. Run: pip install pandas openpyxl"}
    return None


def _load_df(file_path: str, sheet_name: Optional[str] = None):
    path = os.path.expanduser(file_path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > MAX_DATA_FILE_MB:
        raise ValueError(f"File is {size_mb:.1f}MB - larger than the {MAX_DATA_FILE_MB}MB limit")

    ext = os.path.splitext(path)[1].lower()
    if ext not in DATA_EXTENSIONS:
        raise ValueError(f"Unsupported data file type '{ext}'. Supported: {sorted(DATA_EXTENSIONS)}")

    if ext in (".csv", ".tsv"):
        sep = "\t" if ext == ".tsv" else None
        return pd.read_csv(path, sep=sep, engine="python"), None

    excel = pd.ExcelFile(path)
    sheets = excel.sheet_names
    target = sheet_name if sheet_name is not None else sheets[0]
    if target not in sheets:
        raise ValueError(f"Sheet '{target}' not found. Available sheets: {sheets}")
    return excel.parse(target), sheets


def _records(df) -> List[Dict[str, Any]]:
    """JSON-safe records (numpy scalars and timestamps converted)."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def read_data_file(file_path: str, sheet_name: Optional[str] = None,
                   max_preview_rows: int = 15) -> Dict[str, Any]:
    """Profile a CSV/Excel file: shape, columns, dtypes, preview and numeric summary."""
    unavailable = _check_available()
    if unavailable:
        return unavailable

    try:
        df, sheets = _load_df(file_path, sheet_name)
    except Exception as e:
        return {"error": str(e)}

    columns = []
    for col in df.columns[:60]:
        info = {
            "name": str(col),
            "dtype": str(df[col].dtype),
            "nulls": int(df[col].isna().sum()),
        }
        if pd.api.types.is_numeric_dtype(df[col]) and df[col].notna().any():
            info["min"] = round(float(df[col].min()), 4)
            info["max"] = round(float(df[col].max()), 4)
            info["mean"] = round(float(df[col].mean()), 4)
            info["sum"] = round(float(df[col].sum()), 4)
        else:
            samples = df[col].dropna().astype(str).unique()[:5]
            info["sample_values"] = [s[:60] for s in samples]
        columns.append(info)

    result = {
        "status": "success",
        "file": os.path.expanduser(file_path),
        "rows": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": columns,
        "preview": _records(df.head(max_preview_rows)),
    }
    if sheets:
        result["sheet_names"] = sheets
        result["active_sheet"] = sheet_name or sheets[0]
    return result


def _apply_filters(df, filters: List[Dict[str, Any]]):
    for f in filters:
        col, op, value = f.get("column"), f.get("op"), f.get("value")
        if col not in df.columns:
            raise ValueError(f"Filter column '{col}' not found. Columns: {list(df.columns)}")
        if op not in VALID_FILTER_OPS:
            raise ValueError(f"Filter op '{op}' invalid. Valid: {sorted(VALID_FILTER_OPS)}")
        series = df[col]
        if op == "==":
            df = df[series == value]
        elif op == "!=":
            df = df[series != value]
        elif op == ">":
            df = df[series > value]
        elif op == ">=":
            df = df[series >= value]
        elif op == "<":
            df = df[series < value]
        elif op == "<=":
            df = df[series <= value]
        elif op == "in":
            df = df[series.isin(value if isinstance(value, list) else [value])]
        elif op == "contains":
            df = df[series.astype(str).str.contains(str(value), case=False, na=False)]
    return df


def aggregate_data(
    file_path: str,
    metrics: List[Dict[str, str]],
    group_by: Optional[List[str]] = None,
    filters: Optional[List[Dict[str, Any]]] = None,
    sort_by: Optional[str] = None,
    ascending: bool = False,
    top_n: Optional[int] = None,
    add_share_pct: bool = False,
    sheet_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Group/filter/aggregate a data file and return chart-ready rows.

    metrics: [{"column": "revenue", "agg": "sum"}, ...]. Output columns are
    named "<column>_<agg>". With add_share_pct, the first metric also gets a
    "<column>_<agg>_share_pct" column (percent of the column total).
    """
    unavailable = _check_available()
    if unavailable:
        return unavailable

    try:
        df, _ = _load_df(file_path, sheet_name)

        if filters:
            df = _apply_filters(df, filters)
        if df.empty:
            return {"status": "success", "rows": [], "row_count": 0,
                    "note": "No rows matched the filters"}

        if not metrics:
            raise ValueError("metrics is required, e.g. [{'column': 'revenue', 'agg': 'sum'}]")
        named = {}
        for m in metrics:
            col, agg = m.get("column"), m.get("agg", "sum")
            if col not in df.columns:
                raise ValueError(f"Metric column '{col}' not found. Columns: {list(df.columns)}")
            if agg not in VALID_AGGS:
                raise ValueError(f"agg '{agg}' invalid. Valid: {sorted(VALID_AGGS)}")
            named[f"{col}_{agg}"] = (col, agg)

        if group_by:
            missing = [g for g in group_by if g not in df.columns]
            if missing:
                raise ValueError(f"group_by columns not found: {missing}")
            out = df.groupby(group_by, dropna=False).agg(
                **{name: pd.NamedAgg(column=c, aggfunc=a) for name, (c, a) in named.items()}
            ).reset_index()
        else:
            out = pd.DataFrame([{
                name: getattr(df[c], a)() for name, (c, a) in named.items()
            }])

        if add_share_pct:
            first = next(iter(named))
            total = out[first].sum()
            if total:
                out[f"{first}_share_pct"] = (out[first] / total * 100).round(1)

        if sort_by:
            if sort_by not in out.columns:
                raise ValueError(f"sort_by '{sort_by}' not in result columns: {list(out.columns)}")
            out = out.sort_values(sort_by, ascending=ascending)
        if top_n:
            out = out.head(int(top_n))

        out = out.round(4)
        return {
            "status": "success",
            "rows": _records(out),
            "row_count": int(len(out)),
            "result_columns": [str(c) for c in out.columns],
        }
    except Exception as e:
        return {"error": str(e)}
