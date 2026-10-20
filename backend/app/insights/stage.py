"""Construction Stage Assistant: what to do about each finding at the current building stage.

Each stage lists which kinds of work are still cheap (data/stages.json). A remedy option that is
cheap now but stops being cheap at a later stage is flagged 'act now', with the stage it must be
done before. Generic site checks for the stage are shown when they relate to this plan."""
from app.insights.common import load_data, remedy_fit


def _last_cheap(requires: set, order: list, stages: dict, start: int) -> int | None:
    last = None
    for i in range(start, len(order)):
        if requires <= set(stages[order[i]]["cheap"]):
            last = i
        else:
            break
    return last


def stage_plan(a: dict, stage: str | None, gains: dict | None = None, language: str = "en") -> dict:
    doc = load_data("stages")
    order, stages = doc["order"], doc["stages"]
    stage = stage if stage in stages else None
    out = {"stage": stage, "stages": [{"code": s, "label": stages[s]["label"], "label_mr": stages[s]["label_mr"],
                                       "description": stages[s]["description"]} for s in order]}
    if stage is None:
        return {**out, "act_now": [], "anytime": [], "costly_now": [], "checklist": [], "next_stage": None,
                "becomes_costly_next": []}
    idx = order.index(stage)
    gains = gains or {}
    act_now, anytime, costly = [], [], []
    for f in a["findings"]:
        r = f.get("remedy")
        if f["status"] != "issue" or not r:
            continue
        meta = remedy_fit(r)
        for kind, opt, text in (("everyday", meta["everyday"], r["recommendation"]),
                                ("structural", meta["structural"], r.get("structural_note"))):
            if not opt or not text:
                continue
            req = set(opt["requires"])
            last = _last_cheap(req, order, stages, idx)
            item = {"finding_id": f["id"], "subject": f["subject_label"], "finding": f["finding"],
                    "bucket": f["bucket"], "option": kind, "text": text, "requires": sorted(req),
                    "score_gain": gains.get(f["id"]) if kind == "structural" else None}
            if last is None:
                costly.append({**item, "why": "This stage is past the point where this is cheap; it now means "
                                              "undoing finished work."})
            elif last == len(order) - 1:
                anytime.append(item)
            else:
                deadline = order[last + 1]
                act_now.append({**item, "deadline_stage": deadline, "deadline_label": stages[deadline]["label"],
                                "deadline_label_mr": stages[deadline]["label_mr"],
                                "why": f"Cheap now; becomes costly once you reach "
                                       f"'{stages[deadline]['label']}'."})
    sev = {"major": 0, "warning": 1}
    for lst in (act_now, anytime, costly):
        lst.sort(key=lambda i: (sev.get(i["bucket"], 2), i["option"] != "structural"))

    issue_zones = {f["zone"] for f in a["findings"] if f["status"] == "issue" and f.get("zone")}
    categories = {f["category"] for f in a["findings"]}
    room_types = {r["room_type"] for r in a["rooms"]}
    checklist = []
    for it in stages[stage]["checklist"]:
        t = it.get("topic") or {}
        relevant = it.get("always") or (set(t.get("zones", [])) & issue_zones) or \
            (t.get("category") in categories) or (set(t.get("room_types", [])) & room_types)
        if relevant:
            checklist.append(it["text_mr"] if language == "mr" else it["text"])
    nxt = order[idx + 1] if idx + 1 < len(order) else None
    lost = sorted(set(stages[stage]["cheap"]) - set(stages[nxt]["cheap"])) if nxt else []
    return {**out, "current": {"code": stage, **{k: stages[stage][k] for k in ("label", "label_mr", "description", "description_mr")}},
            "act_now": act_now, "anytime": anytime, "costly_now": costly, "checklist": checklist,
            "next_stage": {"code": nxt, "label": stages[nxt]["label"]} if nxt else None,
            "becomes_costly_next": lost}
