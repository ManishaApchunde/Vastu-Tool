"""Vastu Trust & Accuracy Passport: how much to trust this analysis, and why.

It reports where North came from, how much of the plan the AI drew versus what people corrected,
and how sensitive the result is (a North reading 10 degrees off, rooms that straddle two zones,
rooms no rule covers, remedies without an approved catalogue entry)."""
from app.geometry.primitives import GeometryError
from app.geometry.zones import ZONE_NAMES
from app.insights.common import angle_diff, plan_input_from_snapshot, simulate
from app.insights.mistakes import check_plan

SENSITIVITY_DEG = 10.0

# Reasons are stored as codes so the PDF and the video can word them in English or Marathi.
REASONS = {
    "en": {
        "stale": "The plan or North changed after this analysis; re-run it.",
        "north_unconfirmed": "North is not confirmed.",
        "compass_disagrees": "The on-site compass reading differs from the plan's North by {deg}°.",
        "north_image_top": "North is the top of the image and has not been checked on site.",
        "mock_detector": "Rooms came from the demo (mock) detector, not a real AI reading.",
        "low_confidence": "{n} low-confidence AI room(s) were not reviewed.",
        "rooms_change_zone": "{n} room(s) change zone if North is off by {deg}°.",
        "score_range": "The score ranges {lo}–{hi} within ±{deg}° of North.",
        "borderline": "{n} room(s) sit across two zones.",
        "plan_errors": "{n} plan error(s) found by the Mistake Catcher.",
        "not_scored": "{n} room(s) are not covered by any rule.",
        "no_remedy": "{n} issue(s) have no approved remedy yet.",
        "rules_pending": "The rule set has not yet been reviewed by a Vastu practitioner.",
    },
    "mr": {
        "stale": "या विश्लेषणानंतर आराखडा किंवा उत्तर दिशा बदलली आहे; विश्लेषण पुन्हा चालवा.",
        "north_unconfirmed": "उत्तर दिशा निश्चित केलेली नाही.",
        "compass_disagrees": "प्रत्यक्ष जागेवरील होकायंत्राचे वाचन आराखड्यातील उत्तर दिशेपेक्षा {deg}° वेगळे आहे.",
        "north_image_top": "रेखाचित्राची वरची बाजू उत्तर मानली आहे; ती प्रत्यक्ष जागेवर तपासलेली नाही.",
        "mock_detector": "खोल्या डेमो (नमुना) डिटेक्टरमधून आल्या आहेत, प्रत्यक्ष AI वाचनातून नाहीत.",
        "low_confidence": "कमी खात्रीच्या {n} AI खोल्या तपासलेल्या नाहीत.",
        "rooms_change_zone": "उत्तर दिशा {deg}° ने चुकल्यास {n} खोल्यांचे क्षेत्र बदलते.",
        "score_range": "उत्तर दिशेत {deg}° पर्यंत फरक पडल्यास गुण {lo} ते {hi} दरम्यान बदलतात.",
        "borderline": "{n} खोल्या दोन क्षेत्रांमध्ये विभागलेल्या आहेत.",
        "plan_errors": "AI चूक शोधकाला आराखड्यात {n} त्रुटी आढळल्या.",
        "not_scored": "{n} खोल्यांसाठी कोणताही नियम लागू होत नाही.",
        "no_remedy": "{n} समस्यांसाठी अद्याप मान्यताप्राप्त उपाय नाही.",
        "rules_pending": "हा नियम-संच अद्याप वास्तुतज्ज्ञांनी तपासलेला नाही.",
    },
}
# Marathi wording when the count is one (Marathi nouns and verbs change with number).
REASONS_MR_ONE = {
    "low_confidence": "कमी खात्रीची 1 AI खोली तपासलेली नाही.",
    "rooms_change_zone": "उत्तर दिशा {deg}° ने चुकल्यास 1 खोलीचे क्षेत्र बदलते.",
    "borderline": "1 खोली दोन क्षेत्रांमध्ये विभागलेली आहे.",
    "plan_errors": "AI चूक शोधकाला आराखड्यात 1 त्रुटी आढळली.",
    "not_scored": "1 खोलीसाठी कोणताही नियम लागू होत नाही.",
    "no_remedy": "1 समस्येसाठी अद्याप मान्यताप्राप्त उपाय नाही.",
}
LEVEL_LABELS = {"en": {"high": "High confidence", "medium": "Medium confidence", "low": "Low confidence"},
                "mr": {"high": "उच्च विश्वासार्हता", "medium": "मध्यम विश्वासार्हता", "low": "कमी विश्वासार्हता"}}


def reason_text(code: str, params: dict, language: str = "en") -> str:
    if language == "mr" and params.get("n") == 1 and code in REASONS_MR_ONE:
        return REASONS_MR_ONE[code].format(**params)
    return REASONS[language][code].format(**params)
BORDERLINE_SHARE = 0.6


def build_passport(*, project, analysis, fp, a: dict, rules, catalogue, cfg: dict, rule_set,
                   site=None, stale: bool = False, rules_pending_review: bool = False) -> dict:
    snap = analysis.input_snapshot or {}
    fp_rooms = {r.id: r for r in fp.rooms}
    snap_rooms = snap.get("rooms") or []

    # --- detection provenance -------------------------------------------------------------------
    def source_of(r):
        return r.get("source") or (fp_rooms[r["id"]].source if r["id"] in fp_rooms else "user")

    def conf_of(r):
        if "confidence" in r:
            return r["confidence"]
        return fp_rooms[r["id"]].confidence if r["id"] in fp_rooms else None

    sources = [source_of(r) for r in snap_rooms]
    detection = fp.detection or {}
    detected = len(detection.get("rooms", [])) + len(detection.get("stairs", []))
    from_ai = sum(1 for s in sources if s in ("ai", "ai_edited"))
    confs = [c for c in (conf_of(r) for r in snap_rooms) if c is not None]
    low_unreviewed = [r["label"] for r in snap_rooms if source_of(r) == "ai" and (conf_of(r) or 1) < 0.7]
    provider = snap.get("detection_provider") or fp.detection_provider
    detection_out = {
        "provider": provider, "is_mock": provider == "mock",
        "detected_rooms": detected, "kept_unchanged": sources.count("ai"), "edited": sources.count("ai_edited"),
        "added_by_user": sources.count("user"), "removed": max(0, detected - from_ai),
        "average_confidence": round(sum(confs) / len(confs), 2) if confs else None,
        "low_confidence_unreviewed": low_unreviewed,
        "quality_warnings": (fp.quality or {}).get("warnings", []),
        "openings_by_source": {s: sum(1 for o in snap.get("openings", []) if o.get("source", "user") == s)
                               for s in ("ai", "ai_edited", "user")},
    }

    # --- North ----------------------------------------------------------------------------------
    north = {"angle": analysis.north_angle, "confirmed": bool(fp.north and fp.north.confirmed),
             "confirmed_at": snap.get("north_confirmed_at") or (fp.north.confirmed_at.isoformat()
                                                                if fp.north and fp.north.confirmed_at else None),
             "is_image_top": abs(analysis.north_angle % 360) < 0.01, "site_check": None}
    if site is not None and site.compass_north_angle is not None:
        diff = angle_diff(site.compass_north_angle, analysis.north_angle)
        north["site_check"] = {"compass_angle": site.compass_north_angle, "difference_deg": round(diff, 1),
                               "agrees": diff <= SENSITIVITY_DEG, "recorded_at": site.created_at.isoformat()}

    # --- sensitivity ----------------------------------------------------------------------------
    sensitivity, borderline = None, []
    try:
        plan = plan_input_from_snapshot(snap)
        runs = {d: simulate(plan, analysis.north_angle + d, analysis.zone_system, rules, catalogue, cfg)
                for d in (-SENSITIVITY_DEG, 0.0, SENSITIVITY_DEG)}
        zones_at = {d: {r.id: r.primary_zone for r in run["zr"].rooms} for d, run in runs.items()}
        changing = []
        for r in runs[0.0]["zr"].rooms:
            alts = {zones_at[-SENSITIVITY_DEG][r.id], zones_at[SENSITIVITY_DEG][r.id]} - {r.primary_zone}
            if alts:
                changing.append({"room_id": r.id, "label": r.label, "zone_now": r.primary_zone,
                                 "could_be": sorted(alts)})
            ranked = sorted(r.overlaps.items(), key=lambda kv: -kv[1])
            if ranked and ranked[0][1] < BORDERLINE_SHARE and len(ranked) > 1:
                borderline.append({"room_id": r.id, "label": r.label, "zone": ranked[0][0],
                                   "zone_name": ZONE_NAMES.get(ranked[0][0]), "share": ranked[0][1],
                                   "second_zone": ranked[1][0], "second_share": ranked[1][1]})
        scores = [run["overall"] for run in runs.values() if run["overall"] is not None]
        sensitivity = {"degrees": SENSITIVITY_DEG, "score_now": a["overall_score"],
                       "score_min": min(scores) if scores else None, "score_max": max(scores) if scores else None,
                       "rooms_changing_zone": changing}
    except (GeometryError, KeyError, TypeError):
        sensitivity = None

    not_scored = [f["subject_label"] for f in a["findings"] if f["status"] == "not_evaluated"]
    placeholders = [f["subject_label"] for f in a["findings"] if f.get("remedy") and not f["remedy"].get("approved", True)]
    checks = check_plan(
        rooms=[{"id": r["id"], "label": r["label"], "room_type": r["room_type"], "polygon": r["polygon"],
                "source": source_of(r), "confidence": conf_of(r)} for r in snap_rooms],
        openings=snap.get("openings", []), boundary=snap.get("boundary"), width=fp.width, height=fp.height,
        detection=fp.detection, property_type=project.property.property_type if project.property else None,
        north={"north_angle": analysis.north_angle, "confirmed": north["confirmed"]})

    # --- overall level --------------------------------------------------------------------------
    reasons_down, reasons_up = [], []
    def add(severity: str, code: str, **params):
        reasons_down.append((severity, code, params))

    if stale:
        add("critical", "stale")
    if not north["confirmed"]:
        add("critical", "north_unconfirmed")
    if north["site_check"] and not north["site_check"]["agrees"]:
        add("critical", "compass_disagrees", deg=north["site_check"]["difference_deg"])
    elif north["site_check"]:
        reasons_up.append("An on-site compass reading agrees with the plan's North.")
    elif north["is_image_top"]:
        add("caution", "north_image_top")
    if detection_out["is_mock"]:
        add("caution", "mock_detector")
    if low_unreviewed:
        add("caution", "low_confidence", n=len(low_unreviewed))
    if sensitivity and sensitivity["rooms_changing_zone"]:
        add("caution", "rooms_change_zone", n=len(sensitivity["rooms_changing_zone"]), deg=int(SENSITIVITY_DEG))
    if sensitivity and sensitivity["score_min"] is not None and \
            sensitivity["score_max"] - sensitivity["score_min"] >= 10:
        add("caution", "score_range", lo=sensitivity["score_min"], hi=sensitivity["score_max"], deg=int(SENSITIVITY_DEG))
    if borderline:
        add("caution", "borderline", n=len(borderline))
    if checks["counts"]["error"]:
        add("critical", "plan_errors", n=checks["counts"]["error"])
    if not_scored:
        add("caution", "not_scored", n=len(not_scored))
    if placeholders:
        add("caution", "no_remedy", n=len(placeholders))
    if rules_pending_review:
        add("caution", "rules_pending")
    if detection_out["edited"] or detection_out["added_by_user"]:
        reasons_up.append(f"{detection_out['edited'] + detection_out['added_by_user']} room(s) were corrected or "
                          "added by a person.")
    reasons_up.append("Every room was confirmed by a person before analysis (AI output is never analysed directly).")

    critical = sum(1 for r in reasons_down if r[0] == "critical")
    cautions = sum(1 for r in reasons_down if r[0] == "caution")
    level = "low" if critical else "medium" if cautions >= 2 else "high"
    return {
        "level": level, "stale": stale,
        "reasons": [{"severity": lvl, "code": code, "params": params, "text": reason_text(code, params)}
                    for lvl, code, params in reasons_down],
        "strengths": reasons_up,
        "north": north, "detection": detection_out,
        "uncertainty": {"north_sensitivity": sensitivity, "borderline_rooms": borderline,
                        "not_scored_rooms": not_scored, "placeholder_remedies": placeholders},
        "rule_set": {"name": rule_set.name, "version": rule_set.version, "methodology": rule_set.methodology,
                     "pending_expert_review": rules_pending_review},
        "plan_checks": checks["counts"],
        "analysis_id": analysis.id, "analysed_at": analysis.created_at.isoformat(),
    }
