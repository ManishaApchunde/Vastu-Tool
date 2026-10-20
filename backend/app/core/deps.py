from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError, NotFound
from app.core.security import decode_access_token
from app.models import FloorPlan, Project, Report, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if not creds:
        raise AppError("unauthorized", "Sign in to continue.", 401)
    user_id = decode_access_token(creds.credentials)
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise AppError("unauthorized", "Your session has expired. Sign in again.", 401)
    return user


# Ownership helpers: a resource owned by someone else is reported as "not found" so IDs don't leak.
def owned_project(db: Session, project_id: str, user: User) -> Project:
    project = db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise NotFound("Project")
    return project


def owned_floor_plan(db: Session, floor_plan_id: str, user: User) -> FloorPlan:
    fp = db.get(FloorPlan, floor_plan_id)
    if not fp or fp.project.owner_id != user.id:
        raise NotFound("Floor plan")
    return fp


def owned_report(db: Session, report_id: str, user: User) -> Report:
    report = db.get(Report, report_id)
    if not report or report.project.owner_id != user.id:
        raise NotFound("Report")
    return report
