"""Background job lifecycle. Jobs are rows in processing_jobs so status, errors and retries are
visible to the user regardless of the queue backend.

JOB_MODE=inline  -> runs in FastAPI's background task threadpool (no Redis needed)
JOB_MODE=celery  -> enqueued to Celery/Redis; worker calls execute_job()"""
import logging
from collections.abc import Callable

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.errors import AppError
from app.models import ProcessingJob
from app.models.base import utcnow

log = logging.getLogger("vastu.jobs")
HANDLERS: dict[str, Callable[[Session, ProcessingJob], dict]] = {}


def handler(kind: str):
    def deco(fn):
        HANDLERS[kind] = fn
        return fn
    return deco


def create_job(db: Session, *, kind: str, owner_id: str, project_id: str, floor_plan_id: str | None = None,
               payload: dict | None = None) -> ProcessingJob:
    job = ProcessingJob(kind=kind, owner_id=owner_id, project_id=project_id, floor_plan_id=floor_plan_id,
                        payload=payload or {}, max_attempts=settings.job_max_attempts)
    db.add(job)
    db.commit()
    return job


def dispatch(job: ProcessingJob, background: BackgroundTasks | None = None) -> None:
    if settings.job_mode == "celery":
        from app.workers.tasks import execute_job_task

        execute_job_task.delay(job.id)
    elif background is not None:
        background.add_task(execute_job, job.id)
    else:
        execute_job(job.id)


def execute_job(job_id: str) -> None:
    # Handlers must be imported so their @handler decorators register.
    from app.reports import service as _reports  # noqa: F401
    from app.services import pipeline as _pipeline  # noqa: F401
    from app.videos import service as _videos  # noqa: F401

    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None or job.status == "succeeded":
            return
        job.status, job.attempts, job.started_at = "running", job.attempts + 1, utcnow()
        job.error = job.error_code = None
        db.commit()
        try:
            job.result = HANDLERS[job.kind](db, job)
            job.status = "succeeded"
        except AppError as exc:
            db.rollback()
            job.status, job.error_code, job.error = "failed", exc.code, exc.message
            _on_failure(db, job)
        except Exception as exc:  # noqa: BLE001 - surface any failure on the job row
            log.exception("job %s failed", job_id)
            db.rollback()
            job.status, job.error_code = "failed", "internal_error"
            job.error = "Processing failed unexpectedly. Retry, or contact support if it keeps failing."
            _on_failure(db, job, exc)
        job.finished_at = utcnow()
        db.commit()


def _on_failure(db: Session, job: ProcessingJob, exc: Exception | None = None) -> None:
    from app.models import FloorPlan, FloorPlanStatus, Report, ReportVideo

    if job.kind == "detection" and job.floor_plan_id:
        fp = db.get(FloorPlan, job.floor_plan_id)
        if fp and fp.status == FloorPlanStatus.PROCESSING:
            fp.status = FloorPlanStatus.DETECTION_FAILED
    if job.kind == "report" and job.payload.get("report_id"):
        report = db.get(Report, job.payload["report_id"])
        if report:
            report.status, report.error = "failed", job.error
    if job.kind == "video" and job.payload.get("video_id"):
        video = db.get(ReportVideo, job.payload["video_id"])
        if video:
            video.status, video.error = "failed", job.error


def retry(db: Session, job: ProcessingJob, background: BackgroundTasks | None = None) -> ProcessingJob:
    if job.status != "failed":
        raise AppError("job_not_failed", "Only failed jobs can be retried.", 409)
    if job.attempts >= job.max_attempts:
        raise AppError("retry_limit", "This job has reached its retry limit.", 409,
                       "Upload the plan again or verify it manually.")
    job.status = "queued"
    db.commit()
    dispatch(job, background)
    return job
