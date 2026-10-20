"""Response shaping. Kept in one place so the API, the dashboard and the PDF all read the same data."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.geometry.zones import ZONE_NAMES
from app.models import Analysis, FloorPlan, ProcessingJob, Project, Report
from app.services.storage import get_storage
from app.vastu.room_types import ROOM_TYPES


def _int(v):
    return int(round(v)) if v is not None else None


def iso(dt):
    return dt.isoformat() if dt else None


def job_out(job: ProcessingJob | None) -> dict | None:
    if job is None:
        return None
    return {"id": job.id, "kind": job.kind, "status": job.status, "attempts": job.attempts,
            "max_attempts": job.max_attempts, "error_code": job.error_code, "error": job.error,
            "can_retry": job.status == "failed" and job.attempts < job.max_attempts,
            "created_at": iso(job.created_at), "finished_at": iso(job.finished_at)}


def latest_job(db: Session, *, floor_plan_id: str | None = None, project_id: str | None = None, kind: str):
    q = select(ProcessingJob).where(ProcessingJob.kind == kind)
    q = q.where(ProcessingJob.floor_plan_id == floor_plan_id) if floor_plan_id else q.where(
        ProcessingJob.project_id == project_id)
    return db.scalar(q.order_by(ProcessingJob.created_at.desc()))


def floor_plan_out(db: Session, fp: FloorPlan, include_detection: bool = False) -> dict:
    out = {
        "id": fp.id, "project_id": fp.project_id, "status": fp.status, "original_filename": fp.original_filename,
        "content_type": fp.content_type, "width": fp.width, "height": fp.height, "quality": fp.quality,
        "image_url": get_storage().signed_url(fp.preview_key),
        "detection_provider": fp.detection_provider, "has_detection": fp.detection is not None,
        "verified": fp.verified_at is not None, "verified_at": iso(fp.verified_at),
        "boundary": fp.boundary, "centre": fp.centre, "zone_system": fp.zone_system,
        "north": {"north_angle": fp.north.north_angle, "confirmed": fp.north.confirmed,
                  "confirmed_at": iso(fp.north.confirmed_at)} if fp.north else None,
        "rooms": [{"id": r.id, "label": r.label, "room_type": r.room_type, "polygon": r.polygon,
                   "confidence": r.confidence, "source": r.source, "primary_zone": r.primary_zone,
                   "direction": r.direction, "bearing_deg": r.bearing_deg} for r in fp.rooms],
        "openings": [{"id": o.id, "kind": o.kind, "is_main_entrance": o.is_main_entrance, "position": o.position,
                      "confidence": o.confidence, "source": o.source, "zone": o.zone, "direction": o.direction}
                     for o in fp.openings],
        "zones": [{"code": z.code, "name": z.name, "polygon": z.polygon, "coverage": z.coverage} for z in fp.zones],
        "detection_job": job_out(latest_job(db, floor_plan_id=fp.id, kind="detection")),
        "created_at": iso(fp.created_at),
    }
    if include_detection:
        out["detection"] = fp.detection
    return out


def project_out(db: Session, p: Project, detail: bool = False) -> dict:
    fp = p.floor_plans[-1] if p.floor_plans else None
    analysis = p.analyses[-1] if p.analyses else None
    out = {
        "id": p.id, "name": p.name, "description": p.description, "is_demo": p.is_demo,
        "created_at": iso(p.created_at), "updated_at": iso(p.updated_at),
        "property": {"name": p.property.name, "client_name": p.property.client_name,
                     "address": p.property.address,
                     "property_type": p.property.property_type,
                     "built_up_area_sqft": p.property.built_up_area_sqft, "notes": p.property.notes}
        if p.property else None,
        "floor_plan_id": fp.id if fp else None,
        "floor_plan_status": fp.status if fp else None,
        "overall_score": _int(analysis.overall_score) if analysis else None,
        "analysis_id": analysis.id if analysis else None,
    }
    if detail and fp:
        out["floor_plan"] = floor_plan_out(db, fp)
    return out


def analysis_out(db: Session, a: Analysis) -> dict:
    fp = db.get(FloorPlan, a.floor_plan_id)
    findings = [finding_out(f) for f in a.findings]
    by_room = {f["subject_ref"]: f for f in findings if f["subject_type"] == "room" and f["category"] == "rooms"}
    rooms = []
    for r in fp.rooms:
        f = by_room.get(r.id)
        room_findings = [x for x in findings if x["subject_ref"] == r.id]
        worst = "info"
        for b in ("major", "warning", "positive"):
            if any(x["bucket"] == b for x in room_findings):
                worst = b
                break
        rooms.append({
            "id": r.id, "label": r.label, "room_type": r.room_type,
            "room_type_label": ROOM_TYPES.get(r.room_type, r.room_type), "polygon": r.polygon,
            "zone": r.primary_zone, "zone_name": ZONE_NAMES.get(r.primary_zone, r.primary_zone),
            "direction": r.direction, "bearing_deg": r.bearing_deg,
            "rule_result": f["status"] if f else "not_evaluated", "worst_bucket": worst,
            "finding": f["finding"] if f else None, "remedy": f["remedy"] if f else None,
        })
    remedies = [dict(f["remedy"], subject=f["subject_label"], zone=f["zone"], severity=f["severity"],
                     finding_id=f["id"]) for f in findings if f["remedy"]]
    remedies.sort(key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(r["priority"], 3))
    rs = a.rule_set
    return {
        "id": a.id, "project_id": a.project_id, "floor_plan_id": a.floor_plan_id, "status": a.status,
        "created_at": iso(a.created_at), "overall_score": _int(a.overall_score), "category_scores": a.category_scores,
        "score_breakdown": a.score_breakdown, "counts": a.counts, "north_angle": a.north_angle,
        "zone_system": a.zone_system,
        "rule_set": {"code": rs.code, "name": rs.name, "methodology": rs.methodology, "version": rs.version,
                     "disclaimer": rs.disclaimer},
        "centre": fp.centre, "boundary": fp.boundary,
        "zones": [{"code": z.code, "name": z.name, "polygon": z.polygon, "coverage": z.coverage} for z in fp.zones],
        "openings": [{"id": o.id, "kind": o.kind, "is_main_entrance": o.is_main_entrance, "position": o.position,
                      "zone": o.zone, "direction": o.direction} for o in fp.openings],
        "image_url": get_storage().signed_url(fp.preview_key), "image_width": fp.width, "image_height": fp.height,
        "rooms": rooms, "findings": findings, "remedies": remedies,
        # Most important first: major before warning, then the heaviest-weighted rules.
        "summary": sorted((f for f in findings if f["bucket"] in ("major", "warning")),
                          key=lambda f: (f["bucket"] != "major", -(f["weight"] or 0)))[:5],
    }


def finding_out(f) -> dict:
    return {"id": f.id, "rule_code": f.rule_code, "category": f.category, "subject_type": f.subject_type,
            "subject_ref": f.subject_ref, "subject_label": f.subject_label, "room_type": f.room_type,
            "zone": f.zone, "zone_name": ZONE_NAMES.get(f.zone, f.zone) if f.zone else None,
            "direction": f.direction, "status": f.status, "severity": f.severity, "bucket": f.bucket,
            "weight": f.weight, "earned": f.earned, "finding": f.finding, "explanation": f.explanation,
            "remedy": f.remedy_snapshot}


def report_out(db: Session, r: Report) -> dict:
    job = db.get(ProcessingJob, r.job_id) if r.job_id else None
    url = None
    if r.status == "ready" and r.storage_key:
        lang = r.language or "en"
        url = get_storage().signed_url(r.storage_key, download_name=f"vastu-report-{r.id[:8]}-{lang}.pdf")
    return {"id": r.id, "project_id": r.project_id, "analysis_id": r.analysis_id, "status": r.status,
            "language": r.language or "en", "action_plan": bool((r.options or {}).get("action_plan")),
            "error": r.error, "download_url": url, "created_at": iso(r.created_at), "job": job_out(job)}
