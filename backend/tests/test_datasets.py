import pytest

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


async def _create_dataset(client, headers, name="Test DS", spec=SUPPORT_SPEC):
    resp = await client.post(
        "/api/v1/datasets",
        headers=headers,
        json={"name": name, "description": "test", "specification": spec},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_create_dataset_returns_persisted_spec(client, registered_user):
    body = await _create_dataset(client, registered_user["headers"])
    assert body["name"] == "Test DS"
    assert body["status"] == "draft"
    assert body["specification"]["dataset_type"] == "customer_support"


@pytest.mark.asyncio
async def test_create_dataset_rejects_duplicate_columns(client, registered_user):
    bad_spec = {
        "dataset_type": "custom",
        "languages": ["English"],
        "columns": [
            {"name": "id", "data_type": "integer", "description": "", "required": True, "allowed_values": []},
            {"name": "id", "data_type": "string", "description": "", "required": True, "allowed_values": []},
        ],
        "constraints": [],
    }
    resp = await client.post(
        "/api/v1/datasets",
        headers=registered_user["headers"],
        json={"name": "Bad", "description": None, "specification": bad_spec},
    )
    assert resp.status_code == 422
    assert "Duplicate column" in resp.text


@pytest.mark.asyncio
async def test_list_datasets_only_returns_own(client, registered_user, other_user):
    await _create_dataset(client, registered_user["headers"], name="Alice DS")
    await _create_dataset(client, other_user["headers"], name="Bob DS")

    resp = await client.get("/api/v1/datasets", headers=registered_user["headers"])
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()]
    assert names == ["Alice DS"]


@pytest.mark.asyncio
async def test_list_datasets_pagination(client, registered_user):
    for i in range(3):
        await _create_dataset(client, registered_user["headers"], name=f"DS {i}")

    resp = await client.get(
        "/api/v1/datasets?limit=2&offset=0", headers=registered_user["headers"]
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = await client.get(
        "/api/v1/datasets?limit=2&offset=2", headers=registered_user["headers"]
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_dataset_cross_tenant_returns_404(client, registered_user, other_user):
    ds = await _create_dataset(client, registered_user["headers"])

    resp = await client.get(
        f"/api/v1/datasets/{ds['id']}", headers=other_user["headers"]
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_versions_cross_tenant_returns_404(client, registered_user, other_user):
    ds = await _create_dataset(client, registered_user["headers"])

    resp = await client.get(
        f"/api/v1/datasets/{ds['id']}/versions", headers=other_user["headers"]
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_preview_records_cross_tenant_returns_404(client, registered_user, other_user):
    ds = await _create_dataset(client, registered_user["headers"])

    resp = await client.get(
        f"/api/v1/datasets/{ds['id']}/versions/00000000-0000-0000-0000-000000000000/records",
        headers=other_user["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_versions_are_empty_before_generation(client, registered_user):
    ds = await _create_dataset(client, registered_user["headers"])
    resp = await client.get(
        f"/api/v1/datasets/{ds['id']}/versions", headers=registered_user["headers"]
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_dataset_requires_auth(client):
    resp = await client.post(
        "/api/v1/datasets",
        json={"name": "x", "description": None, "specification": SUPPORT_SPEC},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_edit_record_rejects_unknown_fields(client, registered_user, test_engine):
    """Guards Step 6: record edits must match the schema exactly."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models import DatasetVersion

    ds = await _create_dataset(client, registered_user["headers"])

    # Directly insert a version to test edit_record without running full generation.
    Session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with Session() as db:
        version = DatasetVersion(
            dataset_id=ds["id"],
            version_number=1,
            schema_definition=SUPPORT_SPEC,
            records=[
                {"id": 1, "customer_query": "hi", "sentiment": "positive"},
                {"id": 2, "customer_query": "hello", "sentiment": "neutral"},
            ],
            record_count=2,
            quality_report={},
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
        version_id = str(version.id)

    bad_payload = {
        "id": 1,
        "customer_query": "hi",
        "sentiment": "positive",
        "unexpected_field": "boom",
    }
    resp = await client.patch(
        f"/api/v1/datasets/{ds['id']}/versions/{version_id}/records/0",
        headers=registered_user["headers"],
        json=bad_payload,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_edit_record_rejects_invalid_allowed_value(client, registered_user, test_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models import DatasetVersion

    ds = await _create_dataset(client, registered_user["headers"])

    Session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with Session() as db:
        version = DatasetVersion(
            dataset_id=ds["id"],
            version_number=1,
            schema_definition=SUPPORT_SPEC,
            records=[{"id": 1, "customer_query": "hi", "sentiment": "positive"}],
            record_count=1,
            quality_report={},
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
        version_id = str(version.id)

    resp = await client.patch(
        f"/api/v1/datasets/{ds['id']}/versions/{version_id}/records/0",
        headers=registered_user["headers"],
        json={"id": 1, "customer_query": "hi", "sentiment": "purple"},
    )
    assert resp.status_code == 422
    assert "one of" in resp.text


@pytest.mark.asyncio
async def test_edit_record_rejects_wrong_type(client, registered_user, test_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models import DatasetVersion

    ds = await _create_dataset(client, registered_user["headers"])

    Session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with Session() as db:
        version = DatasetVersion(
            dataset_id=ds["id"],
            version_number=1,
            schema_definition=SUPPORT_SPEC,
            records=[{"id": 1, "customer_query": "hi", "sentiment": "positive"}],
            record_count=1,
            quality_report={},
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
        version_id = str(version.id)

    resp = await client.patch(
        f"/api/v1/datasets/{ds['id']}/versions/{version_id}/records/0",
        headers=registered_user["headers"],
        json={"id": "not-an-int", "customer_query": "hi", "sentiment": "positive"},
    )
    assert resp.status_code == 422
    assert "must be an integer" in resp.text


@pytest.mark.asyncio
async def test_edit_record_rejects_negative_index(client, registered_user):
    ds = await _create_dataset(client, registered_user["headers"])

    resp = await client.patch(
        f"/api/v1/datasets/{ds['id']}/versions/00000000-0000-0000-0000-000000000000/records/-1",
        headers=registered_user["headers"],
        json={"id": 1, "customer_query": "hi", "sentiment": "positive"},
    )
    # Path(ge=0) rejects -1 with 422 before the version lookup happens.
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_edit_record_creates_new_version(client, registered_user, test_engine):
    """Edits must never mutate the source version — they append a new one."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models import DatasetVersion

    ds = await _create_dataset(client, registered_user["headers"])

    Session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with Session() as db:
        version = DatasetVersion(
            dataset_id=ds["id"],
            version_number=1,
            schema_definition=SUPPORT_SPEC,
            records=[{"id": 1, "customer_query": "hi", "sentiment": "positive"}],
            record_count=1,
            quality_report={},
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
        version_id = str(version.id)

    resp = await client.patch(
        f"/api/v1/datasets/{ds['id']}/versions/{version_id}/records/0",
        headers=registered_user["headers"],
        json={"id": 1, "customer_query": "edited", "sentiment": "neutral"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version_number"] == 2
    assert body["record_count"] == 1

    # Source version is untouched.
    versions_resp = await client.get(
        f"/api/v1/datasets/{ds['id']}/versions", headers=registered_user["headers"]
    )
    versions = versions_resp.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert versions[1]["version_number"] == 1