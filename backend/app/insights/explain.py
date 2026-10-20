"""Explain the Score: how the official score was built, finding by finding.

Everything is arithmetic on the stored findings and the scoring config saved with the analysis, so
the numbers here always add up to the score on the dashboard and in the PDF."""
from app.insights.common import overall_from, points_for


def _what_if_resolved(findings: list[dict], target: dict, cfg: dict) -> float | None:
    changed = [dict(f, status="preferred", severity="positive") if f["id"] == target["id"] else f for f in findings]
    return overall_from(changed, cfg)[0]


def explain_score(a: dict, cfg: dict, approved_rule_codes: list[str]) -> dict:
    findings = a["findings"]
    base, _ = overall_from(findings, cfg)
    labels = {c["category"]: c for c in (a.get("score_breakdown") or {}).get("categories", [])}

    categories = []
    for code, weight in cfg["category_weights"].items():
        items = []
        for f in findings:
            if f["category"] != code:
                continue
            pts = points_for(f["status"], f["severity"], cfg)
            if pts is None or not f["weight"]:
                continue
            items.append({
                "finding_id": f["id"], "subject": f["subject_label"], "finding": f["finding"],
                "status": f["status"], "severity": f["severity"], "rule_code": f["rule_code"],
                "weight": f["weight"], "points": pts, "earned": round(f["weight"] * pts, 2),
                "lost": round(f["weight"] * (1 - pts), 2), "explanation": f["explanation"],
            })
        items.sort(key=lambda x: -x["lost"])
        c = labels.get(code, {})
        categories.append({
            "category": code, "label": c.get("label", code.title()), "category_weight": weight,
            "score": c.get("score"), "earned": c.get("earned", 0), "possible": c.get("possible", 0),
            "share_of_overall": None, "items": items,
        })
    scored_weight = sum(c["category_weight"] for c in categories if c["score"] is not None) or 1
    for c in categories:
        if c["score"] is not None:
            c["share_of_overall"] = round(c["category_weight"] / scored_weight, 3)
            c["contribution"] = round(c["score"] * c["share_of_overall"], 1)

    drags = []
    for f in findings:
        if f["status"] != "issue" or not f["weight"]:
            continue
        after = _what_if_resolved(findings, f, cfg)
        if after is None or base is None:
            continue
        drags.append({"finding_id": f["id"], "subject": f["subject_label"], "finding": f["finding"],
                      "category": f["category"], "severity": f["severity"], "bucket": f["bucket"],
                      "overall_gain": round(after - base, 1),
                      "structural_only": bool((f.get("remedy") or {}).get("structural_note"))})
    drags.sort(key=lambda d: -d["overall_gain"])

    all_resolved = overall_from([dict(f, status="preferred", severity="positive") if f["status"] == "issue" else f
                                 for f in findings], cfg)[0]
    triggered = sorted({f["rule_code"] for f in findings if f["rule_code"]})
    return {
        "overall": a["overall_score"],
        "overall_exact": round(base, 2) if base is not None else None,
        "steps": [
            "Each rule that applies to your plan produces a finding with a weight (how much the rule matters).",
            f"A finding earns weight × points: preferred {cfg['status_points'].get('preferred', 1)}, acceptable "
            f"{cfg['status_points'].get('acceptable', 0.75)}, issue {cfg['issue_points'].get('low', 0.5)} / "
            f"{cfg['issue_points'].get('medium', 0.25)} / {cfg['issue_points'].get('high', 0)} for low / medium / high severity.",
            "Each category score is the points it earned divided by the points it could earn.",
            "The overall score is the weighted average of the categories that have at least one scored finding.",
            "Rooms with no matching rule are listed as not scored; they neither raise nor lower the score.",
        ],
        "points": {"status_points": cfg["status_points"], "issue_points": cfg["issue_points"],
                   "category_weights": cfg["category_weights"]},
        "categories": categories,
        "drags": drags,
        "ceiling_if_all_issues_resolved": round(all_resolved) if all_resolved is not None else None,
        "not_scored": [{"subject": f["subject_label"], "finding": f["finding"]}
                       for f in findings if f["status"] == "not_evaluated"],
        "rules": {"approved_in_rule_set": len(approved_rule_codes), "triggered": len(triggered),
                  "triggered_codes": triggered,
                  "not_triggered": len(set(approved_rule_codes) - set(triggered))},
        "note": "What-if gains assume the finding's rule outcome becomes 'preferred' (for example after a "
                "relocation). Everyday remedies ease an issue but do not change where a room is, so they do not "
                "change the score.",
    }
