import csv
from io import StringIO
import re


def _safe(value):
    if value is None:
        return ""
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        value = ", ".join(f"{key}: {item}" for key, item in value.items())
    value = str(value)
    if value.lstrip().startswith(("=", "+", "-", "@")) and not re.fullmatch(r"-?\d+(?:\.\d+)?", value.strip()):
        return "'" + value
    return value


def report_csv(report: dict) -> str:
    output = StringIO()
    rows = report["rows"]
    columns = [key for row in rows for key in row if key not in {"cells"}]
    columns = list(dict.fromkeys(columns))
    if report["report"] == "pivot":
        columns = ["label", *report["pivot_columns"], "total"]
        rows = [{"label": row["label"], **row["cells"], "total": row["total"]} for row in rows]
    if not columns:
        columns = ["message"]
        rows = [{"message": "No data for the selected filters"}]
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _safe(row.get(key)) for key in columns})
    return "\ufeff" + output.getvalue()
