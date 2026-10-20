"""Video report job: report model -> scenes -> slides + narration -> MP4 with subtitles."""
import logging
import re
import tempfile
from pathlib import Path

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models import Analysis, FloorPlan, Project, ReportVideo, User
from app.models.base import utcnow
from app.reports.i18n import LANGUAGE_NAMES, LANGUAGES
from app.services import jobs
from app.services.storage import get_storage

log = logging.getLogger("vastu.video")


def start_video(db: Session, project: Project, user: User, background: BackgroundTasks | None = None,
                language: str = "en") -> ReportVideo:
    if not project.analyses:
        raise AppError("no_analysis", "Run the Vastu analysis before creating a video.", 409)
    if language not in LANGUAGES:
        raise AppError("invalid_language", f"Unsupported language '{language}'.", 422)
    video = ReportVideo(project_id=project.id, analysis_id=project.analyses[-1].id, language=language,
                        status="queued", progress=0)
    db.add(video)
    db.commit()
    job = jobs.create_job(db, kind="video", owner_id=user.id, project_id=project.id, payload={"video_id": video.id})
    video.job_id = job.id
    db.commit()
    jobs.dispatch(job, background)
    return video


def _cues(text: str, start: float, seconds: float) -> list[tuple[float, float, str]]:
    """Splits a scene's narration into subtitle lines timed by length within its audio."""
    parts = []
    for sent in re.split(r"(?<=[.।!?])\s+", text.strip()):
        while len(sent) > 110:
            cut = max(sent.rfind(", ", 0, 100), sent.rfind("; ", 0, 100), sent.rfind(": ", 0, 100))
            cut = cut if cut > 30 else sent.rfind(" ", 0, 100)
            parts.append(sent[:cut + 1].strip())
            sent = sent[cut + 1:].strip()
        if sent:
            parts.append(sent)
    total = sum(len(p) for p in parts) or 1
    out, t = [], start
    for p in parts:
        d = seconds * len(p) / total
        out.append((t, t + d, p))
        t += d
    return out


@jobs.handler("video")
def generate_video(db: Session, job) -> dict:
    from app.insights.context import Ctx
    from app.insights.voice import speakable
    from app.reports.action_plan import build_action_plan
    from app.reports.plan_render import render_report_plan
    from app.reports.report_data import build_report_data
    from app.videos.compose import VideoError, captions, join, segment
    from app.videos.script import build_scenes
    from app.videos.slides import render_slide
    from app.videos.tts import TTSUnavailable, pick_narrator

    video = db.get(ReportVideo, job.payload["video_id"])
    if video is None:
        raise AppError("not_found", "Video was deleted.", 404)
    video.status, video.progress, video.error = "running", 1, None
    db.commit()
    analysis = db.get(Analysis, video.analysis_id)
    project = db.get(Project, video.project_id)
    fp = db.get(FloorPlan, analysis.floor_plan_id)
    storage = get_storage()
    lang = video.language
    name = LANGUAGE_NAMES[lang]
    try:
        data = build_report_data(db, analysis, project, language=lang)
        ap = build_action_plan(Ctx(db, project, analysis, language=lang), lang)
        scenes = build_scenes(data, ap, lang)
        image = storage.get(fp.preview_key)
        plan_png = render_report_plan(image, data)
        room_ids = {s.data["room_id"] for s in scenes if s.kind == "room"}
        thumbs = {r["id"]: render_report_plan(image, data, highlight=r["id"], max_side=1100)
                  for r in data["rooms"] if r["id"] in room_ids}
        with tempfile.TemporaryDirectory(prefix="vastu-video-") as tmp:
            work = Path(tmp)
            narrator = pick_narrator(speakable(scenes[0].narration, lang), lang, work)
            segs, cues, transcript, t = [], [], [], 0.0
            for i, sc in enumerate(scenes):
                wav = work / f"s{i:02d}.wav"
                seconds = narrator.synth(speakable(sc.narration, lang), lang, wav)
                scene_cues = _cues(sc.narration, 0.0, seconds)
                frames = []
                for j, (a, b, text) in enumerate(scene_cues if settings.video_burn_captions else [(0, seconds, None)]):
                    png = work / f"s{i:02d}-{j:02d}.png"
                    png.write_bytes(render_slide(sc, i, len(scenes), language=lang, brand=data["brand"],
                                                 name=data["property"]["name"], plan_png=plan_png, thumbs=thumbs,
                                                 caption=text))
                    frames.append((png, b - a))
                seg = work / f"s{i:02d}.mp4"
                length = segment(frames, wav, seconds, seg, work)
                cues += [(t + a, t + b, text) for a, b, text in scene_cues]
                transcript.append({"title": sc.title, "start": round(t, 1), "text": sc.narration})
                if i == 0:
                    poster = render_slide(sc, 0, len(scenes), language=lang, brand=data["brand"],
                                          name=data["property"]["name"], plan_png=plan_png, thumbs=thumbs)
                segs.append(seg)
                t += length
                video.progress = 5 + int(85 * (i + 1) / len(scenes))
                db.commit()
            srt, vtt = captions(cues)
            (work / "subs.srt").write_text(srt, encoding="utf-8")
            out = work / "video.mp4"
            join(segs, work / "subs.srt", lang, out, work)
            base = f"users/{project.owner_id}/projects/{project.id}/videos/{video.id}"
            storage.put(f"{base}.mp4", out.read_bytes(), "video/mp4")
            storage.put(f"{base}.srt", srt.encode("utf-8"), "application/x-subrip")
            storage.put(f"{base}.vtt", vtt.encode("utf-8"), "text/vtt")
            storage.put(f"{base}-poster.png", poster, "image/png")
    except TTSUnavailable as exc:
        raise AppError("narration_failed", f"The {name} narration voice stopped responding.", 502,
                       "Check the internet connection and retry; or set VIDEO_TTS=silent for a captioned video.") from exc
    except VideoError as exc:
        log.error("video %s: ffmpeg failed: %s", video.id, exc)
        raise AppError("video_failed", "The video could not be assembled.", 500, "Retry the video.") from exc
    video.storage_key, video.subtitles_key = f"{base}.mp4", f"{base}.srt"
    video.captions_key, video.poster_key = f"{base}.vtt", f"{base}-poster.png"
    video.narration, video.duration_seconds, video.scenes = narrator.name, round(t, 1), len(scenes)
    video.transcript, video.status, video.progress = transcript, "ready", 100
    video.updated_at = utcnow()
    db.commit()
    return {"video_id": video.id, "seconds": video.duration_seconds, "narration": narrator.name}
