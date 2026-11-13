import uuid
from sqlalchemy import select
from app.ai.providers.factory import get_dataset_provider
from app.db.models import Dataset, DatasetVersion, GenerationJob
from app.db.session import SessionLocal
from app.domains.quality.service import evaluate_records
from app.schemas import DatasetSpecification


async def run_generation_job(job_id: str) -> None:
    """Run one idempotent job. Celery calls this function; inline development does too.

    Concurrency safety:
    - The job row is locked with ``SELECT ... FOR UPDATE`` before any status change,
      so two workers cannot both observe the job as ``queued`` and process it twice.
    - The ``DatasetVersion`` UNIQUE constraint on ``(dataset_id, version_number)`` is a
      hard backstop in case a future refactor removes the row lock.
    - ``running`` jobs are treated as in-flight and skipped; retries only re-enter
      ``queued`` or ``failed`` jobs.
    """
    async with SessionLocal() as db:
        # Lock the job row so a concurrent worker cannot pick up the same job.
        job = await db.scalar(
            select(GenerationJob)
            .where(GenerationJob.id == uuid.UUID(job_id))
            .with_for_update()
        )
        if not job:
            return
        if job.status in {"completed", "cancelled", "running"}:
            # Already processed or actively in-flight — idempotent no-op.
            return

        dataset = await db.get(Dataset, job.dataset_id)
        if not dataset:
            job.status = "failed"
            job.error_message = "Dataset no longer exists"
            await db.commit()
            return

        # Atomically claim the job. Commit releases the row lock so the next worker
        # sees status="running" and bails.
        job.status = "running"
        dataset.status = "generating"
        await db.commit()

        try:
            specification = DatasetSpecification.model_validate(dataset.specification)
            provider = get_dataset_provider()
            records = provider.generate(
                specification, job.requested_records, seed=job.id.int % 2**32
            )
            quality = evaluate_records(records, specification)

            latest = await db.scalar(
                select(DatasetVersion.version_number)
                .where(DatasetVersion.dataset_id == dataset.id)
                .order_by(DatasetVersion.version_number.desc())
                .limit(1)
            )
            version = DatasetVersion(
                dataset_id=dataset.id,
                version_number=(latest or 0) + 1,
                schema_definition=specification.model_dump(mode="json"),
                records=records,
                record_count=len(records),
                quality_report=quality,
            )
            db.add(version)
            job.status = "completed"
            job.generated_records = len(records)
            job.usage = {
                "provider": provider.name,
                "model": job.model_name,
                "estimated_tokens": 0,
                "estimated_cost_usd": 0,
            }
            dataset.status = "ready"
            await db.commit()
        except Exception as exc:  # keep actionable failure state for the user
            await db.rollback()
            # After rollback the identity map is cleared — re-fetch before updating.
            job = await db.get(GenerationJob, uuid.UUID(job_id))
            dataset = await db.get(Dataset, job.dataset_id) if job else None
            if job:
                job.status = "failed"
                job.error_message = str(exc)[:1000]
            if dataset:
                dataset.status = "failed"
            await db.commit()
            raise