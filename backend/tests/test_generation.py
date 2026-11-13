from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Dataset, GenerationJob
from app.domains.generation.service import run_generation_job

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


async def _create_dataset(client, headers):
    resp = await client.post(
        "/api/v1/datasets",
        headers=headers,
        json={"name": "Gen Test", "description": None, "specification": SUPPORT_SPEC},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _user_id(client, headers) -> UUID:
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    return UUID(resp.json()["id"])


async def _make_job(test_engine, dataset_id, user_id, status="queued", requested=3):
    Session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with Session() as db:
        job = GenerationJob(
            dataset_id=UUID(dataset_id),
            requested_by_id=user_id,
            requested_records=requested,
            model_name="local-template-generator",
            status=status,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return str(job.id)


@pytest.mark.asyncio
async def test_generate_endpoint_inline_creates_version(client, registered_user):
    ds = await _create_dataset(client, registered_user["headers"])

    resp = await client.post(
        f"/api/v1/datasets/{ds['id']}/generate",
        headers=registered_user["headers"],
        json={"record_count": 5},
    )
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["status"] == "completed"
    assert job["generated_records"] == 5

    versions_resp = await client.get(
        f"/api/v1/datasets/{ds['id']}/versions",
        headers=registered_user["headers"],
    )
    versions = versions_resp.json()
    assert len(versions) == 1
    v = versions[0]
    assert v["version_number"] == 1
    assert v["record_count"] == 5
    assert v["quality_report"]["record_count"] == 5
    assert v["quality_report"]["quality_score"] == 100


@pytest.mark.asyncio
async def test_generate_endpoint_rejects_unauthenticated(client, registered_user):
    ds = await _create_dataset(client, registered_user["headers"])
    resp = await client.post(
        f"/api/v1/datasets/{ds['id']}/generate",
        json={"record_count": 5},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_generate_endpoint_cross_tenant_returns_404(
    client, registered_user, other_user
):
    ds = await _create_dataset(client, registered_user["headers"])
    resp = await client.post(
        f"/api/v1/datasets/{ds['id']}/generate",
        headers=other_user["headers"],
        json={"record_count": 5},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_rejects_zero_records(client, registered_user):
    ds = await _create_dataset(client, registered_user["headers"])
    resp = await client.post(
        f"/api/v1/datasets/{ds['id']}/generate",
        headers=registered_user["headers"],
        json={"record_count": 0},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_run_generation_job_is_idempotent(client, registered_user):
    """The Step 5 fix: a second run of a completed job must not create a second version."""
    ds = await _create_dataset(client, registered_user["headers"])
    resp = await client.post(
        f"/api/v1/datasets/{ds['id']}/generate",
        headers=registered_user["headers"],
        json={"record_count": 3},
    )
    job_id = resp.json()["id"]

    # Second call — should be a no-op because status is "completed".
    await run_generation_job(job_id)

    versions = await client.get(
        f"/api/v1/datasets/{ds['id']}/versions",
        headers=registered_user["headers"],
    )
    assert len(versions.json()) == 1


@pytest.mark.asyncio
async def test_run_generation_job_skips_running_jobs(
    client, registered_user, test_engine
):
    """The Step 5 fix: a job with status 'running' belongs to another worker."""
    ds = await _create_dataset(client, registered_user["headers"])
    user_id = await _user_id(client, registered_user["headers"])
    job_id = await _make_job(test_engine, ds["id"], user_id, status="running")

    await run_generation_job(job_id)

    versions = await client.get(
        f"/api/v1/datasets/{ds['id']}/versions",
        headers=registered_user["headers"],
    )
    assert versions.json() == []


@pytest.mark.asyncio
async def test_run_generation_job_unknown_id_is_noop(client):
    """A worker restarting while messages are stale must not crash on missing jobs."""
    await run_generation_job("00000000-0000-0000-0000-000000000000")


@pytest.mark.asyncio
async def test_run_generation_job_marks_failed_when_dataset_deleted(
    client, registered_user, test_engine
):
    """If the dataset is deleted between queueing and running, the job fails cleanly."""
    ds = await _create_dataset(client, registered_user["headers"])
    user_id = await _user_id(client, registered_user["headers"])
    job_id = await _make_job(test_engine, ds["id"], user_id, status="queued")

    Session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with Session() as db:
        # SQLite does not enforce FK constraints by default, so this delete succeeds.
        # On Postgres you would see a constraint error here; the production code path
        # is defensive against both cases.
        dataset = await db.get(Dataset, UUID(ds["id"]))
        await db.delete(dataset)
        await db.commit()

    await run_generation_job(job_id)

    async with Session() as db:
        job = await db.get(GenerationJob, UUID(job_id))
        assert job.status == "failed"
        assert "no longer exists" in (job.error_message or "").lower()


@pytest.mark.asyncio
async def test_generation_job_not_found_returns_404(client, registered_user):
    resp = await client.get(
        "/api/v1/generation-jobs/00000000-0000-0000-0000-000000000000",
        headers=registered_user["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generation_job_cross_tenant_returns_404(
    client, registered_user, other_user
):
    ds = await _create_dataset(client, registered_user["headers"])
    resp = await client.post(
        f"/api/v1/datasets/{ds['id']}/generate",
        headers=registered_user["headers"],
        json={"record_count": 2},
    )
    job_id = resp.json()["id"]

    resp = await client.get(
        f"/api/v1/generation-jobs/{job_id}", headers=other_user["headers"]
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_analytics_overview_aggregates(client, registered_user):
    ds = await _create_dataset(client, registered_user["headers"])
    await client.post(
        f"/api/v1/datasets/{ds['id']}/generate",
        headers=registered_user["headers"],
        json={"record_count": 4},
    )

    resp = await client.get(
        "/api/v1/analytics/overview", headers=registered_user["headers"]
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset_count"] == 1
    assert body["generation_jobs"] == 1
    assert body["completed_jobs"] == 1
    assert body["failed_jobs"] == 0
    assert body["generated_records"] == 4


@pytest.mark.asyncio
async def test_prompt_analyze_returns_local_spec(client, registered_user):
    resp = await client.post(
        "/api/v1/prompts/analyze",
        headers=registered_user["headers"],
        json={
            "prompt": "Generate 20 customer support conversations in English and Hindi",
            "record_count": 100,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "local"
    assert body["specification"]["dataset_type"] == "customer_support"
    assert body["suggested_record_count"] == 20
    assert "Hindi" in body["specification"]["languages"]


@pytest.mark.asyncio
async def test_prompt_analyze_rejects_unauthenticated(client):
    resp = await client.post(
        "/api/v1/prompts/analyze",
        json={"prompt": "Generate 20 things", "record_count": 10},
    )
    assert resp.status_code == 401