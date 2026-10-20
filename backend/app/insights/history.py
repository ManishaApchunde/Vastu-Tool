"""Vastu Change History: every analysis run of a project is kept, so versions of the plan can be
compared by score, category, rooms and findings."""
RANK = {"preferred": 3, "acceptable": 2, "not_evaluated": 1, "issue": 0}
SEV = {"low": 2, "medium": 1, "high": 0}


def versions(project, analyses) -> list[dict]:
    plans = {fp.id: fp for fp in project.floor_plans}
    latest = analyses[-1].id if analyses else None
    out = []
    for i, an in enumerate(analyses, 1):
        fp = plans.get(an.floor_plan_id)
        snap = an.input_snapshot or {}
        out.append({"id": an.id, "version": i, "created_at": an.created_at.isoformat(),
                    "overall_score": round(an.overall_score) if an.overall_score is not None else None,
                    "category_scores": an.category_scores, "counts": an.counts, "north_angle": an.north_angle,
                    "rooms": len(snap.get("rooms", [])), "floor_plan_id": an.floor_plan_id,
                    "plan_file": fp.original_filename if fp else None, "is_latest": an.id == latest,
                    "room_labels": [r["label"] for r in snap.get("rooms", [])]})
    return out


def _key(f: dict) -> tuple:
    return (f.get("rule_code") or "unscored", f["subject_type"], f["subject_label"].strip().lower())


def _subject_key(f: dict) -> tuple:
    return (f["category"], f["subject_type"], f["subject_label"].strip().lower())


def _better(a: dict, b: dict) -> int:
    """>0 if b is better than a."""
    ra, rb = RANK[a["status"]], RANK[b["status"]]
    if ra != rb:
        return rb - ra
    if a["status"] == b["status"] == "issue":
        return SEV.get(b["severity"], 0) - SEV.get(a["severity"], 0)
    return 0


def compare(old: dict, new: dict) -> dict:
    """old/new are analysis_out() dicts."""
    cats = sorted(set(old["category_scores"] or {}) | set(new["category_scores"] or {}))
    cat_delta = []
    for c in cats:
        o, n = (old["category_scores"] or {}).get(c), (new["category_scores"] or {}).get(c)
        cat_delta.append({"category": c, "old": o, "new": n,
                          "delta": (n - o) if o is not None and n is not None else None})

    # Findings matched by subject (room/entrance/zone + category), so a room that moved to a better
    # zone shows as 'improved' even though a different rule now applies.
    old_by = {_subject_key(f): f for f in old["findings"]}
    new_by = {_subject_key(f): f for f in new["findings"]}
    improved, worsened, resolved, new_issues, unchanged = [], [], [], [], 0
    for k in set(old_by) | set(new_by):
        o, n = old_by.get(k), new_by.get(k)
        if o and n:
            d = _better(o, n)
            entry = {"subject": n["subject_label"], "old": o["finding"], "new": n["finding"],
                     "old_bucket": o["bucket"], "new_bucket": n["bucket"]}
            if d > 0:
                improved.append(entry)
            elif d < 0:
                worsened.append(entry)
            else:
                unchanged += 1
        elif o and o["status"] == "issue":
            resolved.append({"subject": o["subject_label"], "finding": o["finding"], "bucket": o["bucket"]})
        elif n and n["status"] == "issue":
            new_issues.append({"subject": n["subject_label"], "finding": n["finding"], "bucket": n["bucket"]})

    old_rooms = {r["label"].strip().lower(): r for r in old["rooms"]}
    new_rooms = {r["label"].strip().lower(): r for r in new["rooms"]}
    moved, retyped = [], []
    for k in set(old_rooms) & set(new_rooms):
        o, n = old_rooms[k], new_rooms[k]
        if o["zone"] != n["zone"]:
            moved.append({"room": n["label"], "old_zone": o["zone_name"], "new_zone": n["zone_name"]})
        if o["room_type"] != n["room_type"]:
            retyped.append({"room": n["label"], "old_type": o["room_type_label"], "new_type": n["room_type_label"]})
    o_score, n_score = old["overall_score"], new["overall_score"]
    return {
        "old": {"id": old["id"], "created_at": old["created_at"], "overall_score": o_score,
                "north_angle": old["north_angle"]},
        "new": {"id": new["id"], "created_at": new["created_at"], "overall_score": n_score,
                "north_angle": new["north_angle"]},
        "score_delta": (n_score - o_score) if o_score is not None and n_score is not None else None,
        "north_changed": abs((old["north_angle"] or 0) - (new["north_angle"] or 0)) > 0.01,
        "categories": cat_delta,
        "findings": {"improved": improved, "worsened": worsened, "resolved": resolved, "new_issues": new_issues,
                     "unchanged": unchanged},
        "rooms": {"added": sorted(new_rooms[k]["label"] for k in set(new_rooms) - set(old_rooms)),
                  "removed": sorted(old_rooms[k]["label"] for k in set(old_rooms) - set(new_rooms)),
                  "moved_zone": moved, "retyped": retyped},
    }


def analysis_view(an) -> dict:
    """A self-contained view of one analysis built only from what was stored with it (its findings and
    input snapshot), so old versions compare correctly after the plan has been re-verified."""
    from app.geometry.zones import ZONE_NAMES
    from app.services.serializers import finding_out
    from app.vastu.room_types import ROOM_TYPES

    findings = [finding_out(f) for f in an.findings]
    placement = {f["subject_ref"]: f for f in findings if f["subject_type"] == "room" and f["category"] == "rooms"}
    rooms = []
    for r in (an.input_snapshot or {}).get("rooms", []):
        f = placement.get(r["id"])
        zone = f["zone"] if f else None
        rooms.append({"id": r["id"], "label": r["label"], "room_type": r["room_type"],
                      "room_type_label": ROOM_TYPES.get(r["room_type"], r["room_type"]),
                      "zone": zone, "zone_name": ZONE_NAMES.get(zone, zone)})
    return {"id": an.id, "created_at": an.created_at.isoformat(),
            "overall_score": round(an.overall_score) if an.overall_score is not None else None,
            "category_scores": an.category_scores, "north_angle": an.north_angle, "findings": findings,
            "rooms": rooms}
