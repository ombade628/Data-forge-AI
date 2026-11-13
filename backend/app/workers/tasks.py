import asyncio
from app.domains.generation.service import run_generation_job
from app.workers.celery_app import celery_app


@celery_app.task(name="dataforge.execute_generation", bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def execute_generation(self, job_id: str):
    return asyncio.run(run_generation_job(job_id))

