"""Seed rule set, rules, remedies, scoring config, a demo user and a complete demo project.

    python -m app.seed.seed            # idempotent
    python -m app.seed.seed --reset-rules   # reload rules/remedies/scoring from JSON
"""
import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Project, Property, Remedy, RuleSet, ScoringConfig, User, VastuRule

DATA = Path(__file__).parent / "data"
DEMO_EMAIL, DEMO_PASSWORD = "demo@example.com", "demo12345"


def seed_rules(db: Session, reset: bool = False) -> RuleSet:
    rules_doc = json.loads((DATA / "rules.json").read_text())
    meta = rules_doc["rule_set"]
    rs = db.scalar(select(RuleSet).where(RuleSet.code == meta["code"]))
    if rs and not reset:
        sync_remedy_metadata(db, rs)
        return rs
    if rs and reset:
        db.delete(rs)
        db.flush()
    rs = RuleSet(**meta, is_active=True)
    db.add(rs)
    db.flush()
    for r in rules_doc["rules"]:
        db.add(VastuRule(rule_set_id=rs.id, approved_by="seed (pending expert review)", **r))
    for m in json.loads((DATA / "remedies.json").read_text())["remedies"]:
        db.add(Remedy(rule_set_id=rs.id, approved_by="seed (pending expert review)", **m))
    sc = json.loads((DATA / "scoring.json").read_text())
    db.add(ScoringConfig(rule_set_id=rs.id, name=sc["name"], config=sc["config"], is_active=True))
    db.commit()
    return rs


def sync_remedy_metadata(db: Session, rs: RuleSet) -> int:
    """Back-fill catalogue fields added after a database was first seeded (kind, phase,
    structural_note), without touching rows a reviewer has already filled in."""
    by_code = {m["code"]: m for m in json.loads((DATA / "remedies.json").read_text())["remedies"]}
    changed = 0
    for rem in db.scalars(select(Remedy).where(Remedy.rule_set_id == rs.id)):
        src = by_code.get(rem.code)
        if not src or rem.structural_note is not None or rem.phase is not None:
            continue
        if rem.kind in (None, "non_structural") and src.get("kind") not in (None, "non_structural") \
                or src.get("structural_note") or src.get("phase"):
            rem.kind = src.get("kind") or "non_structural"
            rem.phase = src.get("phase")
            rem.structural_note = src.get("structural_note")
            # The everyday recommendation was split from the structural note in the same release.
            if src.get("structural_note"):
                rem.recommendation = src["recommendation"]
            changed += 1
        elif rem.kind is None:
            rem.kind = "non_structural"
            changed += 1
    if changed:
        db.commit()
    return changed


def seed_demo_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD), full_name="Demo User")
        db.add(user)
        db.commit()
    return user


def create_demo_project(db: Session, user: User) -> Project:
    """Runs the real pipeline end to end with the mock analyzer and a user-corrected plan."""
    from app.ai.mock import MockFloorPlanAnalyzer
    from app.schemas.inputs import OpeningIn, RoomIn, VerificationIn
    from app.seed.demo_plan import draw_demo_plan
    from app.services import pipeline

    project = Project(owner_id=user.id, name="Demo Residence", is_demo=True,
                      description="Sample 3-bedroom plan for trying the workflow.")
    project.property = Property(name="Demo Residence", address="Plot 14, Baner, Pune, Maharashtra",
                                property_type="independent_house", built_up_area_sqft=1850)
    db.add(project)
    db.commit()
    fp = pipeline.create_floor_plan(db, project, "demo-floor-plan.png", draw_demo_plan())
    det = MockFloorPlanAnalyzer().analyze_floor_plan(b"", fp.width, fp.height)
    fp.detection, fp.detection_provider, fp.status = det.model_dump(), det.provider, "detected"
    db.commit()

    rooms = [RoomIn(label="Bedroom 2" if r.name == "Room" else r.name,
                    room_type="bedroom" if r.name == "Room" else r.room_type, polygon=r.polygon,
                    confidence=r.confidence, source="ai_edited" if r.name == "Room" else "ai") for r in det.rooms]
    rooms += [RoomIn(label="Staircase", room_type="staircase", polygon=s.polygon, confidence=s.confidence,
                     source="ai") for s in det.stairs]
    openings = [OpeningIn(kind=o.kind, position=o.position, is_main_entrance=o.is_main_entrance,
                          confidence=o.confidence, source="ai") for o in det.doors + det.windows]
    pipeline.apply_verification(db, fp, VerificationIn(boundary=det.boundary, rooms=rooms, openings=openings))
    pipeline.set_north(db, fp, 0, user)
    pipeline.run_analysis(db, fp)
    return project


def run(reset_rules: bool = False) -> None:
    with SessionLocal() as db:
        seed_rules(db, reset=reset_rules)
        user = seed_demo_user(db)
        if not db.scalar(select(Project).where(Project.owner_id == user.id, Project.is_demo.is_(True))):
            create_demo_project(db, user)
    print(f"Seed complete. Demo login: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    from app.core.db import Base, engine
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)
    run(reset_rules="--reset-rules" in sys.argv)
