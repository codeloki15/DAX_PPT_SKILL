# Data Ingestion Reference

How to load a CSV/Excel file with `dax.py profile` and compute slide-ready figures with `dax.py aggregate`, so every number on a slide traces back to a file.

## Workflow rule (non-negotiable)

```
dax.py profile   →  learn the real column names, dtypes, nulls
dax.py aggregate →  let pandas do the arithmetic
dax.py chart     →  feed the returned rows in verbatim
```

Never transcribe a figure from a preview row, and never compute a sum, mean, share or growth rate mentally. If a slide needs a number, an `aggregate` call produced it. `profile`'s `preview` is for understanding shape only — it is `df.head(15)`, not data to quote.

`--workspace` is a **global** flag and must come before the subcommand:

```bash
python3 scripts/dax.py --workspace ./deck aggregate --file sales.csv --agg revenue:sum
#                      ^^^^^^^^^^^^^^^^^^^ here, not after "aggregate"
```

Both commands print one JSON object to stdout and exit non-zero on error (exception: an empty filter result — see Footguns).

---

## 1. `dax.py profile`

```
dax.py --workspace DIR profile --file F [--sheet S]
```

| Flag | Required | Meaning |
|---|---|---|
| `--file` | yes | Path to the data file. `~` is expanded. |
| `--sheet` | no | Excel sheet name. Defaults to the first sheet. Ignored for CSV/TSV. |

Preview rows are fixed at 15 (`max_preview_rows` is not exposed on the CLI).

### Output structure

```json
{
  "status": "success",
  "file": "sales.csv",
  "rows": 5,
  "column_count": 5,
  "columns": [ ... ],
  "preview": [ ... ],
  "sheet_names": ["Sheet1"],      // Excel only
  "active_sheet": "Sheet1"        // Excel only
}
```

| Key | Type | Notes |
|---|---|---|
| `rows` | int | `len(df)` — the full row count. |
| `column_count` | int | True total. **Only the first 60 columns appear in `columns[]`.** |
| `columns[]` | list | One entry per column, see below. |
| `preview` | list of flat dicts | `df.head(15)`, JSON-safe (dates ISO-formatted). |

### `columns[]` entries

Every entry has `name` (str), `dtype` (str, e.g. `"int64"` / `"object"` / `"float64"`), `nulls` (int). Then **exactly one** of two branches:

| Branch | When | Added keys |
|---|---|---|
| Numeric summary | numeric dtype **and** ≥1 non-null value | `min`, `max`, `mean`, `sum` — each `round(float(x), 4)`, so **always floats even for int64** |
| Samples | everything else | `sample_values`: up to 5 distinct non-null values as strings, each truncated to 60 chars |

An all-null numeric column falls into the samples branch and yields `"sample_values": []`.

### Real output

```bash
python3 scripts/dax.py --workspace ./deck profile --file sales.csv
```
```json
{
  "status": "success",
  "file": "sales.csv",
  "rows": 5,
  "column_count": 5,
  "columns": [
    {"name": "region", "dtype": "object", "nulls": 0,
     "sample_values": ["East", "West", "North"]},
    {"name": "revenue", "dtype": "int64", "nulls": 0,
     "min": 0.0, "max": 300.0, "mean": 125.0, "sum": 625.0},
    {"name": "deals", "dtype": "int64", "nulls": 0,
     "min": 1.0, "max": 3.0, "mean": 2.4, "sum": 12.0}
  ],
  "preview": [
    {"region": "East", "rep": "Ann", "revenue": 300, "deals": 3, "year": 2024}
  ]
}
```

---

## 2. `dax.py aggregate`

```
dax.py --workspace DIR aggregate --file F --agg COL:FN
       [--sheet S] [--group-by C1,C2] [--agg COL:FN ...]
       [--filters JSON] [--sort-by OUTCOL] [--ascending] [--top-n N] [--share]
```

| Flag | Required | Form | Notes |
|---|---|---|---|
| `--file` | yes | path | `~` expanded |
| `--agg` | **yes** | `COL:FN` | Repeatable. Order matters for `--share`. |
| `--group-by` | no | `region,year` | Comma separated. Omit → one whole-table row. |
| `--filters` | no | JSON array or `@file.json` | ANDed in order |
| `--sort-by` | no | **output** column name | See §4 |
| `--ascending` | no | flag | Default is **descending** |
| `--top-n` | no | int | `head(N)`, applied after sorting |
| `--share` | no | flag | Adds `<first metric>_share_pct` |
| `--sheet` | no | str | Excel only |

argparse rejects a missing `--agg` before the engine runs: `dax.py aggregate: error: the following arguments are required: --agg` (exit 2).

### Pipeline order

`load → filter → empty-check → aggregate → share → sort → top-N → round(4)`

Two consequences worth internalising: the share total is computed **before** sort/top-N (so a top-N slice's shares correctly sum to less than 100), and the empty-check runs **before** metric validation.

### Success shape

```json
{"status": "success", "rows": [ {...} ], "row_count": 3,
 "result_columns": ["region", "revenue_sum"]}
```

`rows` is a list of flat dicts — directly chart-ready. `group_by` uses `dropna=False`, so NaN keys survive as their own group.

---

## 3. Valid values

**`VALID_AGGS`** — exactly these seven:

```
sum  mean  median  min  max  count  nunique
```

Invalid → exit 1:
```json
{"error": "agg 'avg' invalid. Valid: ['count', 'max', 'mean', 'median', 'min', 'nunique', 'sum']"}
```

Malformed `--agg` (no colon) is caught by the CLI first:
```json
{"error": "--agg must look like 'column:sum' (got 'revenue'). Valid aggs: sum, mean, median, min, max, count, nunique"}
```

**`VALID_FILTER_OPS`** — exactly these eight:

```
==  !=  >  >=  <  <=  in  contains
```

Invalid → exit 1:
```json
{"error": "Filter op '=~' invalid. Valid: ['!=', '<', '<=', '==', '>', '>=', 'contains', 'in']"}
```

Filter element shape: `{"column": ..., "op": ..., "value": ...}`.

---

## 4. Output column naming rule — read this one

Aggregation renames every metric column. The rule is mechanical:

```
<column>_<agg>                 e.g. revenue:sum   -> revenue_sum
<column>_<agg>_share_pct       e.g. with --share  -> revenue_sum_share_pct
```

**`--sort-by` must name the OUTPUT column, not the input column.** This is the single most common mistake.

```bash
# WRONG
--agg revenue:sum --sort-by revenue
{"error": "sort_by 'revenue' not in result columns: ['region', 'revenue_sum']"}   # exit 1

# RIGHT
--agg revenue:sum --sort-by revenue_sum
```

The same renaming applies downstream: when you feed rows into `dax.py chart`, the value key is `revenue_sum`, not `revenue`. `result_columns` in every success response tells you the exact names — read it rather than guessing.

`--share` only ever applies to the **first** `--agg` in the order you passed it.

---

## 5. Worked examples

Sample file `sales.csv`:

```
region,rep,revenue,deals,year
East,Ann,300,3,2024
East,Bob,150,3,2025
West,Cid,150,2,2024
West,Dee,0,3,2025
North,Eve,25,1,2025
```

### (a) Simple group-by

```bash
python3 scripts/dax.py --workspace ./deck aggregate \
  --file sales.csv --group-by region --agg revenue:sum --sort-by revenue_sum
```
```json
{"status": "success",
 "rows": [{"region": "East", "revenue_sum": 450},
          {"region": "West", "revenue_sum": 150},
          {"region": "North", "revenue_sum": 25}],
 "row_count": 3,
 "result_columns": ["region", "revenue_sum"]}
```

### (b) Filtered + top-N

Filters are ANDed in array order.

```bash
python3 scripts/dax.py --workspace ./deck aggregate \
  --file sales.csv --group-by rep --agg revenue:sum \
  --filters '[{"column":"year","op":">=","value":2025},
              {"column":"region","op":"in","value":["East","West"]}]' \
  --sort-by revenue_sum --top-n 2
```
```json
{"status": "success",
 "rows": [{"rep": "Bob", "revenue_sum": 150},
          {"rep": "Dee", "revenue_sum": 0}],
 "row_count": 2,
 "result_columns": ["rep", "revenue_sum"]}
```

Long filter arrays belong in a file: `--filters @filters.json`.

### (c) Multi-metric

```bash
python3 scripts/dax.py --workspace ./deck aggregate \
  --file sales.csv --group-by region \
  --agg revenue:sum --agg deals:mean --agg rep:nunique --sort-by revenue_sum
```
```json
{"status": "success",
 "rows": [{"region": "East", "revenue_sum": 450, "deals_mean": 3.0, "rep_nunique": 2},
          {"region": "West", "revenue_sum": 150, "deals_mean": 2.5, "rep_nunique": 2},
          {"region": "North", "revenue_sum": 25,  "deals_mean": 1.0, "rep_nunique": 1}],
 "row_count": 3,
 "result_columns": ["region", "revenue_sum", "deals_mean", "rep_nunique"]}
```

### (d) Share of total, top-N

```bash
python3 scripts/dax.py --workspace ./deck aggregate \
  --file sales.csv --group-by region --agg revenue:sum \
  --share --sort-by revenue_sum --top-n 2
```
```json
{"status": "success",
 "rows": [{"region": "East", "revenue_sum": 450, "revenue_sum_share_pct": 72.0},
          {"region": "West", "revenue_sum": 150, "revenue_sum_share_pct": 24.0}],
 "row_count": 2,
 "result_columns": ["region", "revenue_sum", "revenue_sum_share_pct"]}
```

72.0 + 24.0 = 96.0, not 100 — correct, because the denominator is all three regions (625), computed before `--top-n` trimmed the result. Shares are rounded to 1 decimal.

### (e) Whole-table total (no `--group-by`)

```bash
python3 scripts/dax.py --workspace ./deck aggregate \
  --file sales.csv --agg revenue:sum --agg region:nunique
```
```json
{"status": "success", "rows": [{"revenue_sum": 625, "region_nunique": 3}],
 "row_count": 1, "result_columns": ["revenue_sum", "region_nunique"]}
```

---

## 6. Limits and formats

| Constant | Value |
|---|---|
| `MAX_DATA_FILE_MB` | `50` |
| `DATA_EXTENSIONS` | `.csv` `.tsv` `.xlsx` `.xlsm` `.xls` |

- `.tsv` → `sep="\t"`. `.csv` → `sep=None, engine="python"`, which **sniffs the delimiter**, so semicolon- and pipe-delimited files parse as `.csv` too.
- `.xlsx` / `.xlsm` need `openpyxl`. `.xls` is listed but needs `xlrd`, which the skill does not require — treat `.xls` as unsupported in practice and ask for a re-save.
- Anything else: `{"error": "Unsupported data file type '.json'. Supported: ['.csv', '.tsv', '.xls', '.xlsm', '.xlsx']"}`
- Oversized: `{"error": "File is 61.3MB - larger than the 50MB limit"}`
- Requires pandas; without it every call returns `{"error": "pandas not installed. Run: pip install pandas openpyxl"}`. Check with `dax.py doctor`.

---

## 7. Footguns

**`contains` is a case-insensitive REGEX, not a plain substring.** It compiles to `series.astype(str).str.contains(str(value), case=False, na=False)`. `.` `*` `+` `(` `)` `|` `[` `]` `?` are metacharacters.

```bash
--filters '[{"column":"rep","op":"contains","value":"A.n"}]'   # matches "Ann"
```
Escape literals: `"value": "Acme \\(US\\)"`. For an exact match, use `==` or `in`.

**`in` accepts a scalar.** A non-list `value` is wrapped in a one-element list, so `{"op":"in","value":"East"}` behaves like `==`. Pass a JSON array for a real set.

**An empty filter result is a SUCCESS, exit 0, and has no `result_columns` key.**

```json
{"status": "success", "rows": [], "row_count": 0, "note": "No rows matched the filters"}
```
Check `row_count` before charting; do not assume `result_columns` exists. The empty-check also short-circuits metric validation, so a typo'd `--agg` column paired with a zero-match filter returns success rather than the usual column error.

**Numeric summary values in `profile` are floats.** `int64` columns report `"min": 25.0`. Don't render them raw as a count.

**Only the first 60 columns are profiled**, while `column_count` reports the true total. On a wide file, confirm a column exists before referencing it — or rely on the error text, which echoes every available column.

**Errors echo the valid options.** `Metric column 'X' not found. Columns: [...]`, `Sheet 'Q3' not found. Available sheets: [...]`, `sort_by 'X' not in result columns: [...]`. Self-correct from the error text instead of re-profiling.

**Rounding.** All result numerics get `round(4)`; shares get `round(1)`. Do any further rounding in the chart's `--number-format`, not by hand.
