"""Post-Move Verification: compare the real house with the analysed plan.

The customer records how each room is actually used, whether the main entrance is the one on the
plan, a compass reading taken on site, and progress on each remedy. This module reports the
differences and simulates the analysis 'as built' (actual room types, and the site North when it
disagrees) without changing anything. Applying the differences is a separate, explicit step."""
from app.geometry.primitives import GeometryError
from app.insights.common import angle_diff, plan_input_from_snapshot, simulate
from app.vastu.room_types import ROOM_TYPES

NORTH_TOLERANCE = 10.0
PROGRESS = ("done", "partial", "not_started", "not_possible")


def evaluate_site(a: dict, analysis, sv, rules, catalogue, cfg: dict) -> dict:
    snap = analysis.input_snapshot or {}
    planned = {r["id"]: r for r in snap.get("rooms", [])}
    retyped, missing = [], []
    overrides = {}
    for it in sv.items or []:
        r = planned.get(it.get("room_id"))
        if not r:
            continue
        if it.get("present") is False:
            missing.append(r["label"])
        actual = it.get("actual_room_type")
        if actual and actual in ROOM_TYPES and actual != r["room_type"]:
            overrides[r["id"]] = actual
            retyped.append({"room_id": r["id"], "room": r["label"], "planned": ROOM_TYPES.get(r["room_type"]),
                            "actual": ROOM_TYPES[actual], "note": it.get("note")})

    north = None
    use_north = analysis.north_angle
    if sv.compass_north_angle is not None:
        diff = angle_diff(sv.compass_north_angle, analysis.north_angle)
        north = {"plan": analysis.north_angle, "site": sv.compass_north_angle, "difference_deg": round(diff, 1),
                 "agrees": diff <= NORTH_TOLERANCE}
        if not north["agrees"]:
            use_north = sv.compass_north_angle

    as_built = None
    if overrides or use_north != analysis.north_angle:
        try:
            sim = simulate(plan_input_from_snapshot(snap, overrides), use_north, analysis.zone_system,
                           rules, catalogue, cfg)
            changed_ids = set(overrides)
            as_built = {
                "overall_score": sim["overall"], "official_score": a["overall_score"],
                "delta": (sim["overall"] - a["overall_score"]) if None not in (sim["overall"], a["overall_score"]) else None,
                "used_site_north": use_north != analysis.north_angle,
                "issues_in_changed_rooms": [
                    {"subject": f.subject_label, "finding": f.finding, "bucket": f.bucket}
                    for f in sim["findings"] if f.status == "issue"
                    and (f.subject_ref in changed_ids or use_north != analysis.north_angle)][:12],
            }
        except (GeometryError, KeyError):
            as_built = None

    issues = [f for f in a["findings"] if f["status"] == "issue" and f.get("remedy")]
    progress = sv.remedy_progress or {}
    tally = {k: 0 for k in PROGRESS}
    rows = []
    for f in issues:
        state = progress.get(f["id"], "not_started")
        state = state if state in PROGRESS else "not_started"
        tally[state] += 1
        rows.append({"finding_id": f["id"], "subject": f["subject_label"], "finding": f["finding"],
                     "recommendation": f["remedy"]["recommendation"], "state": state})
    doable = len(issues) - tally["not_possible"]
    pct = round(100 * (tally["done"] + 0.5 * tally["partial"]) / doable) if doable else None

    actions = []
    if retyped:
        actions.append(f"{len(retyped)} room(s) are used differently from the plan; apply the as-built types and "
                       "re-run the analysis.")
    if missing:
        actions.append(f"{len(missing)} room(s) on the plan don't exist on site; correct the plan on the Verify step.")
    if north and not north["agrees"]:
        actions.append(f"The site compass differs from the plan's North by {north['difference_deg']}°; re-check it "
                       "away from metal and electrical equipment, then update North if it holds.")
    if sv.entrance_confirmed is False:
        actions.append("The main entrance used on site is not the one on the plan; mark the right door on the "
                       "Verify step.")
    verdict = "matches" if not actions else "re_run" if (retyped or (north and not north["agrees"])) else "differences"
    return {"id": sv.id, "analysis_id": sv.analysis_id, "created_at": sv.created_at.isoformat(),
            "applied_at": sv.applied_at.isoformat() if sv.applied_at else None,
            "verdict": verdict, "actions": actions, "north": north, "entrance_confirmed": sv.entrance_confirmed,
            "retyped_rooms": retyped, "missing_rooms": missing, "as_built": as_built,
            "remedies": {"items": rows, "tally": tally, "percent_done": pct}, "notes": sv.notes,
            "items": sv.items or [], "compass_north_angle": sv.compass_north_angle}
