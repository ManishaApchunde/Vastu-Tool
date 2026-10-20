"""Transparent score calculation.

Each scored finding has a weight (from its rule) and earns `weight * points`, where points come
from the scoring config (e.g. preferred = 1.0, issue/high = 0). A category's score is
earned / possible * 100. The overall score is the weighted mean of category scores that have at
least one scored finding. Every number is returned in the breakdown so the UI/PDF can show how
the score was built."""
from app.vastu.types import FindingResult

DEFAULT_SCORING = {
    "status_points": {"preferred": 1.0, "acceptable": 0.75},
    "issue_points": {"low": 0.5, "medium": 0.25, "high": 0.0},
    "category_weights": {"rooms": 0.30, "entrance": 0.20, "zones": 0.20, "layout": 0.15, "directions": 0.15},
    "category_labels": {"rooms": "Rooms", "entrance": "Entrance", "zones": "Zones",
                        "layout": "Layout", "directions": "Directions"},
}


def points_for(f: FindingResult, cfg: dict) -> float | None:
    if f.status in cfg["status_points"]:
        return float(cfg["status_points"][f.status])
    if f.status == "issue":
        return float(cfg["issue_points"].get(f.severity, 0.0))
    return None  # not scored


def score(findings: list[FindingResult], cfg: dict | None = None) -> dict:
    cfg = cfg or DEFAULT_SCORING
    cats: dict[str, dict] = {c: {"earned": 0.0, "possible": 0.0, "items": 0} for c in cfg["category_weights"]}
    for f in findings:
        pts = points_for(f, cfg)
        if pts is None or f.weight <= 0:
            f.earned = 0.0
            continue
        f.earned = round(f.weight * pts, 3)
        bucket = cats.setdefault(f.category, {"earned": 0.0, "possible": 0.0, "items": 0})
        bucket["earned"] += f.earned
        bucket["possible"] += f.weight
        bucket["items"] += 1

    category_scores, breakdown = {}, []
    weighted, weight_sum = 0.0, 0.0
    for code, data in cats.items():
        cat_weight = float(cfg["category_weights"].get(code, 0.0))
        value = round(100 * data["earned"] / data["possible"]) if data["possible"] else None
        category_scores[code] = value
        breakdown.append({
            "category": code, "label": cfg.get("category_labels", {}).get(code, code.title()),
            "earned": round(data["earned"], 2), "possible": round(data["possible"], 2),
            "findings": data["items"], "category_weight": cat_weight, "score": value,
        })
        if value is not None and cat_weight > 0:
            weighted += value * cat_weight
            weight_sum += cat_weight

    overall = round(weighted / weight_sum) if weight_sum else None
    counts = {b: sum(1 for f in findings if f.bucket == b) for b in ("positive", "warning", "major", "info")}
    return {
        "overall": overall,
        "category_scores": category_scores,
        "breakdown": {"categories": breakdown, "method": "weighted mean of category scores (earned / possible)",
                      "config": {k: cfg[k] for k in ("status_points", "issue_points", "category_weights")}},
        "counts": counts,
    }
