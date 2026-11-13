from fastapi import APIRouter
from sqlalchemy import func, select
from app.api.deps import CurrentUser, DbSession
from app.db.models import Dataset, GenerationJob

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
async def overview(user: CurrentUser, db: DbSession):
    dataset_count = await db.scalar(select(func.count(Dataset.id)).where(Dataset.owner_id == user.id)) or 0
    jobs = (await db.scalars(select(GenerationJob).join(Dataset).where(Dataset.owner_id == user.id))).all()
    return {
        "dataset_count": dataset_count,
        "generation_jobs": len(jobs),
        "completed_jobs": sum(job.status == "completed" for job in jobs),
        "failed_jobs": sum(job.status == "failed" for job in jobs),
        "generated_records": sum(job.generated_records for job in jobs),
        "estimated_cost_usd": sum(float(job.usage.get("estimated_cost_usd", 0)) for job in jobs),
    }

