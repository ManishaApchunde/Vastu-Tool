"""Customer insight tools (see app/insights). All read the latest analysis of a project you own,
except the public expert-review endpoints, which are reached with an unguessable, expiring token."""
import hashlib
import secrets
from datetime import timedelta

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, owned_floor_plan, owned_project
from app.core.errors import AppError, NotFound
from app.insights import common
from app.insights.context import Ctx
from app.insights.handoff import build_pack, review_out
from app.insights.history import analysis_view, compare, versions
from app.insights.mistakes import check_plan
from app.insights.postmove import evaluate_site
from app.insights.voice import voice_script
from app.models import Analysis, ExpertReview, FloorPlan, SiteVerification, User
from app.models.base import utcnow
from app.schemas.inputs import (
    ApplySiteIn, ExpertFeedbackIn, ExpertReviewIn, InsightContextIn, SiteVerificationIn, VerificationIn,
)
from app.services import pipeline
from app.services.serializers import analysis_out
from app.vastu.room_types import ROOM_TYPES

router = APIRouter(tags=["insights"])


def _ctx(db: Session, project_id: str, user: User) -> Ctx:
    return Ctx(db, owned_project(db, project_id, user))


def _meta(c: Ctx) -> dict:
    return {"analysis_id": c.analysis.id, "stale": c.stale}


# --- context settings (FitCheck constraints, family profile, construction stage) ----------------
@router.get("/projects/{project_id}/insights/context")
def get_context(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = owned_project(db, project_id, user).property
    return {"fit_constraints": p.fit_constraints if p else None, "family_profile": p.family_profile if p else None,
            "construction_stage": p.construction_stage if p else None}


@router.put("/projects/{project_id}/insights/context")
def put_context(project_id: str, body: InsightContextIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    project = owned_project(db, project_id, user)
    p = project.property
    if p is None:
        raise AppError("no_property", "This project has no property details.", 409)
    sent = body.model_fields_set
    if "fit_constraints" in sent:
        p.fit_constraints = body.fit_constraints.model_dump() if body.fit_constraints else None
    if "family_profile" in sent:
        p.family_profile = body.family_profile.model_dump() if body.family_profile else None
    if "construction_stage" in sent:
        p.construction_stage = body.construction_stage
    db.commit()
    return get_context(project_id, user, db)


# --- one endpoint per tool ----------------------------------------------------------------------
@router.get("/projects/{project_id}/insights/summary")
def summary(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _ctx(db, project_id, user)
    gains = c.gains()
    pp, fit, conf, fam, st = c.passport(), c.fit(gains), c.conflicts(), c.family(), c.stage(gains)
    sites = [s for s in c.project.site_verifications if s.analysis_id == c.analysis.id]
    return {**_meta(c), "overall_score": c.a["overall_score"], "trust_level": pp["level"],
            "trust_reasons": len(pp["reasons"]), "fit_counts": fit["counts"], "conflicts": len(conf["conflicts"]),
            "family_score": fam["family_score"], "family_set": bool(fam["profile"]["members"] or fam["profile"]["focus"]
                                                                     or fam["profile"]["room_priority"]),
            "stage": (st.get("current") or {}).get("label"), "act_now": len(st["act_now"]),
            "versions": len(c.project.analyses), "site_checks": len(sites),
            "expert_reviews": len(c.project.expert_reviews), "plan_checks": c.plan_checks()["counts"]}


@router.get("/projects/{project_id}/insights/explain")
def explain(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _ctx(db, project_id, user)
    return {**_meta(c), **c.explain()}


@router.get("/projects/{project_id}/insights/passport")
def passport(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _ctx(db, project_id, user)
    return {**_meta(c), **c.passport(), "plan_check_items": c.plan_checks()["checks"]}


@router.get("/projects/{project_id}/insights/fitcheck")
def fit(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _ctx(db, project_id, user)
    return {**_meta(c), **c.fit()}


@router.get("/projects/{project_id}/insights/conflicts")
def conflicts(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _ctx(db, project_id, user)
    return {**_meta(c), **c.conflicts()}


@router.get("/projects/{project_id}/insights/family")
def family(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _ctx(db, project_id, user)
    return {**_meta(c), **c.family()}


@router.get("/projects/{project_id}/insights/stage")
def stage(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _ctx(db, project_id, user)
    return {**_meta(c), **c.stage()}


@router.get("/projects/{project_id}/insights/history")
def history(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = owned_project(db, project_id, user)
    return {"versions": versions(project, project.analyses)}


@router.get("/projects/{project_id}/insights/history/compare")
def history_compare(project_id: str, old: str = Query(max_length=32), new: str = Query(max_length=32),
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = owned_project(db, project_id, user)
    by_id = {an.id: an for an in project.analyses}
    if old not in by_id or new not in by_id:
        raise NotFound("Analysis version")
    return compare(analysis_view(by_id[old]), analysis_view(by_id[new]))


@router.get("/projects/{project_id}/insights/voice")
def voice(project_id: str, language: str = Query("en", pattern="^(en|mr)$"),
          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _ctx(db, project_id, user)
    name = (c.prop.name if c.prop and c.prop.name else c.project.name)
    return {**_meta(c), **voice_script(c.a, name, language, c.rule_templates())}


# --- AI Mistake Catcher (works before any analysis) ---------------------------------------------
def _fp_checks(fp: FloorPlan, rooms, openings, boundary) -> dict:
    prop = fp.project.property
    return check_plan(rooms=rooms, openings=openings, boundary=boundary, width=fp.width, height=fp.height,
                      detection=fp.detection, property_type=prop.property_type if prop else None,
                      north={"north_angle": fp.north.north_angle, "confirmed": fp.north.confirmed} if fp.north else None)


@router.get("/floor-plans/{fp_id}/checks")
def plan_checks(fp_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Checks the verified plan, or the AI detection when nothing is verified yet."""
    fp = owned_floor_plan(db, fp_id, user)
    if fp.verified_at:
        rooms = [{"id": r.id, "label": r.label, "room_type": r.room_type, "polygon": r.polygon,
                  "source": r.source, "confidence": r.confidence} for r in fp.rooms]
        openings = [{"id": o.id, "kind": o.kind, "is_main_entrance": o.is_main_entrance, "position": o.position,
                     "source": o.source, "confidence": o.confidence} for o in fp.openings]
        return {"subject": "verified", **_fp_checks(fp, rooms, openings, fp.boundary)}
    det = fp.detection or {}
    rooms = [{"id": r["id"], "label": r["name"], "room_type": r["room_type"], "polygon": r["polygon"],
              "source": "ai", "confidence": r["confidence"]} for r in det.get("rooms", [])]
    openings = [{"id": o["id"], "kind": o["kind"], "is_main_entrance": o["is_main_entrance"],
                 "position": o["position"], "source": "ai", "confidence": o["confidence"]}
                for o in det.get("doors", []) + det.get("windows", [])]
    return {"subject": "detection", **_fp_checks(fp, rooms, openings, det.get("boundary"))}


@router.post("/floor-plans/{fp_id}/checks")
def draft_checks(fp_id: str, body: VerificationIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Checks a draft from the verification editor before it is saved."""
    fp = owned_floor_plan(db, fp_id, user)
    return {"subject": "draft", **_fp_checks(fp, [r.model_dump() for r in body.rooms],
                                             [o.model_dump() for o in body.openings], body.boundary)}


# --- Post-Move Verification ---------------------------------------------------------------------
def _site_out(c: Ctx, sv: SiteVerification) -> dict:
    _, rules, catalogue, _ = c.rule_ctx
    analysis = c.db.get(Analysis, sv.analysis_id)
    a = c.a if analysis.id == c.analysis.id else analysis_out(c.db, analysis)
    return evaluate_site(a, analysis, sv, rules, catalogue, common.scoring_cfg(analysis))


@router.get("/projects/{project_id}/site-verifications")
def list_site(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _ctx(db, project_id, user)
    rooms = [{"id": r["id"], "label": r["label"], "room_type": r["room_type"]}
             for r in (c.analysis.input_snapshot or {}).get("rooms", [])]
    issues = [{"finding_id": f["id"], "subject": f["subject_label"], "finding": f["finding"],
               "recommendation": f["remedy"]["recommendation"], "bucket": f["bucket"]}
              for f in c.a["findings"] if f["status"] == "issue" and f.get("remedy")]
    return {**_meta(c), "plan_rooms": rooms, "issues": issues, "north_angle": c.analysis.north_angle,
            "verifications": [_site_out(c, s) for s in reversed(c.project.site_verifications)]}


@router.post("/projects/{project_id}/site-verifications", status_code=201)
def create_site(project_id: str, body: SiteVerificationIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    c = _ctx(db, project_id, user)
    sv = SiteVerification(project_id=c.project.id, analysis_id=c.analysis.id,
                          compass_north_angle=body.compass_north_angle, entrance_confirmed=body.entrance_confirmed,
                          items=[i.model_dump() for i in body.items], remedy_progress=body.remedy_progress,
                          notes=body.notes)
    db.add(sv)
    db.commit()
    db.refresh(c.project)
    return _site_out(c, sv)


@router.post("/projects/{project_id}/site-verifications/{sv_id}/apply")
def apply_site(project_id: str, sv_id: str, body: ApplySiteIn | None = Body(default=None),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Applies as-built room types (and optionally the site North) to the plan, then re-runs the analysis.
    The previous analysis stays in the change history."""
    project = owned_project(db, project_id, user)
    sv = db.get(SiteVerification, sv_id)
    if not sv or sv.project_id != project.id:
        raise NotFound("Site verification")
    analysis = db.get(Analysis, sv.analysis_id)
    fp = db.get(FloorPlan, analysis.floor_plan_id)
    if not project.floor_plans or project.floor_plans[-1].id != fp.id:
        raise AppError("plan_replaced", "A newer floor plan has been uploaded since this check.", 409)
    rooms = {r.id: r for r in fp.rooms}
    changed = 0
    for it in sv.items or []:
        r = rooms.get(it.get("room_id"))
        if r and it.get("actual_room_type") and it["actual_room_type"] != r.room_type:
            if it["actual_room_type"] in ROOM_TYPES:
                r.room_type, r.source = it["actual_room_type"], "user"
                changed += 1
    if body and body.use_site_north and sv.compass_north_angle is not None:
        pipeline.set_north(db, fp, sv.compass_north_angle, user)
    elif changed:
        fp.status = pipeline.FloorPlanStatus.NORTH_SET
    sv.applied_at = utcnow()
    db.commit()
    new = pipeline.run_analysis(db, fp)
    return {"applied_rooms": changed, "used_site_north": bool(body and body.use_site_north),
            "analysis_id": new.id, "overall_score": round(new.overall_score) if new.overall_score is not None else None}


# --- Expert Review Handoff ----------------------------------------------------------------------
def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _pack(db: Session, review: ExpertReview) -> dict:
    project = review.project
    analysis = db.get(Analysis, review.analysis_id)
    c = Ctx(db, project, analysis)
    gains = c.gains()
    fam = c.family() if project.property and project.property.family_profile else None
    st = c.stage(gains) if project.property and project.property.construction_stage else None
    return build_pack(project=project, a=c.a, passport=c.passport(), checks=c.plan_checks(), explain=c.explain(),
                      fit=c.fit(gains), conflicts=c.conflicts(), family=fam, stage=st, message=review.message,
                      include_contact=bool(review.include_contact))


@router.get("/projects/{project_id}/expert-reviews")
def list_reviews(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = owned_project(db, project_id, user)
    return [review_out(r) for r in reversed(project.expert_reviews)]


@router.post("/projects/{project_id}/expert-reviews", status_code=201)
def create_review(project_id: str, body: ExpertReviewIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    project = owned_project(db, project_id, user)
    analysis = common.latest_analysis(project)
    if common.is_stale(project, analysis):
        raise AppError("stale_analysis", "Re-run the analysis before sending it for review.", 409)
    token = secrets.token_urlsafe(24)
    review = ExpertReview(project_id=project.id, analysis_id=analysis.id, token_hash=_hash(token),
                          expert_name=body.expert_name, expert_role=body.expert_role, message=body.message,
                          expires_at=utcnow() + timedelta(days=body.valid_days),
                          include_contact=body.include_contact)
    db.add(review)
    db.commit()
    # The token is shown once; only its hash is stored.
    return {**review_out(review, with_feedback=False), "token": token}


@router.post("/projects/{project_id}/expert-reviews/{review_id}/revoke")
def revoke_review(project_id: str, review_id: str, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    project = owned_project(db, project_id, user)
    review = db.get(ExpertReview, review_id)
    if not review or review.project_id != project.id:
        raise NotFound("Expert review")
    review.status = "revoked"
    db.commit()
    return review_out(review)


def _public_review(db: Session, token: str) -> ExpertReview:
    review = db.scalar(select(ExpertReview).where(ExpertReview.token_hash == _hash(token)))
    if not review or review.status == "revoked":
        raise NotFound("Review link")
    expires = review.expires_at if review.expires_at.tzinfo else review.expires_at.replace(tzinfo=utcnow().tzinfo)
    if expires < utcnow():
        raise AppError("link_expired", "This review link has expired. Ask the homeowner for a new one.", 410)
    return review


@router.get("/expert-review/{token}")
def public_review(token: str, db: Session = Depends(get_db)):
    review = _public_review(db, token)
    return {"review": review_out(review), "pack": _pack(db, review)}


@router.post("/expert-review/{token}/feedback")
def public_feedback(token: str, body: ExpertFeedbackIn, db: Session = Depends(get_db)):
    review = _public_review(db, token)
    review.feedback = {"verdict": body.verdict, "summary": body.summary,
                       "north_confirmed": body.north_confirmed,
                       "items": {k: v.model_dump() for k, v in body.items.items()}}
    review.reviewer_signature = body.signature
    review.status, review.submitted_at = "submitted", utcnow()
    db.commit()
    return {"status": review.status, "submitted_at": review.submitted_at.isoformat()}
