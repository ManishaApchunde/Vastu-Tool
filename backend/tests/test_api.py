import io

from PIL import Image

from app.seed.demo_plan import draw_demo_plan


def create_project(client, auth, name="Test Home"):
    r = client.post("/projects", json={"name": name, "property": {"address": "Pune"}}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def upload(client, auth, pid, data=None, name="plan.png", ctype="image/png"):
    return client.post(f"/projects/{pid}/floor-plan", headers=auth,
                       files={"file": (name, data if data is not None else draw_demo_plan(), ctype)})


def verified_payload(det):
    rooms = [{"label": "Bedroom 2" if r["name"] == "Room" else r["name"], "room_type": r["room_type"],
              "polygon": r["polygon"], "source": "ai"} for r in det["rooms"]]
    rooms += [{"label": "Stairs", "room_type": "staircase", "polygon": s["polygon"], "source": "ai"}
              for s in det["stairs"]]
    openings = [{"kind": o["kind"], "position": o["position"], "is_main_entrance": o["is_main_entrance"]}
                for o in det["doors"] + det["windows"]]
    return {"boundary": det["boundary"], "rooms": rooms, "openings": openings}


def test_auth_required(client):
    assert client.get("/projects").status_code == 401


def test_full_workflow(client, auth):
    p = create_project(client, auth)
    r = upload(client, auth, p["id"])
    assert r.status_code == 201, r.text
    fp = r.json()

    det = client.get(f"/floor-plans/{fp['id']}/detection", headers=auth).json()
    assert det["status"] == "detected" and det["job"]["status"] == "succeeded"
    assert len(det["detection"]["rooms"]) >= 5

    # Analysis is blocked until verification + North
    assert client.put(f"/floor-plans/{fp['id']}/north", json={"north_angle": 0}, headers=auth).status_code == 409
    r = client.put(f"/floor-plans/{fp['id']}/verification", json=verified_payload(det["detection"]), headers=auth)
    assert r.status_code == 200, r.text
    assert client.post(f"/floor-plans/{fp['id']}/run-analysis", headers=auth).json()["error"]["code"] == "missing_north"

    r = client.put(f"/floor-plans/{fp['id']}/north", json={"north_angle": 0}, headers=auth)
    assert r.json()["north"]["north_angle"] == 0
    zones = client.post(f"/floor-plans/{fp['id']}/calculate-zones", headers=auth).json()
    assert len(zones["zones"]) == 9 and zones["centre"]

    a = client.post(f"/floor-plans/{fp['id']}/run-analysis", headers=auth)
    assert a.status_code == 200, a.text
    a = a.json()
    assert 0 <= a["overall_score"] <= 100
    kitchen = next(r for r in a["rooms"] if r["label"] == "Kitchen")
    assert kitchen["zone"] == "SE" and kitchen["rule_result"] == "preferred"
    bath = next(r for r in a["rooms"] if r["label"] == "Bath")
    assert bath["zone"] == "C" and bath["worst_bucket"] == "major" and bath["remedy"]

    assert client.get(f"/projects/{p['id']}/findings?bucket=major", headers=auth).json()
    assert client.get(f"/projects/{p['id']}/remedies", headers=auth).json()

    rep = client.post(f"/projects/{p['id']}/report", headers=auth)
    assert rep.status_code == 202
    rep = client.get(f"/reports/{rep.json()['id']}", headers=auth).json()
    assert rep["status"] == "ready", rep
    pdf = client.get(rep["download_url"].replace("http://localhost:8000", ""))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_rotating_north_changes_zones(client, auth):
    p = create_project(client, auth)
    fp = upload(client, auth, p["id"]).json()
    det = client.get(f"/floor-plans/{fp['id']}/detection", headers=auth).json()["detection"]
    client.put(f"/floor-plans/{fp['id']}/verification", json=verified_payload(det), headers=auth)
    client.put(f"/floor-plans/{fp['id']}/north", json={"north_angle": 180}, headers=auth)
    a = client.post(f"/floor-plans/{fp['id']}/run-analysis", headers=auth).json()
    assert next(r for r in a["rooms"] if r["label"] == "Kitchen")["zone"] == "NW"


def test_other_user_cannot_access(client, auth, other_auth):
    p = create_project(client, auth)
    assert client.get(f"/projects/{p['id']}", headers=other_auth).status_code == 404
    assert upload(client, other_auth, p["id"]).status_code == 404


def test_upload_validation(client, auth):
    p = create_project(client, auth)
    assert upload(client, auth, p["id"], b"hello", "plan.txt", "text/plain").json()["error"]["code"] == "unsupported_format"
    assert upload(client, auth, p["id"], b"not a png", "plan.png").json()["error"]["code"] == "invalid_file"
    tiny = io.BytesIO()
    Image.new("RGB", (50, 50), "white").save(tiny, format="PNG")
    assert upload(client, auth, p["id"], tiny.getvalue()).json()["error"]["code"] == "image_too_small"


def test_pdf_upload(client, auth):
    p = create_project(client, auth)
    img = Image.open(io.BytesIO(draw_demo_plan()))
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    r = upload(client, auth, p["id"], buf.getvalue(), "plan.pdf", "application/pdf")
    assert r.status_code == 201, r.text
    assert r.json()["content_type"] == "application/pdf" and r.json()["width"] > 300


def test_verification_rejects_bad_geometry(client, auth):
    p = create_project(client, auth)
    fp = upload(client, auth, p["id"]).json()
    r = client.put(f"/floor-plans/{fp['id']}/verification", headers=auth,
                   json={"rooms": [], "openings": []})
    assert r.json()["error"]["code"] == "missing_rooms"
    r = client.put(f"/floor-plans/{fp['id']}/verification", headers=auth,
                   json={"rooms": [{"label": "X", "room_type": "living",
                                    "polygon": [[0, 0], [10, 10], [0, 0]]}]})
    assert r.json()["error"]["code"] == "invalid_geometry"


def test_detection_failure_and_retry(client, auth, monkeypatch):
    from app.ai import factory
    from app.ai.base import AIDetectionError
    from app.ai.mock import MockFloorPlanAnalyzer

    class Broken(MockFloorPlanAnalyzer):
        def analyze_floor_plan(self, *a, **k):
            raise AIDetectionError("provider down")

    monkeypatch.setattr(factory, "MockFloorPlanAnalyzer", Broken)
    p = create_project(client, auth)
    fp = upload(client, auth, p["id"]).json()
    det = client.get(f"/floor-plans/{fp['id']}/detection", headers=auth).json()
    assert det["status"] == "detection_failed" and det["job"]["can_retry"]
    assert det["job"]["error_code"] == "ai_detection_failed"

    monkeypatch.setattr(factory, "MockFloorPlanAnalyzer", MockFloorPlanAnalyzer)
    r = client.post(f"/jobs/{det['job']['id']}/retry", headers=auth)
    assert r.status_code == 202
    assert client.get(f"/floor-plans/{fp['id']}/detection", headers=auth).json()["status"] == "detected"


def test_expired_file_link_rejected(client):
    r = client.get("/files/users/x/preview.png?exp=1&sig=bad")
    assert r.status_code == 403


def test_demo_project_endpoint(client, auth):
    r = client.post("/projects/demo", headers=auth)
    assert r.status_code == 201
    a = client.get(f"/projects/{r.json()['id']}/analysis", headers=auth).json()
    assert a["counts"]["major"] >= 1 and a["counts"]["positive"] >= 5
