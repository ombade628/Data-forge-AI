from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.db.models import Dataset, GenerationJob
from app.domains.generation.service import run_generation_job
from app.schemas import GenerationJobRead, GenerationRequest

router = APIRouter(tags=["generation"])


async def get_owned_dataset(dataset_id: UUID, user: CurrentUser, db: DbSession) -> Dataset:
    dataset = await db.scalar(select(Dataset).where(Dataset.id == dataset_id, Dataset.owner_id == user.id))
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.post("/datasets/{dataset_id}/generate", response_model=GenerationJobRead, status_code=status.HTTP_202_ACCEPTED)
async def generate(dataset_id: UUID, payload: GenerationRequest, user: CurrentUser, db: DbSession):
    await get_owned_dataset(dataset_id, user, db)
    job = GenerationJob(dataset_id=dataset_id, requested_by_id=user.id, requested_records=payload.record_count, model_name=get_settings().llm_model)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    if get_settings().job_execution == "celery":
        from app.workers.tasks import execute_generation
        execute_generation.delay(str(job.id))
    else:
        await run_generation_job(str(job.id))
        await db.refresh(job)
    return job


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobRead)
async def get_job(job_id: UUID, user: CurrentUser, db: DbSession):
    job = await db.scalar(select(GenerationJob).join(Dataset).where(GenerationJob.id == job_id, Dataset.owner_id == user.id))
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")
    return job

