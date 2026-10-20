from app.services.jobs import execute_job
from app.workers.celery_app import celery_app


@celery_app.task(name="vastu.execute_job")
def execute_job_task(job_id: str) -> None:
    # Failures are recorded on the job row; users retry via POST /jobs/{id}/retry.
    execute_job(job_id)
