import logging

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Analysis, FloorPlan, Project, Report, User
from app.models.base import utcnow
from app.reports.i18n import LANGUAGES, LANGUAGE_NAMES
from app.reports.pdf import build_pdf
from app.reports.plan_render import render_report_plan
from app.reports.report_data import build_report_data
from app.services import jobs
from app.services.storage import get_storage

log = logging.getLogger(__name__)


def start_report(db: Session, project: Project, user: User, background: BackgroundTasks | None = None,
                 language: str = "en", include_action_plan: bool = True) -> Report:
    if not project.analyses:
        raise AppError("no_analysis", "Run the Vastu analysis before generating a report.", 409)
    analysis = project.analyses[-1]
    if language not in LANGUAGES:
        raise AppError("invalid_language", f"Unsupported report language '{language}'.", 422,
                       f"Use one of: {', '.join(LANGUAGES)}.")
    report = Report(project_id=project.id, analysis_id=analysis.id, status="queued", language=language,
                    options={"action_plan": include_action_plan})
    db.add(report)
    db.commit()
    job = jobs.create_job(db, kind="report", owner_id=user.id, project_id=project.id,
                          payload={"report_id": report.id})
    report.job_id = job.id
    db.commit()
    jobs.dispatch(job, background)
    return report


@jobs.handler("report")
def generate_report(db: Session, job) -> dict:
    report = db.get(Report, job.payload["report_id"])
    if report is None:
        raise AppError("not_found", "Report was deleted.", 404)
    report.status = "running"
    db.commit()
    analysis = db.get(Analysis, report.analysis_id)
    project = db.get(type(report.project), report.project_id)
    fp = db.get(FloorPlan, analysis.floor_plan_id)
    storage = get_storage()
    image = storage.get(fp.preview_key)
    language = report.language or "en"
    try:
        # Analysis -> report model -> images -> PDF. The renderer only lays out the report model.
        # Language only changes wording: the analysis, scores and findings are read, never recomputed.
        data = build_report_data(db, analysis, project, language=language)
        if (report.options or {}).get("action_plan"):
            from app.insights.context import Ctx
            from app.reports.action_plan import build_action_plan

            data["action_plan"] = build_action_plan(Ctx(db, project, analysis, language=language), language)
        plan_png = render_report_plan(image, data)
        thumbs = {r["id"]: render_report_plan(image, data, highlight=r["id"], max_side=900) for r in data["rooms"]}
        pdf = build_pdf(data, plan_png, thumbs, language=language)
    except Exception as exc:  # noqa: BLE001
        if language == "en":
            raise AppError("pdf_failed", "The PDF could not be generated.", 500, "Retry the report.") from exc
        log.exception("%s report %s failed", language, report.id)
        raise AppError("pdf_failed", f"The {LANGUAGE_NAMES[language]} PDF could not be generated.", 500,
                       "Retry, or download the English PDF instead.") from exc
    key = f"users/{project.owner_id}/projects/{project.id}/reports/{report.id}.pdf"  # id is unique per language
    storage.put(key, pdf, "application/pdf")
    report.storage_key, report.status, report.error = key, "ready", None
    report.updated_at = utcnow()
    db.commit()
    return {"report_id": report.id, "bytes": len(pdf)}
