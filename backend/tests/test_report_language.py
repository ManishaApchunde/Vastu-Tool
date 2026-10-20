"""English / Marathi report tests.

Language changes wording only: the Marathi report must carry exactly the same scores, results,
room order and remedies as the English one, render Devanagari with an embedded Unicode font, and
fail loudly (never fall back to English) if it cannot be generated."""
import io
import re
from datetime import datetime, timezone

import pytest
from pypdf import PdfReader

from app.core.db import SessionLocal
from app.models import Project
from app.reports import pdf as pdf_module
from app.reports.i18n import MarathiTexts, load_catalogue
from app.reports.pdf import build_pdf
from app.reports.plan_render import render_report_plan
from app.reports.report_data import build_report_data
from app.services.storage import get_storage

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
WHEN = datetime(2026, 10, 7, tzinfo=timezone.utc)


@pytest.fixture
def demo(client, auth):
    r = client.post("/projects/demo", headers=auth)
    db = SessionLocal()
    project = db.get(Project, r.json()["id"])
    yield db, project
    db.close()


def _data(db, project, **kw):
    return build_report_data(db, project.analyses[-1], project, generated_at=WHEN, **kw)


def _pdf(db, project, data, language):
    image = get_storage().get(project.floor_plans[-1].preview_key)
    plan = render_report_plan(image, data)
    thumbs = {r["id"]: render_report_plan(image, data, highlight=r["id"], max_side=500) for r in data["rooms"]}
    return build_pdf(data, plan, thumbs, language=language)


def test_default_language_is_english_and_unchanged(demo):
    db, project = demo
    default, en = _data(db, project), _data(db, project, language="en")
    assert default == en
    assert en["report_title"] == "Vastu Evaluation Report" and en["generated_on"] == "07 October 2026"


def test_marathi_keeps_every_number_and_decision(demo):
    db, project = demo
    en, mr = _data(db, project, language="en"), _data(db, project, language="mr")
    assert (mr["overall_score"], mr["score_tone"], mr["counts"]) == (en["overall_score"], en["score_tone"], en["counts"])
    assert [(c["key"], c["score"], c["earned"], c["possible"], c["weight"]) for c in mr["categories"]] == \
           [(c["key"], c["score"], c["earned"], c["possible"], c["weight"]) for c in en["categories"]]
    # same rooms, same attention-first order, same results, zones, directions and scores
    pick = ("id", "number", "room_type", "zone", "direction", "zone_share", "score", "status", "tone", "rule_code")
    assert [{k: r[k] for k in pick} for r in mr["rooms"]] == [{k: r[k] for k in pick} for r in en["rooms"]]
    # same remedies, priorities, phases and structural flags
    pick = ("code", "zone", "priority", "kind", "phase", "approved", "needs_professional", "severity", "bucket")
    assert [{k: r[k] for k in pick} for r in mr["remedies"]] == [{k: r[k] for k in pick} for r in en["remedies"]]
    assert {k: len(v) for k, v in mr["findings"].items()} == {k: len(v) for k, v in en["findings"].items()}
    assert mr["geometry"]["north_angle"] == en["geometry"]["north_angle"]


def test_marathi_dynamic_content_is_translated(demo):
    db, project = demo
    mr = _data(db, project, language="mr")
    assert mr["report_title"] == "वास्तु मूल्यांकन अहवाल" and mr["generated_on"] == "07 ऑक्टोबर 2026"
    texts = (mr["executive_summary"] + mr["final_summary"]["next_steps"] + mr["final_summary"]["priorities"]
             + [f["text"] for g in mr["findings"].values() for f in g]
             + [f["explanation"] for g in mr["findings"].values() for f in g if f["explanation"]]
             + [x for r in mr["remedies"] for x in (r["problem"], r["why"], r["action"], r["structural_note"]) if x]
             + [s for room in mr["rooms"] for s in room["introduction"]]
             + [c["text"] for room in mr["rooms"] for c in room["considerations"]])
    untranslated = [t for t in texts if not DEVANAGARI.search(t)]
    assert not untranslated, untranslated
    rooms = {r["room_type"]: r for r in mr["rooms"]}
    assert rooms["kitchen"]["label"] == "स्वयंपाकघर" and rooms["kitchen"]["result"] == "अत्यंत शुभ"
    assert rooms["bedroom"]["label"] == "शयनकक्ष 2"  # number kept
    assert next(r for r in mr["rooms"] if r["label"] == "स्नानगृह")["zone_name"] == "मध्य (ब्रह्मस्थान)"
    # numbers inside translated findings are the stored values (e.g. "100%" of Bath in the centre)
    assert any("100%" in f["text"] and "ब्रह्मस्थान" in f["text"] for f in mr["findings"]["major"])


def test_catalogue_covers_every_seeded_rule_and_remedy():
    import json
    from pathlib import Path

    seed = Path(__file__).parents[1] / "app" / "seed" / "data"
    cat = load_catalogue("mr")
    assert {r["code"] for r in json.loads((seed / "rules.json").read_text())["rules"]} <= set(cat["rules"])
    assert {r["code"] for r in json.loads((seed / "remedies.json").read_text())["remedies"]} <= set(cat["remedies"])
    for r in cat["rules"].values():  # Marathi templates only use values the rule engine provides
        assert set(re.findall(r"\{(\w+)\}", r["finding_template"])) <= {"room", "zone", "zone_name", "share",
                                                                         "coverage", "count"}


def test_marathi_text_helpers():
    t = MarathiTexts()
    # values substituted into the English sentence are recovered and re-used
    f = {"status": "issue", "rule_code": "ne_zone_cut", "subject_label": "North-East zone", "zone": "NE",
         "finding": "The North-East corner is cut: only 42% of the zone is inside the plan."}
    assert "42%" in t.finding_text(f, "The North-East corner is cut: only {coverage} of the zone is inside the plan.")
    # engine-built "not evaluated" sentence
    f = {"status": "not_evaluated", "rule_code": None, "subject_label": "Lounge 3", "room_type": "other", "zone": "N",
         "finding": "Lounge 3 (Other) has no placement rule in this rule set; not scored."}
    assert t.finding_text(f, None) == "Lounge 3 (इतर) साठी या नियम-संचात स्थान-नियम नाही; गुण दिलेले नाहीत."
    # a rule added later without a Marathi entry keeps its English text instead of failing
    f = {"status": "issue", "rule_code": "custom_rule", "subject_label": "Gym", "zone": "N", "finding": "Gym is odd."}
    assert t.finding_text(f, "{room} is odd.") == "Gym is odd." and "rule:custom_rule" in t.missing
    assert t.label("Master Bedroom") == "मुख्य शयनकक्ष" and t.label("Pooja-2") == "देवघर-2"
    assert t.label("Grandma's Den") == "Grandma's Den"  # custom names stay as typed
    assert t.ui("summary_lead", score=70, rule_set="x", pos=1, warn=1, maj=0, rooms=3).count("इशारा") == 1


def test_marathi_pdf_embeds_a_devanagari_font(demo):
    db, project = demo
    data = _data(db, project, language="mr")
    pdf = _pdf(db, project, data, "mr")
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) >= 10
    embedded = {}
    for page in reader.pages:
        for ref in page["/Resources"].get("/Font", {}).values():
            font = ref.get_object()
            if font["/Subtype"] == "/TrueType":
                embedded[font["/BaseFont"]] = "/FontFile2" in font["/FontDescriptor"].get_object()
    names = " ".join(embedded)
    assert "NotoSansDevanagari-Regular" in names and "NotoSansDevanagari-Bold" in names
    assert all(embedded.values())  # fonts travel with the PDF
    assert DEVANAGARI.search("".join(p.extract_text() for p in reader.pages))


def test_api_language_parameter_and_filenames(client, auth):
    p = client.post("/projects/demo", headers=auth).json()
    en = client.post(f"/projects/{p['id']}/report", headers=auth)  # no body: original behaviour
    mr = client.post(f"/projects/{p['id']}/report", headers=auth, json={"language": "mr"})
    assert en.status_code == mr.status_code == 202
    en, mr = (client.get(f"/reports/{r.json()['id']}", headers=auth).json() for r in (en, mr))
    assert (en["language"], en["status"]) == ("en", "ready") and (mr["language"], mr["status"]) == ("mr", "ready")
    assert "-en.pdf" in en["download_url"] and "-mr.pdf" in mr["download_url"]
    body = client.get(mr["download_url"].replace("http://localhost:8000", ""))
    assert body.status_code == 200 and body.content.startswith(b"%PDF")
    assert 'filename="vastu-report-' in body.headers["content-disposition"]
    listed = client.get(f"/projects/{p['id']}/reports", headers=auth).json()
    assert {r["language"] for r in listed} == {"en", "mr"}
    bad = client.post(f"/projects/{p['id']}/report", headers=auth, json={"language": "fr"})
    assert bad.status_code == 422


def test_marathi_failure_is_reported_not_replaced_with_english(client, auth, monkeypatch):
    p = client.post("/projects/demo", headers=auth).json()
    original = pdf_module.build_pdf

    def broken(report, plan_png, thumbs, language="en"):
        if language == "mr":
            raise RuntimeError("font missing")
        return original(report, plan_png, thumbs, language=language)

    monkeypatch.setattr("app.reports.service.build_pdf", broken)
    mr = client.post(f"/projects/{p['id']}/report", headers=auth, json={"language": "mr"}).json()
    mr = client.get(f"/reports/{mr['id']}", headers=auth).json()
    assert mr["status"] == "failed" and mr["download_url"] is None
    assert "Marathi" in mr["error"]
    en = client.post(f"/projects/{p['id']}/report", headers=auth, json={"language": "en"}).json()
    assert client.get(f"/reports/{en['id']}", headers=auth).json()["status"] == "ready"  # English unaffected
