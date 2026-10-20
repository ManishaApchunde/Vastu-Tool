from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, owned_floor_plan
from app.models import User
from app.schemas.inputs import NorthIn, VerificationIn
from app.services import pipeline
from app.services.serializers import analysis_out, floor_plan_out, job_out
from app.vastu.room_types import ROOM_TYPES

router = APIRouter(tags=["floor-plans"])


@router.get("/room-types")
def room_types():
    return [{"value": k, "label": v} for k, v in ROOM_TYPES.items()]


@router.get("/floor-plans/{fp_id}")
def get_floor_plan(fp_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return floor_plan_out(db, owned_floor_plan(db, fp_id, user))


@router.post("/floor-plans/{fp_id}/analyze", status_code=202)
def analyze(fp_id: str, background: BackgroundTasks, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    fp = owned_floor_plan(db, fp_id, user)
    return job_out(pipeline.start_detection(db, fp, user, background))


@router.get("/floor-plans/{fp_id}/detection")
def detection(fp_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fp = owned_floor_plan(db, fp_id, user)
    out = floor_plan_out(db, fp, include_detection=True)
    return {"floor_plan_id": fp.id, "status": fp.status, "detection": out["detection"],
            "job": out["detection_job"], "quality": fp.quality}


@router.put("/floor-plans/{fp_id}/verification")
def verify(fp_id: str, body: VerificationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fp = pipeline.apply_verification(db, owned_floor_plan(db, fp_id, user), body)
    return floor_plan_out(db, fp)


@router.put("/floor-plans/{fp_id}/north")
def north(fp_id: str, body: NorthIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fp = owned_floor_plan(db, fp_id, user)
    pipeline.set_north(db, fp, body.north_angle, user)
    return floor_plan_out(db, fp)


@router.post("/floor-plans/{fp_id}/calculate-zones")
def calculate_zones(fp_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fp = owned_floor_plan(db, fp_id, user)
    pipeline.calculate_zones(db, fp)
    return floor_plan_out(db, fp)


@router.post("/floor-plans/{fp_id}/run-analysis")
def run_analysis(fp_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fp = owned_floor_plan(db, fp_id, user)
    return analysis_out(db, pipeline.run_analysis(db, fp))
