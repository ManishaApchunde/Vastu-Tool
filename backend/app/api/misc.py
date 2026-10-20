import mimetypes

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, owned_report
from app.core.errors import AppError, NotFound
from app.core.security import verify_file_signature
from app.models import ProcessingJob, User
from app.services import jobs
from app.services.serializers import job_out, report_out
from app.services.storage import LocalStorage, get_storage

router = APIRouter(tags=["reports", "jobs", "files"])


@router.get("/reports/{report_id}")
def get_report(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return report_out(db, owned_report(db, report_id, user))


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(ProcessingJob, job_id)
    if not job or job.owner_id != user.id:
        raise NotFound("Job")
    return job_out(job)


@router.post("/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, background: BackgroundTasks, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    job = db.get(ProcessingJob, job_id)
    if not job or job.owner_id != user.id:
        raise NotFound("Job")
    if job.kind == "detection" and job.floor_plan_id:
        from app.models import FloorPlan, FloorPlanStatus

        fp = db.get(FloorPlan, job.floor_plan_id)
        if fp and fp.status == FloorPlanStatus.DETECTION_FAILED:
            fp.status = FloorPlanStatus.PROCESSING
    if job.kind == "video" and job.payload.get("video_id"):
        from app.models import ReportVideo

        video = db.get(ReportVideo, job.payload["video_id"])
        if video:
            video.status, video.error, video.progress = "queued", None, 0
    if job.kind == "report" and job.payload.get("report_id"):
        from app.models import Report

        report = db.get(Report, job.payload["report_id"])
        if report:
            report.status, report.error = "queued", None
    return job_out(jobs.retry(db, job, background))


@router.get("/files/{key:path}")
def serve_file(key: str, exp: int, sig: str, request: Request, name: str | None = None):
    """Serves local-storage files behind an HMAC-signed, expiring URL (S3 uses presigned URLs)."""
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise NotFound("File")
    if not verify_file_signature(key, exp, sig):
        raise AppError("link_expired", "This link has expired. Reload the page to get a new one.", 403)
    data = storage.get(key)
    media = {".vtt": "text/vtt", ".srt": "application/x-subrip"}.get(key[key.rfind("."):]) \
        or mimetypes.guess_type(key)[0] or "application/octet-stream"
    headers = {"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff", "Accept-Ranges": "bytes"}
    if name:
        headers["Content-Disposition"] = f'attachment; filename="{name}"'
    # Byte ranges let the browser's video player seek.
    rng = request.headers.get("range", "")
    if rng.startswith("bytes=") and "," not in rng:
        start_s, _, end_s = rng[6:].partition("-")
        try:
            start = int(start_s) if start_s else max(0, len(data) - int(end_s))
            end = min(int(end_s), len(data) - 1) if start_s and end_s else len(data) - 1
        except ValueError:
            start, end = 0, len(data) - 1
        if start >= len(data) or start > end:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{len(data)}"})
        headers["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
        return Response(data[start:end + 1], status_code=206, media_type=media, headers=headers)
    return Response(data, media_type=media, headers=headers)
