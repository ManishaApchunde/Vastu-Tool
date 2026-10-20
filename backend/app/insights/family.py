"""Family Priority Mode: the same analysis, viewed through what matters to this household.

Members (elderly parents, students, someone working from home…) and goals (better sleep, study…)
raise the importance of particular rooms. The tool re-orders advice and computes a separate
'family view' score with those rooms weighted up. The official score is never changed."""
from app.insights.common import load_data, overall_from

SEVERITY = {"high": 0, "medium": 1, "low": 2}


def family_view(a: dict, cfg: dict, profile: dict | None) -> dict:
    doc = load_data("family")
    mult = doc["multipliers"]
    profile = profile or {}
    members = [m for m in profile.get("members", []) if m in doc["roles"]]
    focus = [x for x in profile.get("focus", []) if x in doc["focus"]]
    explicit = {k: v for k, v in (profile.get("room_priority") or {}).items() if v in mult}

    boosted_types, boosted_cats, why = set(), set(), {}
    for m in members:
        for t in doc["roles"][m]["room_types"]:
            boosted_types.add(t)
            why.setdefault(t, []).append(doc["roles"][m]["label"])
    for x in focus:
        for t in doc["focus"][x].get("room_types", []):
            boosted_types.add(t)
            why.setdefault(t, []).append(doc["focus"][x]["label"])
        boosted_cats.update(doc["focus"][x].get("categories", []))

    def level(f: dict) -> str:
        if f.get("subject_ref") in explicit:
            return explicit[f["subject_ref"]]
        if f.get("room_type") in boosted_types or f["category"] in boosted_cats:
            return "high"
        return "normal"

    findings = a["findings"]
    family_score, _ = overall_from(findings, cfg, weight_of=lambda f: mult[level(f)])
    rooms = []
    for r in a["rooms"]:
        lvl = explicit.get(r["id"]) or ("high" if r["room_type"] in boosted_types else "normal")
        rooms.append({"id": r["id"], "label": r["label"], "room_type": r["room_type"],
                      "room_type_label": r["room_type_label"], "priority": lvl,
                      "priority_source": "you" if r["id"] in explicit else ("family" if lvl == "high" else "default"),
                      "because": why.get(r["room_type"], []), "worst_bucket": r["worst_bucket"],
                      "finding": r["finding"]})
    rooms.sort(key=lambda r: ({"high": 0, "normal": 1, "low": 2}[r["priority"]], r["label"]))

    actions = [f for f in findings if f["status"] == "issue"]
    actions.sort(key=lambda f: (-mult[level(f)], SEVERITY.get(f["severity"], 3), -(f["weight"] or 0)))
    member_notes = []
    for m in members:
        role = doc["roles"][m]
        rel = [f for f in findings if f.get("room_type") in role["room_types"] and f["status"] != "not_evaluated"]
        member_notes.append({
            "role": m, "label": role["label"], "label_mr": role["label_mr"], "note": role["note"],
            "issues": [{"finding_id": f["id"], "subject": f["subject_label"], "finding": f["finding"],
                        "bucket": f["bucket"]} for f in rel if f["status"] == "issue"],
            "positives": [{"subject": f["subject_label"], "finding": f["finding"]} for f in rel
                          if f["status"] in ("preferred", "acceptable")],
        })
    return {
        "profile": {"members": members, "focus": focus, "room_priority": explicit},
        "options": {"roles": {k: {"label": v["label"], "label_mr": v["label_mr"]} for k, v in doc["roles"].items()},
                    "focus": {k: {"label": v["label"], "label_mr": v["label_mr"]} for k, v in doc["focus"].items()}},
        "official_score": a["overall_score"],
        "family_score": round(family_score) if family_score is not None else None,
        "rooms": rooms,
        "priority_actions": [{"finding_id": f["id"], "subject": f["subject_label"], "finding": f["finding"],
                              "bucket": f["bucket"], "priority": level(f),
                              "recommendation": (f.get("remedy") or {}).get("recommendation")} for f in actions],
        "member_notes": member_notes,
        "note": "The family view weights your priority rooms ×2 and low-priority rooms ×0.5. It is a personal "
                "lens on the same findings; the official score and the PDF report are unchanged.",
    }
