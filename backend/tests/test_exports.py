import csv
import io
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.services.exports import MEDIA_TYPES, SUPPORTED_FORMATS, build_export

SUPPORT_SPEC = {
    "dataset_type": "customer_support",
    "languages": ["English"],
    "columns": [
        {"name": "id", "data_type": "integer", "description": "pk", "required": True, "allowed_values": []},
        {"name": "customer_query", "data_type": "string", "description": "", "required": True, "allowed_values": []},
        {
            "name": "sentiment",
            "data_type": "string",
            "description": "",
            "required": True,
            "allowed_values": ["positive", "neutral", "negative"],
        },
    ],
    "constraints": [],
}


async def _generate_version(client, headers):
    resp = await client.post(
        "/api/v1/datasets",
        headers=headers,
        json={"name": "Export Test", "description": None, "specification": SUPPORT_SPEC},
    )
    ds = resp.json()
    resp = await client.post(
        f"/api/v1/datasets/{ds['id']}/generate",
        headers=headers,
        json={"record_count": 3},
    )
    assert resp.status_code == 202, resp.text
    versions = await client.get(
        f"/api/v1/datasets/{ds['id']}/versions", headers=headers
    )
    return versions.json()[0]


@pytest.mark.asyncio
async def test_export_csv_round_trips(client, registered_user):
    version = await _generate_version(client, registered_user["headers"])

    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/export?format=csv",
        headers=registered_user["headers"],
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert f"dataforge-v{version['version_number']}.csv" in resp.headers["content-disposition"]

    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == version["record_count"]
    assert set(rows[0].keys()) == {"id", "customer_query", "sentiment"}
    assert rows[0]["id"] == "1"


@pytest.mark.asyncio
async def test_export_json_round_trips(client, registered_user):
    version = await _generate_version(client, registered_user["headers"])

    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/export?format=json",
        headers=registered_user["headers"],
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert f"dataforge-v{version['version_number']}.json" in resp.headers["content-disposition"]

    parsed = json.loads(resp.text)
    assert isinstance(parsed, list)
    assert len(parsed) == version["record_count"]
    assert set(parsed[0].keys()) == {"id", "customer_query", "sentiment"}


@pytest.mark.asyncio
async def test_export_jsonl_round_trips(client, registered_user):
    version = await _generate_version(client, registered_user["headers"])

    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/export?format=jsonl",
        headers=registered_user["headers"],
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")

    lines = [line for line in resp.text.splitlines() if line.strip()]
    assert len(lines) == version["record_count"]
    for line in lines:
        row = json.loads(line)
        assert set(row.keys()) == {"id", "customer_query", "sentiment"}


@pytest.mark.asyncio
async def test_export_xlsx_round_trips(client, registered_user):
    version = await _generate_version(client, registered_user["headers"])

    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/export?format=xlsx",
        headers=registered_user["headers"],
    )
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    assert f"dataforge-v{version['version_number']}.xlsx" in resp.headers["content-disposition"]

    workbook = load_workbook(io.BytesIO(resp.content))
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0] == ("id", "customer_query", "sentiment")
    assert len(rows) - 1 == version["record_count"]


@pytest.mark.asyncio
async def test_export_rejects_unsupported_format(client, registered_user):
    version = await _generate_version(client, registered_user["headers"])
    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/export?format=parquet",
        headers=registered_user["headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_export_cross_tenant_returns_404(client, registered_user, other_user):
    version = await _generate_version(client, registered_user["headers"])
    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/export?format=csv",
        headers=other_user["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_requires_auth(client, registered_user):
    version = await _generate_version(client, registered_user["headers"])
    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/export?format=csv"
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_export_does_not_write_to_disk(client, registered_user):
    """The Step 7 fix: exports must be built in memory, never persisted to data/exports/."""
    version = await _generate_version(client, registered_user["headers"])

    for fmt in SUPPORTED_FORMATS:
        resp = await client.get(
            f"/api/v1/dataset-versions/{version['id']}/export?format={fmt}",
            headers=registered_user["headers"],
        )
        assert resp.status_code == 200

    # The old code created data/exports/<uuid>.<fmt> for every request. That directory
    # (or any file under it) must not exist after a full pass through all formats.
    exports_dir = Path("data/exports")
    if exports_dir.exists():
        assert list(exports_dir.iterdir()) == [], (
            f"Exports leaked to disk: {list(exports_dir.iterdir())}"
        )


def test_build_export_returns_stream_and_filename():
    """Direct test of the service contract — tuple[BytesIO, str, str]."""
    records = [
        {"id": 1, "name": "a"},
        {"id": 2, "name": "b"},
    ]
    stream, media_type, filename = build_export(7, records, "csv")
    assert media_type == MEDIA_TYPES["csv"]
    assert filename == "dataforge-v7.csv"
    assert stream.tell() == 0  # already rewound

    content = stream.read().decode("utf-8")
    assert content.splitlines()[0] == "id,name"
    assert "1,a" in content
    assert "2,b" in content


def test_build_export_handles_empty_records():
    """An empty dataset is a valid export — header-only CSV, empty JSON array."""
    stream, _, _ = build_export(1, [], "json")
    assert stream.read() == b"[]"

    stream, _, _ = build_export(1, [], "csv")
    # No columns, so csv.DictWriter emits an empty header line then nothing.
    assert stream.read() == b"\r\n"


def test_build_export_rejects_unknown_format():
    with pytest.raises(ValueError, match="csv, json, jsonl, or xlsx"):
        build_export(1, [{"id": 1}], "parquet")