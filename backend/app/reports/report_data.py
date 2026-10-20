"""Report model: turns a stored analysis into everything the PDF shows.

All wording here is assembled from analysis data (findings, rule explanations, the remedy
catalogue, scores, geometry). Nothing is property-specific static text, and the PDF renderer does
no Vastu reasoning of its own: it only lays out this structure.

    Analysis + FloorPlan + RuleSet ──► build_report_data() ──► dict ──► pdf.build_pdf() / plan renderer

`language` ("en" | "mr") only selects the wording (see reports/i18n.py). The same findings, scores,
room results and remedies are used for every language.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Analysis, FloorPlan, Project, VastuRule
from app.remedies.engine import PHASES, phase_for
from app.reports.i18n import (  # noqa: F401 - English vocabularies re-exported for existing imports
    DISCLAIMER_POINTS, KIND_LABELS, RESULT_LABELS, ROOM_NOUNS, EnglishTexts, texts_for,
)
from app.services.serializers import analysis_out

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
TONES = ("positive", "warning", "major", "neutral")
_EN = EnglishTexts()

# Room result vocabulary. It is a presentation of the rule outcome, not a separate judgement:
#   any high-severity issue  -> Unfavourable      (major)
#   any other issue          -> Needs attention   (warning)
#   placement preferred      -> Highly auspicious (positive)
#   placement acceptable     -> Auspicious        (positive)
#   no matching rule         -> Not evaluated     (neutral)
# (RESULT_LABELS and DISCLAIMER_POINTS live in reports/i18n.py with their translations.)


def _pct(x: float | None) -> int:
    return int(round((x or 0) * 100))


def _zone_name(code: str | None, t: EnglishTexts = _EN) -> str | None:
    return t.zone(code)


def _join(items: list[str], t: EnglishTexts = _EN) -> str:
    return t.join(items)


def _score_band(score: float | None, t: EnglishTexts = _EN) -> tuple[str, str]:
    return t.score_band(score)


def _tone_for_score(score: float | None) -> str:
    return _score_band(score)[1]  # tone does not depend on language


def _zone_preferences(db: Session, rule_set_id: str) -> dict[str, dict[str, list[str]]]:
    """Per room type, which zones the rule set lists as preferred / acceptable (from approved rules)."""
    prefs: dict[str, dict[str, list[str]]] = {}
    rules = db.scalars(select(VastuRule).where(VastuRule.rule_set_id == rule_set_id,
                                               VastuRule.status == "approved"))
    for r in rules:
        if r.subject_type != "room" or (r.condition or {}).get("type") != "room_in_zone":
            continue
        if r.outcome not in ("preferred", "acceptable"):
            continue
        bucket = prefs.setdefault(r.subject, {"preferred": [], "acceptable": []})
        for z in r.condition.get("zones", []):
            if z not in bucket[r.outcome]:
                bucket[r.outcome].append(z)
    return prefs


def _room_score(findings: list[dict]) -> int | None:
    scored = [f for f in findings if f["status"] != "not_evaluated" and (f["weight"] or 0) > 0]
    possible = sum(f["weight"] for f in scored)
    if not possible:
        return None
    return int(round(100 * sum(f["earned"] for f in scored) / possible))


def _remedy_item(f: dict, remedy: dict, t: EnglishTexts = _EN) -> dict:
    kind = remedy.get("kind") or "non_structural"
    return {
        "code": remedy.get("code"),
        "subject": f["subject_label"],
        "zone": f.get("zone"),
        "zone_name": t.zone(f.get("zone")),
        "problem": remedy.get("problem") or f["finding"],
        "why": remedy.get("explanation"),
        "rule_explanation": f.get("explanation"),
        "action": remedy.get("recommendation"),
        "visual": remedy.get("visual_instruction"),
        "structural_note": remedy.get("structural_note"),
        "priority": remedy.get("priority") or "medium",
        "kind": kind,
        "kind_label": t.kind_label(kind),
        "phase": phase_for(remedy),
        "approved": bool(remedy.get("approved", True)),
        "needs_professional": kind == "structural" or bool(remedy.get("structural_note")),
        "severity": f.get("severity"),
        "bucket": f.get("bucket"),
    }


def _with_catalogue_fields(db: Session, rule_set_id: str, findings: list[dict]) -> None:
    """Analyses stored before remedies had kind/phase/structural_note: fill them from the catalogue."""
    from app.models import Remedy

    missing = {f["remedy"]["code"] for f in findings
               if f.get("remedy") and f["remedy"].get("code") and "kind" not in f["remedy"]}
    if not missing:
        return
    cat = {m.code: m for m in db.scalars(select(Remedy).where(Remedy.rule_set_id == rule_set_id,
                                                              Remedy.code.in_(missing)))}
    for f in findings:
        r = f.get("remedy")
        if r and r.get("code") in cat and "kind" not in r:
            m = cat[r["code"]]
            r.update(kind=m.kind or "non_structural", phase=m.phase, structural_note=m.structural_note)


# --- rooms ---------------------------------------------------------------------------------------
def _room_entry(room: dict, fp_room, findings: list[dict], prefs: dict, rule_set_name: str,
                t: EnglishTexts = _EN) -> dict:
    own = [f for f in findings if f["subject_ref"] == room["id"]]
    placement = next((f for f in own if f["category"] == "rooms"), None)
    status = placement["status"] if placement else "not_evaluated"
    worst = room["worst_bucket"]
    if worst == "major":
        tone, label = "major", t.result_label("major")
    elif worst == "warning":
        tone, label = "warning", t.result_label("warning")
    elif worst == "positive":
        tone = "positive"
        label = t.result_label("preferred" if status == "preferred" else "acceptable")
    else:
        tone, label = "neutral", t.result_label("neutral")

    type_label = room["room_type_label"]
    overlaps = sorted(((z, s) for z, s in ((fp_room.zone_overlaps or {}) if fp_room else {}).items() if s > 0),
                      key=lambda x: -x[1])
    primary_share = _pct(dict(overlaps).get(room["zone"])) if room["zone"] else 0
    others = [(z, _pct(s)) for z, s in overlaps if z != room["zone"] and _pct(s) >= 10]

    # Introduction: where the room is, what the rule set says about it, and why (rule explanation).
    intro: list[str] = []
    name = t.room_name(room["label"], room["room_type"], type_label)
    if room["zone"]:
        intro.append(t.room_where(name, room["zone_name"], primary_share, [(t.zone(z), p) for z, p in others]))
    if placement and status != "not_evaluated":
        intro.append(t.room_verdict(status, rule_set_name, room["zone_name"], room["room_type"], type_label,
                                    placement["severity"]))
        if placement.get("explanation"):
            intro.append(placement["explanation"])
        p = prefs.get(room["room_type"])
        if p and (p["preferred"] or p["acceptable"]):
            intro.append(t.room_prefs([t.zone(z) for z in p["preferred"]], [t.zone(z) for z in p["acceptable"]],
                                      room["room_type"], type_label))
    else:
        intro.append(t.room_unscored(type_label))

    # Considerations: exactly what the rule engine found for this room.
    considerations: list[dict] = []
    rank = {"major": 0, "warning": 1, "positive": 2, "neutral": 3}
    for f in sorted(own, key=lambda x: (rank[_bucket_tone(x["bucket"])], -(x["weight"] or 0))):
        if f["status"] == "not_evaluated":
            continue
        considerations.append({"tone": _bucket_tone(f["bucket"]), "text": f["finding"]})
    if others and any(p >= 25 for _, p in others):
        z, p = max(others, key=lambda x: x[1])
        considerations.append({"tone": "neutral", "text": t.room_straddles(p, t.zone(z))})
    if not any(c["tone"] in ("warning", "major") for c in considerations) and status != "not_evaluated":
        considerations.append({"tone": "neutral", "text": t.room_no_issues()})

    # Recommendations: approved catalogue remedies attached to this room's findings only.
    recs, seen = [], set()
    for f in own:
        if f.get("remedy"):
            item = _remedy_item(f, f["remedy"], t)
            key = item["code"] or item["problem"]
            if key not in seen:
                seen.add(key)
                recs.append(item)
    recs.sort(key=lambda r: PRIORITY_ORDER.get(r["priority"], 3))

    return {
        "id": room["id"], "label": room["label"], "room_type": room["room_type"], "room_type_label": type_label,
        "zone": room["zone"], "zone_name": room["zone_name"],
        "direction": room["direction"], "direction_name": t.zone(room["direction"]),
        "zone_share": primary_share, "other_zones": [{"zone": z, "name": t.zone(z), "share": p} for z, p in others],
        "score": _room_score(own), "status": status, "result": label, "tone": tone,
        "rule_code": placement["rule_code"] if placement else None,
        "introduction": intro, "considerations": considerations, "recommendations": recs,
        "polygon": room["polygon"],
    }


def _bucket_tone(bucket: str) -> str:
    return {"positive": "positive", "warning": "warning", "major": "major"}.get(bucket, "neutral")


# --- main ----------------------------------------------------------------------------------------
def build_report_data(db: Session, analysis: Analysis, project: Project,
                      generated_at: datetime | None = None, language: str = "en") -> dict:
    t = texts_for(language)
    a = analysis_out(db, analysis)
    fp = db.get(FloorPlan, analysis.floor_plan_id)
    fp_rooms = {r.id: r for r in fp.rooms}
    owner = project.owner
    prop = project.property
    generated_at = generated_at or datetime.now(timezone.utc)
    _with_catalogue_fields(db, analysis.rule_set_id, a["findings"])
    source_labels = {r["id"]: r["label"] for r in a["rooms"]}  # numbering must not depend on language
    if language != "en":
        # Translate the stored analysis (labels, finding text, explanations, remedies). Values, codes and
        # buckets are copied unchanged, so everything below makes exactly the same decisions.
        templates = {r.code: r.finding_template for r in db.scalars(
            select(VastuRule).where(VastuRule.rule_set_id == analysis.rule_set_id))}
        a = t.localise_analysis(a, templates)
    rs = a["rule_set"]
    rule_set_name = rs["name"]
    findings = a["findings"]
    prefs = _zone_preferences(db, analysis.rule_set_id)

    # Rooms, numbered attention-first so the report opens with what matters most.
    rooms = [_room_entry(r, fp_rooms.get(r["id"]), findings, prefs, rule_set_name, t) for r in a["rooms"]]
    tone_rank = {"major": 0, "warning": 1, "positive": 2, "neutral": 3}
    rooms.sort(key=lambda r: (tone_rank[r["tone"]], r["score"] if r["score"] is not None else 101,
                              source_labels[r["id"]]))
    for i, r in enumerate(rooms, 1):
        r["number"] = i

    # Findings grouped for the three findings sections.
    def group(bucket):
        items = [f for f in findings if f["bucket"] == bucket]
        items.sort(key=lambda f: -(f["weight"] or 0))
        return [{"subject": f["subject_label"], "text": f["finding"], "explanation": f["explanation"],
                 "zone_name": f["zone_name"], "severity": f["severity"]} for f in items]

    grouped = {"positive": group("positive"), "warning": group("warning"), "major": group("major")}

    # Remedies: one item per (remedy, subject), phased.
    remedy_items, seen = [], set()
    for f in sorted(findings, key=lambda x: (x["bucket"] != "major", -(x["weight"] or 0))):
        if not f.get("remedy"):
            continue
        item = _remedy_item(f, f["remedy"], t)
        key = (item["code"] or item["problem"], item["subject"])
        if key in seen:
            continue
        seen.add(key)
        remedy_items.append(item)
    remedy_items.sort(key=lambda r: (PRIORITY_ORDER.get(r["priority"], 3), r["bucket"] != "major"))

    plan: dict[str, list[dict]] = {p: [] for p in PHASES}
    for r in remedy_items:
        plan[r["phase"]].append({"subject": r["subject"], "text": r["action"], "priority": r["priority"],
                                 "kind_label": r["kind_label"], "structural": False})
        if r["structural_note"]:
            plan["long_term"].append({"subject": r["subject"], "text": r["structural_note"],
                                      "priority": r["priority"], "kind_label": t.kind_label("structural"),
                                      "structural": True})
    remedy_plan = [{"key": p, "label": t.phase_label(p), "items": plan[p]} for p in PHASES]

    # Scores.
    categories = []
    for c in a["score_breakdown"].get("categories", []):
        categories.append({"key": c["category"], "label": t.category_label(c["category"], c["label"]),
                           "score": c["score"],
                           "earned": c["earned"], "possible": c["possible"], "findings": c["findings"],
                           "weight": c["category_weight"], "tone": _tone_for_score(c["score"])})
    overall = a["overall_score"]
    band, band_tone = t.score_band(overall)
    counts = {k: a["counts"].get(k, 0) for k in ("positive", "warning", "major", "info")}
    north = a["north_angle"] or 0.0
    has_entrance = any(o["is_main_entrance"] for o in a["openings"])

    # Executive summary, assembled from the numbers above.
    exec_summary = [t.exec_intro(prop.name if prop else project.name, t.date(generated_at), rule_set_name,
                                 rs["version"], len(rooms), has_entrance, north)]
    if overall is not None:
        strong = [c["label"] for c in categories if c["score"] is not None and c["score"] >= 75]
        weak = [c["label"] for c in categories if c["score"] is not None and c["score"] < 50]
        exec_summary.append(t.exec_score(overall, band, strong, weak))
    top_issues = grouped["major"][:2] or grouped["warning"][:2]
    exec_summary.append(t.exec_counts(counts, [x["text"] for x in top_issues]))
    if remedy_items:
        n_imm = len(plan["immediate"])
        n_struct = sum(1 for r in remedy_items if r["needs_professional"])
        exec_summary.append(t.exec_remedies(len(remedy_items), n_imm, n_struct))

    # Final summary.
    def _line(f):
        return t.subject_line(f["subject"], f["text"])

    strengths = [{"tone": "positive", "text": _line(f)} for f in grouped["positive"][:3]]
    weaknesses = ([{"tone": "major", "text": _line(f)} for f in grouped["major"]]
                  + [{"tone": "warning", "text": _line(f)} for f in grouped["warning"]])[:3]
    priorities = [f"{r['subject']}: {r['problem']}" for r in remedy_items[:5]]
    next_steps = []
    if plan["immediate"]:
        next_steps.append(t.next_immediate())
    if any(r["needs_professional"] for r in remedy_items):
        next_steps.append(t.next_structural())
    unscored = [r["label"] for r in rooms if r["tone"] == "neutral"]
    if unscored:
        next_steps.append(t.next_unscored(unscored))
    if not has_entrance:
        next_steps.append(t.next_entrance())
    next_steps.append(t.next_rerun())

    zone_rows = []
    for z in a["zones"]:
        in_zone = [r["label"] for r in rooms if r["zone"] == z["code"]]
        zone_rows.append({"code": z["code"], "name": z["name"], "coverage": _pct(z["coverage"]), "rooms": in_zone})

    return {
        "brand": settings.report_brand,
        "language": language,
        "generated_on": t.date(generated_at),
        "report_title": t.report_title,
        "property": {
            "name": prop.name if prop else project.name,
            "client_name": (prop.client_name if prop and prop.client_name else None) or (owner.full_name if owner else None),
            "property_type": t.property_type(prop.property_type if prop else "other"),
            "address": prop.address if prop else None,
            "built_up_area": t.built_up_area(prop.built_up_area_sqft) if prop and prop.built_up_area_sqft else None,
            "notes": prop.notes if prop else None,
            "rooms_count": len(rooms),
        },
        "assessment": {
            "date": t.date(generated_at),
            "analysed_on": a["created_at"],
            "rule_set": {"name": rule_set_name, "version": rs["version"], "methodology": rs["methodology"]},
            "zone_system": t.zone_system,
            "north_angle": north,
            "north_text": t.north_text(north),
            "has_main_entrance": has_entrance,
            "plan_file": fp.original_filename,
        },
        "overall_score": overall,
        "score_band": band, "score_tone": band_tone,
        "categories": categories,
        "scoring_method": t.scoring_method,
        "counts": counts,
        "executive_summary": exec_summary,
        "rooms": rooms,
        "zones": zone_rows,
        "findings": grouped,
        "remedies": remedy_items,
        "remedy_plan": remedy_plan,
        "final_summary": {"score": overall, "band": band, "strengths": strengths, "weaknesses": weaknesses,
                          "priorities": priorities, "next_steps": next_steps,
                          "rule_set": rule_set_name},
        "disclaimer": {"rule_set": rs["disclaimer"], "points": list(t.disclaimer_points)},
        # Geometry for the plan renderer (image pixel coordinates).
        "geometry": {"width": a["image_width"], "height": a["image_height"], "centre": a["centre"],
                     "boundary": a["boundary"],
                     "zones": a["zones"], "openings": a["openings"], "north_angle": north},
    }
