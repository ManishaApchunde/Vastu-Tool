"""Report model, phase mapping and PDF generation tests.

The report must be a pure presentation of the stored analysis: room scores come from the room's own
findings, remedies come from the catalogue, and the PDF length follows the property."""
import io

import pytest
from pypdf import PdfReader

from app.core.db import SessionLocal
from app.models import Project, User
from app.remedies.engine import phase_for
from app.reports.pdf import build_pdf
from app.reports.plan_render import render_report_plan
from app.reports.report_data import build_report_data
from app.services.storage import get_storage


@pytest.fixture
def demo(client, auth):
    r = client.post("/projects/demo", headers=auth)
    assert r.status_code == 201, r.text
    db = SessionLocal()
    project = db.get(Project, r.json()["id"])
    yield db, project
    db.close()


def _report(db, project):
    return build_report_data(db, project.analyses[-1], project)


def test_phase_mapping():
    assert phase_for({"priority": "high"}) == "immediate"
    assert phase_for({"priority": "medium"}) == "short_term"
    assert phase_for({"priority": "low"}) == "medium_term"
    assert phase_for({"priority": "high", "kind": "optional"}) == "medium_term"
    assert phase_for({"priority": "low", "kind": "structural"}) == "long_term"
    assert phase_for({"priority": "low", "phase": "immediate"}) == "immediate"  # curated phase wins


def test_room_scores_follow_the_rooms_own_findings(demo):
    db, project = demo
    r = _report(db, project)
    analysis = project.analyses[-1]
    for room in r["rooms"]:
        own = [f for f in analysis.findings if f.subject_ref == room["id"] and f.status != "not_evaluated"]
        if not own:
            assert room["score"] is None and room["tone"] == "neutral"
            continue
        expected = round(100 * sum(f.earned for f in own) / sum(f.weight for f in own))
        assert room["score"] == expected


def test_result_labels_match_rule_outcomes(demo):
    db, project = demo
    rooms = {r["label"]: r for r in _report(db, project)["rooms"]}
    bath = rooms["Bath"]  # toilet in the Brahmasthan: high-severity issue in the demo plan
    assert (bath["tone"], bath["result"], bath["score"]) == ("major", "Unfavourable", 0)
    assert rooms["Staircase"]["result"] == "Needs attention"
    assert rooms["Kitchen"]["result"] == "Highly auspicious"  # South-East is preferred for kitchens
    # attention-first numbering, consistent across plan, tables and cards
    tones = [r["tone"] for r in sorted(rooms.values(), key=lambda x: x["number"])]
    assert tones.index("major") < tones.index("positive")


def test_recommendations_come_only_from_the_catalogue(demo):
    db, project = demo
    r = _report(db, project)
    codes = {f.remedy_snapshot["code"] for f in project.analyses[-1].findings if f.remedy_snapshot}
    for room in r["rooms"]:
        for rec in room["recommendations"]:
            assert rec["code"] in codes
    # structural notes become separate long-term items and are flagged for professional advice
    long_term = next(p for p in r["remedy_plan"] if p["key"] == "long_term")["items"]
    assert long_term and all(i["structural"] for i in long_term)
    assert all(rem["needs_professional"] for rem in r["remedies"] if rem["structural_note"])


def test_text_is_generated_from_data(demo):
    db, project = demo
    r = _report(db, project)
    assert str(r["overall_score"]) in r["executive_summary"][1]
    bath = next(x for x in r["rooms"] if x["label"] == "Bath")
    assert "Centre (Brahmasthan)" in bath["introduction"][0]
    assert any("North-West" in s for s in bath["introduction"])  # preferred zones read from the rules


def test_pdf_builds_and_length_follows_room_count(demo):
    db, project = demo
    r = _report(db, project)
    image = get_storage().get(project.floor_plans[-1].preview_key)
    plan = render_report_plan(image, r)
    thumbs = {room["id"]: render_report_plan(image, r, highlight=room["id"], max_side=600) for room in r["rooms"]}
    full = PdfReader(io.BytesIO(build_pdf(r, plan, thumbs)))
    text = "".join(p.extract_text() for p in full.pages)
    for needle in ("Vastu Evaluation Report", "Room-wise Vastu compliance overview", "Phase-wise remedial",
                   "Disclaimer", f"{r['overall_score']} / 100"):
        assert needle in text
    for room in r["rooms"]:
        assert f"Room {room['number']}: {room['label']} assessment" in text

    small = dict(r, rooms=r["rooms"][:2])
    short = PdfReader(io.BytesIO(build_pdf(small, plan, thumbs)))
    assert len(short.pages) < len(full.pages)


def test_report_job_produces_downloadable_pdf(client, auth):
    p = client.post("/projects/demo", headers=auth).json()
    rep = client.post(f"/projects/{p['id']}/report", headers=auth)
    assert rep.status_code == 202
    rep = client.get(f"/reports/{rep.json()['id']}", headers=auth).json()
    assert rep["status"] == "ready", rep
    pdf = client.get(rep["download_url"].replace("http://localhost:8000", ""))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert len(PdfReader(io.BytesIO(pdf.content)).pages) >= 8


def test_client_name_on_property(client, auth):
    r = client.post("/projects", headers=auth, json={"name": "Flat 402", "property": {"client_name": "A. Client"}})
    assert r.status_code == 201
    assert r.json()["property"]["client_name"] == "A. Client"
