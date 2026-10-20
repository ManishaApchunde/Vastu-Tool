"""Workflow orchestration: upload -> detection -> verification -> North -> zones -> analysis.
Each step checks that the previous one is complete, so AI output can never reach the Vastu engine
without passing through user verification."""
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIDetectionError
from app.ai.factory import get_analyzer
from app.ai.preprocess import validate_and_prepare
from app.core.errors import AppError
from app.geometry.engine import OpeningInput, PlanInput, RoomInput, ZoneResult, boundary_from_rooms, compute_zones
from app.geometry.primitives import GeometryError, to_polygon
from app.models import (
    Analysis, Finding, FloorPlan, FloorPlanStatus, NorthOrientation, Opening, Project, Remedy, Room, RuleSet,
    ScoringConfig, User, VastuRule, VastuZone,
)
from app.models.base import new_id, utcnow
from app.remedies.engine import attach_remedies
from app.schemas.inputs import VerificationIn
from app.scoring.engine import score
from app.services import jobs
from app.services.storage import get_storage
from app.vastu.engine import evaluate
from app.vastu.room_types import normalise_room_type
from app.vastu.types import RemedySpec, RuleSpec


def _geo(exc: GeometryError) -> AppError:
    return AppError(exc.code, exc.message, 422)


# --- 1. upload ---------------------------------------------------------------------------------
def create_floor_plan(db: Session, project: Project, filename: str, data: bytes) -> FloorPlan:
    prepared = validate_and_prepare(filename, data)
    storage = get_storage()
    fid = new_id()
    ext = {"image/png": "png", "image/jpeg": "jpg", "application/pdf": "pdf"}[prepared.content_type]
    base = f"users/{project.owner_id}/projects/{project.id}/floor-plans/{fid}"
    storage.put(f"{base}/original.{ext}", data, prepared.content_type)
    storage.put(f"{base}/preview.png", prepared.preview_png, "image/png")
    fp = FloorPlan(id=fid, project_id=project.id, original_filename=filename[:255],
                   content_type=prepared.content_type, storage_key=f"{base}/original.{ext}",
                   preview_key=f"{base}/preview.png", width=prepared.width, height=prepared.height,
                   quality=prepared.quality, status=FloorPlanStatus.UPLOADED)
    db.add(fp)
    db.commit()
    return fp


# --- 2. AI detection ---------------------------------------------------------------------------
def start_detection(db: Session, fp: FloorPlan, user: User, background: BackgroundTasks | None = None):
    fp.status = FloorPlanStatus.PROCESSING
    db.commit()
    job = jobs.create_job(db, kind="detection", owner_id=user.id, project_id=fp.project_id, floor_plan_id=fp.id)
    jobs.dispatch(job, background)
    return job


@jobs.handler("detection")
def run_detection(db: Session, job) -> dict:
    fp = db.get(FloorPlan, job.floor_plan_id)
    if fp is None:
        raise AppError("not_found", "Floor plan was deleted.", 404)
    image = get_storage().get(fp.preview_key)
    try:
        result = get_analyzer().analyze_floor_plan(image, fp.width, fp.height)
    except AIDetectionError as exc:
        raise AppError("ai_detection_failed", str(exc), 502,
                       "Retry detection, or skip it and draw the rooms on the verification screen.") from exc
    result.warnings = (fp.quality or {}).get("warnings", []) + result.warnings
    fp.detection = result.model_dump()
    fp.detection_provider = result.provider
    fp.status = FloorPlanStatus.DETECTED
    db.commit()
    return {"rooms": len(result.rooms), "doors": len(result.doors), "windows": len(result.windows)}


# --- 3. verification ---------------------------------------------------------------------------
def _clear_derived(fp: FloorPlan) -> None:
    fp.zones.clear()
    fp.centre = None


def apply_verification(db: Session, fp: FloorPlan, data: VerificationIn) -> FloorPlan:
    if not data.rooms:
        raise AppError("missing_rooms", "Add at least one room before confirming the plan.", 422)
    tol_x, tol_y = fp.width * 0.05, fp.height * 0.05

    def in_bounds(p):
        return -tol_x <= p[0] <= fp.width + tol_x and -tol_y <= p[1] <= fp.height + tol_y

    try:
        for r in data.rooms:
            to_polygon(r.polygon, name=f"Room '{r.label}'")
            if not all(in_bounds(p) for p in r.polygon):
                raise GeometryError("invalid_geometry", f"Room '{r.label}' extends outside the floor plan image.")
        boundary = data.boundary or boundary_from_rooms([r.polygon for r in data.rooms])
        to_polygon(boundary, name="Plan boundary")
    except GeometryError as exc:
        raise _geo(exc) from exc
    for o in data.openings:
        if not in_bounds(o.position):
            raise AppError("invalid_geometry", f"A {o.kind} is placed outside the floor plan image.", 422)

    fp.rooms.clear()
    fp.openings.clear()
    db.flush()
    for i, r in enumerate(data.rooms):
        fp.rooms.append(Room(label=r.label.strip(), room_type=normalise_room_type(r.room_type, r.label),
                             polygon=r.polygon, confidence=r.confidence, source=r.source, sort_order=i))
    for o in data.openings:
        fp.openings.append(Opening(kind=o.kind, is_main_entrance=o.is_main_entrance and o.kind == "door",
                                   position=o.position, confidence=o.confidence, source=o.source))
    fp.boundary = boundary
    fp.verified_at = utcnow()
    _clear_derived(fp)
    fp.status = FloorPlanStatus.NORTH_SET if fp.north else FloorPlanStatus.VERIFIED
    db.commit()
    return fp


# --- 4. North ----------------------------------------------------------------------------------
def set_north(db: Session, fp: FloorPlan, angle: float, user: User) -> NorthOrientation:
    if not fp.verified_at:
        raise AppError("not_verified", "Verify the floor plan before setting North.", 409)
    angle = round(angle % 360.0, 2)
    if fp.north is None:
        fp.north = NorthOrientation(north_angle=angle)
    fp.north.north_angle, fp.north.confirmed, fp.north.confirmed_by = angle, True, user.id
    fp.north.confirmed_at = utcnow()
    _clear_derived(fp)
    fp.status = FloorPlanStatus.NORTH_SET
    db.commit()
    return fp.north


# --- 5/6. centre + zones -----------------------------------------------------------------------
def _plan_input(fp: FloorPlan) -> PlanInput:
    return PlanInput(
        boundary=fp.boundary,
        rooms=[RoomInput(r.id, r.label, r.room_type, r.polygon) for r in fp.rooms],
        openings=[OpeningInput(o.id, o.kind, o.is_main_entrance, o.position) for o in fp.openings],
    )


def calculate_zones(db: Session, fp: FloorPlan) -> ZoneResult:
    if not fp.verified_at or not fp.boundary:
        raise AppError("not_verified", "Verify the floor plan first.", 409)
    if not fp.north or not fp.north.confirmed:
        raise AppError("missing_north", "Set and confirm North before calculating zones.", 409)
    try:
        zr = compute_zones(_plan_input(fp), fp.north.north_angle, fp.zone_system)
    except GeometryError as exc:
        raise _geo(exc) from exc

    fp.zones.clear()
    db.flush()
    for z in zr.zones:
        fp.zones.append(VastuZone(system=zr.system, code=z.code, name=z.name, polygon=z.polygon, coverage=z.coverage))
    rooms = {r.id: r for r in fp.rooms}
    for rz in zr.rooms:
        room = rooms[rz.id]
        room.primary_zone, room.direction, room.bearing_deg, room.zone_overlaps = (
            rz.primary_zone, rz.direction, rz.bearing_deg, rz.overlaps)
    openings = {o.id: o for o in fp.openings}
    for oz in zr.openings:
        openings[oz.id].zone, openings[oz.id].direction = oz.zone, oz.direction
    fp.centre = list(zr.centre)
    if fp.status != FloorPlanStatus.ANALYZED:
        fp.status = FloorPlanStatus.ZONED
    db.commit()
    return zr


# --- 7-10. rules, score, remedies --------------------------------------------------------------
def active_rule_set(db: Session) -> RuleSet:
    rs = db.scalar(select(RuleSet).where(RuleSet.is_active.is_(True)).order_by(RuleSet.created_at.desc()))
    if rs is None:
        raise AppError("no_rule_set", "No active Vastu rule set is configured.", 500,
                       "Run the seed script: python -m app.seed.seed")
    return rs


def load_rule_context(db: Session) -> tuple[RuleSet, list[RuleSpec], dict[str, RemedySpec], ScoringConfig]:
    """Active rule set with its approved rules, approved remedy catalogue and active scoring config."""
    rs = active_rule_set(db)
    rules = [
        RuleSpec(r.id, r.code, r.category, r.subject_type, r.subject, r.condition, r.outcome, r.severity,
                 r.weight, r.finding_template, r.explanation, r.remedy_code)
        for r in db.scalars(select(VastuRule).where(VastuRule.rule_set_id == rs.id, VastuRule.status == "approved"))
    ]
    catalogue = {
        m.code: RemedySpec(m.id, m.code, m.problem, m.explanation, m.recommendation, m.priority, m.visual_instruction,
                           m.kind or "non_structural", m.phase, m.structural_note)
        for m in db.scalars(select(Remedy).where(Remedy.rule_set_id == rs.id, Remedy.status == "approved"))
    }
    cfg = db.scalar(select(ScoringConfig).where(ScoringConfig.rule_set_id == rs.id, ScoringConfig.is_active.is_(True))
                    .order_by(ScoringConfig.version.desc()))
    if cfg is None:
        raise AppError("no_scoring_config", "No active scoring configuration.", 500)
    return rs, rules, catalogue, cfg


def run_analysis(db: Session, fp: FloorPlan) -> Analysis:
    zr = calculate_zones(db, fp)  # always recompute from current verified data
    rs, rules, catalogue, cfg = load_rule_context(db)

    try:
        findings = attach_remedies(evaluate(zr, rules), catalogue)
        scored = score(findings, cfg.config)
    except Exception as exc:  # noqa: BLE001
        raise AppError("analysis_failed", "The analysis could not be completed.", 500,
                       "Check the verified plan for unusual shapes and try again.") from exc

    analysis = Analysis(
        project_id=fp.project_id, floor_plan_id=fp.id, rule_set_id=rs.id, scoring_config_id=cfg.id,
        north_angle=zr.north_angle, zone_system=zr.system, overall_score=scored["overall"],
        category_scores=scored["category_scores"], score_breakdown=scored["breakdown"], counts=scored["counts"],
        input_snapshot={"boundary": fp.boundary, "centre": list(zr.centre),
                        "rooms": [{"id": r.id, "label": r.label, "room_type": r.room_type, "polygon": r.polygon,
                                   "source": r.source, "confidence": r.confidence} for r in fp.rooms],
                        "openings": [{"id": o.id, "kind": o.kind, "is_main_entrance": o.is_main_entrance,
                                      "position": o.position, "source": o.source} for o in fp.openings],
                        "north_confirmed_at": fp.north.confirmed_at.isoformat() if fp.north.confirmed_at else None,
                        "detection_provider": fp.detection_provider},
        completed_at=utcnow(),
    )
    for i, f in enumerate(findings):
        analysis.findings.append(Finding(
            rule_id=f.rule_id, rule_code=f.rule_code, category=f.category, subject_type=f.subject_type,
            subject_ref=f.subject_ref, subject_label=f.subject_label, room_type=f.room_type, zone=f.zone,
            direction=f.direction, status=f.status, severity=f.severity, bucket=f.bucket, weight=f.weight,
            earned=f.earned, finding=f.finding, explanation=f.explanation,
            remedy_id=(f.remedy or {}).get("id"), remedy_snapshot=f.remedy, sort_order=i,
        ))
    db.add(analysis)
    fp.status = FloorPlanStatus.ANALYZED
    db.commit()
    return analysis
