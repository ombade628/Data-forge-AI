import csv
import io
import json
from openpyxl import Workbook

SUPPORTED_FORMATS = {"csv", "json", "jsonl", "xlsx"}
MEDIA_TYPES = {
    "csv": "text/csv",
    "json": "application/json",
    "jsonl": "application/x-ndjson",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def build_export(
    version_number: int, records: list[dict], export_format: str
) -> tuple[io.BytesIO, str, str]:
    """Build the export in memory and return (stream, media_type, filename).

    Building in memory avoids writing to a shared directory, which would otherwise
    leak files between users, fill the container's disk, and require cleanup jobs.
    """
    if export_format not in SUPPORTED_FORMATS:
        raise ValueError("format must be csv, json, jsonl, or xlsx")

    columns = list(records[0].keys()) if records else []
    buffer = io.BytesIO()

    if export_format == "json":
        buffer.write(json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8"))
    elif export_format == "jsonl":
        buffer.write(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records).encode("utf-8")
        )
    elif export_format == "csv":
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)
        buffer.write(text.getvalue().encode("utf-8"))
    else:  # xlsx
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(columns)
        for row in records:
            sheet.append([row.get(column) for column in columns])
        workbook.save(buffer)

    buffer.seek(0)
    filename = f"dataforge-v{version_number}.{export_format}"
    return buffer, MEDIA_TYPES[export_format], filename