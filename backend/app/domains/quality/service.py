from collections import Counter
from typing import Any
from app.schemas import DatasetSpecification


def evaluate_records(records: list[dict[str, Any]], specification: DatasetSpecification) -> dict[str, Any]:
    required = [column.name for column in specification.columns if column.required]
    missing = [index for index, row in enumerate(records) if any(row.get(key) in (None, "") for key in required)]
    fingerprints = [repr(sorted(row.items())) for row in records]
    duplicate_count = len(fingerprints) - len(set(fingerprints))
    label_column = next((c.name for c in specification.columns if c.name in {"label", "sentiment", "intent"}), None)
    distribution = Counter(row.get(label_column) for row in records) if label_column else {}
    valid_count = len(records) - len(missing)
    return {
        "record_count": len(records),
        "valid_record_count": valid_count,
        "missing_required_records": len(missing),
        "duplicate_records": duplicate_count,
        "label_distribution": dict(distribution),
        "quality_score": round(
            max(
                0,
                100
                - (len(missing) * 100 / max(1, len(records)))
                - (duplicate_count * 20 / max(1, len(records))),
            ),
            2,
        ),
        "disclaimer": "These checks assess internal quality only. They do not establish statistical representativeness of any real population.",
    }
