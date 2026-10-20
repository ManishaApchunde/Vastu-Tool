"""Expert Review Handoff: a review pack for a Vastu consultant or architect.

The pack bundles the verified plan, every finding with its rule and remedy, the trust passport,
open plan checks, the household's constraints and a list of questions only an expert on site can
settle. It is shared through an expiring link; the expert can reply per finding, and the reply is
stored for the customer. Nothing the expert writes changes the analysis automatically."""


def questions_for_expert(passport: dict, fit: dict, conflicts: dict, a: dict) -> list[str]:
    q = []
    n = passport["north"]
    if n["is_image_top"] and not n["site_check"]:
        q.append("North was taken as the top of the drawing. Please confirm true North on site.")
    if n["site_check"] and not n["site_check"]["agrees"]:
        q.append(f"The site compass reading differs from the plan by {n['site_check']['difference_deg']}°. "
                 "Which is correct?")
    sens = (passport["uncertainty"] or {}).get("north_sensitivity") or {}
    for r in sens.get("rooms_changing_zone", []):
        q.append(f"{r['label']} is near a zone boundary ({r['zone_now']} vs {', '.join(r['could_be'])}). "
                 "Which zone does it fall in on site?")
    for r in passport["uncertainty"]["borderline_rooms"]:
        q.append(f"{r['label']} spans {r['zone']} ({r['share']:.0%}) and {r['second_zone']} "
                 f"({r['second_share']:.0%}). How should it be read?")
    for label in passport["uncertainty"]["not_scored_rooms"]:
        q.append(f"No rule covers {label}. Is its placement acceptable?")
    for label in passport["uncertainty"]["placeholder_remedies"]:
        q.append(f"There is no approved remedy for the issue at {label}. What do you suggest?")
    for i in fit.get("items", []):
        if i["verdict"] == "out_of_scope" and i["bucket"] == "major":
            q.append(f"{i['subject']}: no remedy fits the household's limits. Is there an alternative?")
    for c in conflicts.get("conflicts", []):
        if c["severity"] == "high":
            q.append(f"{c['room']}: {c['message']} What position would you suggest instead?")
    return q


def build_pack(*, project, a: dict, passport: dict, checks: dict, explain: dict, fit: dict, conflicts: dict,
               family: dict | None, stage: dict | None, message: str | None, include_contact: bool) -> dict:
    prop = project.property
    return {
        "project": {"name": project.name,
                    "property_type": prop.property_type if prop else None,
                    "built_up_area_sqft": prop.built_up_area_sqft if prop else None,
                    "address": prop.address if prop and include_contact else None,
                    "client_name": prop.client_name if prop and include_contact else None},
        "message": message,
        "analysis": {k: a[k] for k in ("id", "created_at", "overall_score", "category_scores", "counts",
                                       "north_angle", "rule_set", "score_breakdown")},
        "plan": {k: a[k] for k in ("image_url", "image_width", "image_height", "zones", "centre", "boundary",
                                   "openings")} | {
            "rooms": [{k: r[k] for k in ("id", "label", "room_type", "room_type_label", "polygon", "zone",
                                         "zone_name", "direction", "worst_bucket")} for r in a["rooms"]]},
        "findings": [{k: f[k] for k in ("id", "rule_code", "category", "subject_label", "zone_name", "status",
                                        "severity", "bucket", "finding", "explanation", "remedy")}
                     for f in a["findings"]],
        "passport": {k: passport[k] for k in ("level", "reasons", "strengths", "north", "detection", "uncertainty")},
        "plan_checks": [c for c in checks["checks"] if c["severity"] != "info"],
        "score_drags": explain["drags"],
        "household": {"constraints": fit["constraints"], "construction_stage": (stage or {}).get("current"),
                      "family": (family or {}).get("profile")},
        "questions": questions_for_expert(passport, fit, conflicts, a),
        "conflicts": conflicts["conflicts"],
    }


def review_out(r, *, with_feedback: bool = True) -> dict:
    return {"id": r.id, "analysis_id": r.analysis_id, "expert_name": r.expert_name, "expert_role": r.expert_role,
            "message": r.message, "status": r.status, "expires_at": r.expires_at.isoformat(),
            "created_at": r.created_at.isoformat(),
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "reviewer_signature": r.reviewer_signature, "include_contact": bool(r.include_contact),
            "feedback": r.feedback if with_feedback else None}
