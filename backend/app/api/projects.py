from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user, owned_project
from app.core.errors import AppError
from app.models import Project, Property, Report, User
from app.reports.service import start_report
from app.schemas.inputs import ProjectIn, ReportIn
from app.services import pipeline
from app.services.serializers import analysis_out, floor_plan_out, project_out, report_out

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.scalars(select(Project).where(Project.owner_id == user.id).order_by(Project.updated_at.desc()))
    return [project_out(db, p) for p in projects]


@router.post("", status_code=201)
def create_project(body: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = Project(owner_id=user.id, name=body.name.strip(), description=body.description)
    prop = body.property.model_dump()
    prop["name"] = prop.get("name") or project.name
    project.property = Property(**prop)
    db.add(project)
    db.commit()
    return project_out(db, project, detail=True)


@router.post("/demo", status_code=201)
def create_demo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.seed.seed import create_demo_project

    return project_out(db, create_demo_project(db, user), detail=True)


@router.get("/{project_id}")
def get_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return project_out(db, owned_project(db, project_id, user), detail=True)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(owned_project(db, project_id, user))
    db.commit()


@router.post("/{project_id}/floor-plan", status_code=201)
async def upload_floor_plan(project_id: str, background: BackgroundTasks, file: UploadFile = File(...),
                            analyze: bool = True, user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    project = owned_project(db, project_id, user)
    # Read with a hard cap so an oversized upload never fills memory.
    data = await file.read(settings.max_upload_bytes + 1)
    fp = pipeline.create_floor_plan(db, project, file.filename or "upload", data)
    if analyze:
        pipeline.start_detection(db, fp, user, background)
    return floor_plan_out(db, fp)


def _latest_analysis(project: Project):
    if not project.analyses:
        raise AppError("no_analysis", "This project has not been analysed yet.", 404,
                       "Verify the plan, set North and run the analysis.")
    return project.analyses[-1]


@router.get("/{project_id}/analysis")
def get_analysis(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analysis_out(db, _latest_analysis(owned_project(db, project_id, user)))


@router.get("/{project_id}/findings")
def get_findings(project_id: str, bucket: str | None = None, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    data = analysis_out(db, _latest_analysis(owned_project(db, project_id, user)))
    return [f for f in data["findings"] if bucket is None or f["bucket"] == bucket]


@router.get("/{project_id}/remedies")
def get_remedies(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analysis_out(db, _latest_analysis(owned_project(db, project_id, user)))["remedies"]


@router.post("/{project_id}/report", status_code=202)
def create_report(project_id: str, background: BackgroundTasks, body: ReportIn | None = Body(default=None),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    language = body.language if body else "en"
    report = start_report(db, owned_project(db, project_id, user), user, background, language=language,
                          include_action_plan=body.include_action_plan if body else True)
    return report_out(db, report)


@router.get("/{project_id}/reports")
def list_reports(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = owned_project(db, project_id, user)
    reports = db.scalars(select(Report).where(Report.project_id == project.id).order_by(Report.created_at.desc()))
    return [report_out(db, r) for r in reports]
