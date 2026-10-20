"""Customer insight tools: FitCheck, passport, mistake catcher, score explanation, change history,
daily-life conflicts, family priority, construction stage, post-move verification, expert handoff
and the voice explainer."""
from tests.test_api import create_project, upload, verified_payload


def demo(client, auth):
    r = client.post("/projects/demo", headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def get(client, auth, path, **params):
    r = client.get(path, headers=auth, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_explain_score_adds_up(client, auth):
    p = demo(client, auth)
    ex = get(client, auth, f"/projects/{p['id']}/insights/explain")
    a = get(client, auth, f"/projects/{p['id']}/analysis")
    assert round(ex["overall_exact"]) == a["overall_score"] == ex["overall"]
    # category contributions add up to the overall score
    total = sum(c.get("contribution", 0) for c in ex["categories"] if c["score"] is not None)
    assert abs(total - ex["overall_exact"]) < 1.0
    assert ex["drags"] and all(d["overall_gain"] > 0 for d in ex["drags"])
    assert ex["drags"] == sorted(ex["drags"], key=lambda d: -d["overall_gain"])
    assert ex["ceiling_if_all_issues_resolved"] >= a["overall_score"]
    assert ex["rules"]["triggered"] <= ex["rules"]["approved_in_rule_set"]


def test_passport(client, auth):
    p = demo(client, auth)
    pp = get(client, auth, f"/projects/{p['id']}/insights/passport")
    assert pp["level"] in ("high", "medium", "low")
    assert pp["detection"]["is_mock"] and pp["detection"]["edited"] >= 1  # demo renames "Room" -> Bedroom 2
    assert pp["north"]["is_image_top"]
    sens = pp["uncertainty"]["north_sensitivity"]
    assert sens["score_min"] <= sens["score_now"] <= sens["score_max"]
    assert any("pending" in r["text"] or "reviewed" in r["text"] for r in pp["reasons"])


def test_mistake_catcher_on_detection_and_draft(client, auth):
    p = create_project(client, auth)
    fp = upload(client, auth, p["id"]).json()
    det = get(client, auth, f"/floor-plans/{fp['id']}/checks")
    codes = {c["code"] for c in det["checks"]}
    assert det["subject"] == "detection"
    assert "unclassified_room" in codes  # the mock leaves one room unnamed
    assert "low_confidence_entrance" in codes
    assert "stairs_missing" in codes  # stairs come back separately from rooms

    raw = get(client, auth, f"/floor-plans/{fp['id']}/detection")["detection"]
    draft = verified_payload(raw)
    # introduce mistakes: overlap two rooms, add a second main entrance, mislabel a type
    draft["rooms"][1]["polygon"] = draft["rooms"][0]["polygon"]
    draft["rooms"][2]["room_type"] = "toilet" if draft["rooms"][2]["room_type"] != "toilet" else "kitchen"
    draft["openings"].append({**draft["openings"][0], "is_main_entrance": True, "kind": "door"})
    r = client.post(f"/floor-plans/{fp['id']}/checks", json=draft, headers=auth)
    assert r.status_code == 200, r.text
    codes = {c["code"] for c in r.json()["checks"]}
    assert {"overlapping_rooms", "several_main_entrances", "label_type_mismatch"} <= codes
    assert r.json()["ok"] is False


def test_fitcheck_respects_constraints(client, auth):
    p = demo(client, auth)
    base = get(client, auth, f"/projects/{p['id']}/insights/fitcheck")
    assert base["items"]
    structural = [o for i in base["items"] for o in i["options"] if o["kind"] == "structural"]
    assert structural and all(o["verdict"] == "out_of_scope" for o in structural)

    r = client.put(f"/projects/{p['id']}/insights/context", headers=auth, json={"fit_constraints": {
        "ownership": "tenant", "budget": "high", "allow_structural": True, "allow_services": True,
        "max_disruption": "high"}})
    assert r.status_code == 200, r.text
    fc = get(client, auth, f"/projects/{p['id']}/insights/fitcheck")
    structural = [o for i in fc["items"] for o in i["options"] if o["kind"] == "structural"]
    assert all(o["verdict"] == "conditional" for o in structural)  # tenant: owner permission needed
    assert any("owner" in c for o in structural for c in o["conditions"])

    # planning stage makes structural work cheaper
    client.put(f"/projects/{p['id']}/insights/context", headers=auth,
               json={"fit_constraints": {"budget": "medium", "allow_structural": True, "allow_services": True,
                                         "max_disruption": "high"}, "construction_stage": "planning"})
    fc = get(client, auth, f"/projects/{p['id']}/insights/fitcheck")
    assert any(o["kind"] == "structural" and o["verdict"] == "fits" for i in fc["items"] for o in i["options"])


def test_daily_life_conflicts(client, auth):
    p = demo(client, auth)
    out = get(client, auth, f"/projects/{p['id']}/insights/conflicts")
    assert out["scale_known"] is True  # demo has a built-up area
    assert out["checked_rooms"] >= 1
    for c in out["conflicts"]:
        assert c["severity"] in ("high", "medium", "low") and c["message"] and c["suggestion"]
    assert out["disruptions"]  # demo has issues with a structural option


def test_family_priority_changes_view_not_score(client, auth):
    p = demo(client, auth)
    before = get(client, auth, f"/projects/{p['id']}/analysis")["overall_score"]
    r = client.put(f"/projects/{p['id']}/insights/context", headers=auth,
                   json={"family_profile": {"members": ["elderly", "students"], "focus": ["sleep"]}})
    assert r.status_code == 200
    fam = get(client, auth, f"/projects/{p['id']}/insights/family")
    assert fam["official_score"] == before
    assert fam["family_score"] is not None
    assert fam["rooms"][0]["priority"] == "high"
    assert {m["role"] for m in fam["member_notes"]} == {"elderly", "students"}
    assert get(client, auth, f"/projects/{p['id']}/analysis")["overall_score"] == before
    # clearing works
    client.put(f"/projects/{p['id']}/insights/context", headers=auth, json={"family_profile": None})
    assert get(client, auth, f"/projects/{p['id']}/insights/context")["family_profile"] is None


def test_construction_stage(client, auth):
    p = demo(client, auth)
    none = get(client, auth, f"/projects/{p['id']}/insights/stage")
    assert none["stage"] is None and len(none["stages"]) == 6
    client.put(f"/projects/{p['id']}/insights/context", headers=auth, json={"construction_stage": "planning"})
    plan = get(client, auth, f"/projects/{p['id']}/insights/stage")
    assert plan["act_now"] and all(i["deadline_stage"] for i in plan["act_now"])
    assert plan["checklist"]
    client.put(f"/projects/{p['id']}/insights/context", headers=auth, json={"construction_stage": "occupied"})
    occ = get(client, auth, f"/projects/{p['id']}/insights/stage")
    assert not occ["act_now"] and occ["costly_now"]  # structural options now mean undoing work
    assert client.put(f"/projects/{p['id']}/insights/context", headers=auth,
                      json={"construction_stage": "roofing"}).status_code == 422


def test_history_and_compare(client, auth):
    p = create_project(client, auth)
    fp = upload(client, auth, p["id"]).json()
    det = get(client, auth, f"/floor-plans/{fp['id']}/detection")["detection"]
    client.put(f"/floor-plans/{fp['id']}/verification", json=verified_payload(det), headers=auth)
    client.put(f"/floor-plans/{fp['id']}/north", json={"north_angle": 0}, headers=auth)
    client.post(f"/floor-plans/{fp['id']}/run-analysis", headers=auth)
    client.put(f"/floor-plans/{fp['id']}/north", json={"north_angle": 90}, headers=auth)
    client.post(f"/floor-plans/{fp['id']}/run-analysis", headers=auth)
    h = get(client, auth, f"/projects/{p['id']}/insights/history")["versions"]
    assert [v["version"] for v in h] == [1, 2] and h[-1]["is_latest"]
    cmp = get(client, auth, f"/projects/{p['id']}/insights/history/compare", old=h[0]["id"], new=h[1]["id"])
    assert cmp["north_changed"] and cmp["rooms"]["moved_zone"]
    assert cmp["score_delta"] == h[1]["overall_score"] - h[0]["overall_score"]
    f = cmp["findings"]
    assert f["improved"] or f["worsened"] or f["resolved"] or f["new_issues"]


def test_post_move_verification_and_apply(client, auth):
    p = demo(client, auth)
    data = get(client, auth, f"/projects/{p['id']}/site-verifications")
    assert data["plan_rooms"] and data["issues"] and data["verifications"] == []
    study = next(r for r in data["plan_rooms"] if r["room_type"] == "bedroom")
    issue = data["issues"][0]["finding_id"]
    r = client.post(f"/projects/{p['id']}/site-verifications", headers=auth, json={
        "compass_north_angle": 40, "entrance_confirmed": True,
        "items": [{"room_id": study["id"], "actual_room_type": "study"}],
        "remedy_progress": {issue: "done"}})
    assert r.status_code == 201, r.text
    sv = r.json()
    assert sv["verdict"] == "re_run" and sv["north"]["agrees"] is False
    assert sv["retyped_rooms"][0]["actual"] == "Study"
    assert sv["as_built"]["used_site_north"] is True
    assert sv["remedies"]["tally"]["done"] == 1 and sv["remedies"]["percent_done"] > 0

    # the passport now reports the compass disagreement
    pp = get(client, auth, f"/projects/{p['id']}/insights/passport")
    assert pp["north"]["site_check"]["agrees"] is False and pp["level"] == "low"

    r = client.post(f"/projects/{p['id']}/site-verifications/{sv['id']}/apply", headers=auth,
                    json={"use_site_north": True})
    assert r.status_code == 200, r.text
    assert r.json()["applied_rooms"] == 1 and r.json()["used_site_north"]
    a = get(client, auth, f"/projects/{p['id']}/analysis")
    assert a["north_angle"] == 40 and any(x["room_type"] == "study" for x in a["rooms"])
    assert len(get(client, auth, f"/projects/{p['id']}/insights/history")["versions"]) == 2


def test_expert_review_handoff(client, auth, other_auth):
    p = demo(client, auth)
    r = client.post(f"/projects/{p['id']}/expert-reviews", headers=auth,
                    json={"expert_name": "A. Joshi", "message": "Please check the kitchen.", "valid_days": 7})
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    # public, no auth
    pub = client.get(f"/expert-review/{token}")
    assert pub.status_code == 200, pub.text
    pack = pub.json()["pack"]
    assert pack["findings"] and pack["questions"] and pack["plan"]["rooms"]
    assert pack["project"]["address"] is None  # contact details not shared unless asked
    fid = pack["findings"][0]["id"]
    fb = client.post(f"/expert-review/{token}/feedback", json={
        "verdict": "agree_with_changes", "summary": "Mostly right.", "north_confirmed": False,
        "items": {fid: {"agree": False, "comment": "Check on site."}}, "signature": "A. Joshi"})
    assert fb.status_code == 200, fb.text
    mine = get(client, auth, f"/projects/{p['id']}/expert-reviews")
    assert mine[0]["status"] == "submitted" and mine[0]["feedback"]["items"][fid]["agree"] is False
    # other users can't list it; revoke kills the link
    assert client.get(f"/projects/{p['id']}/expert-reviews", headers=other_auth).status_code == 404
    client.post(f"/projects/{p['id']}/expert-reviews/{mine[0]['id']}/revoke", headers=auth)
    assert client.get(f"/expert-review/{token}").status_code == 404
    assert client.get("/expert-review/not-a-real-token").status_code == 404


def test_voice_summary_en_mr(client, auth):
    p = demo(client, auth)
    en = get(client, auth, f"/projects/{p['id']}/insights/voice", language="en")
    mr = get(client, auth, f"/projects/{p['id']}/insights/voice", language="mr")
    assert en["voice_lang"] == "en-IN" and mr["voice_lang"] == "mr-IN"
    assert [s["id"] for s in en["segments"]] == [s["id"] for s in mr["segments"]]
    assert "out of 100" in en["full_text"]
    assert "100 पैकी" in mr["full_text"] and "स्वयंपाकघर" in mr["full_text"] or "100 पैकी" in mr["full_text"]
    assert "%" not in mr["speech_text"] and "(" not in mr["speech_text"]
    assert client.get(f"/projects/{p['id']}/insights/voice", headers=auth,
                      params={"language": "fr"}).status_code == 422


def test_summary_and_isolation(client, auth, other_auth):
    p = demo(client, auth)
    s = get(client, auth, f"/projects/{p['id']}/insights/summary")
    assert s["trust_level"] in ("high", "medium", "low") and s["versions"] == 1
    for path in ("summary", "explain", "passport", "fitcheck", "conflicts", "family", "stage", "voice", "history"):
        assert client.get(f"/projects/{p['id']}/insights/{path}", headers=other_auth).status_code == 404


def test_insights_need_analysis(client, auth):
    p = create_project(client, auth)
    r = client.get(f"/projects/{p['id']}/insights/explain", headers=auth)
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_analysis"
