from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Body, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, owned_project
from app.core.errors import NotFound
from app.models import ProcessingJob, ReportVideo, User
from app.services.serializers import iso, job_out
from app.services.storage import get_storage
from app.videos.service import start_video

router = APIRouter(tags=["videos"])


class VideoIn(BaseModel):
    language: Literal["en", "mr"] = "en"


def video_out(db: Session, v: ReportVideo) -> dict:
    s = get_storage()
    ready = v.status == "ready" and v.storage_key
    stem = f"vastu-video-{v.id[:8]}-{v.language}"
    latest = v.project.analyses[-1].id if v.project and v.project.analyses else None
    return {
        "id": v.id, "project_id": v.project_id, "analysis_id": v.analysis_id, "language": v.language,
        "status": v.status, "progress": v.progress or 0, "narration": v.narration,
        "duration_seconds": v.duration_seconds, "scenes": v.scenes, "error": v.error,
        "is_current": v.analysis_id == latest, "created_at": iso(v.created_at),
        "video_url": s.signed_url(v.storage_key, ttl=3600) if ready else None,
        "download_url": s.signed_url(v.storage_key, ttl=3600, download_name=f"{stem}.mp4") if ready else None,
        "subtitles_url": s.signed_url(v.subtitles_key, ttl=3600, download_name=f"{stem}.srt") if ready else None,
        "captions_url": s.signed_url(v.captions_key, ttl=3600) if ready else None,
        "poster_url": s.signed_url(v.poster_key, ttl=3600) if ready and v.poster_key else None,
        "transcript": v.transcript if ready else None,
        "job": job_out(db.get(ProcessingJob, v.job_id)) if v.job_id else None,
    }


@router.post("/projects/{project_id}/video", status_code=202)
def create_video(project_id: str, background: BackgroundTasks, body: VideoIn | None = Body(default=None),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    video = start_video(db, owned_project(db, project_id, user), user, background,
                        language=body.language if body else "en")
    return video_out(db, video)


@router.get("/projects/{project_id}/videos")
def list_videos(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = owned_project(db, project_id, user)
    rows = db.scalars(select(ReportVideo).where(ReportVideo.project_id == project.id)
                      .order_by(ReportVideo.created_at.desc()))
    return [video_out(db, v) for v in rows]


@router.get("/videos/{video_id}")
def get_video(video_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    v = db.get(ReportVideo, video_id)
    if not v or v.project.owner_id != user.id:
        raise NotFound("Video")
    return video_out(db, v)
