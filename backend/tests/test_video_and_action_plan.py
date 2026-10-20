"""Personal action plan in the PDF, and the narrated video report."""
import io
import wave

import pypdfium2 as pdfium
import pytest

from tests.test_insights import demo, get


def _pdf_text(client, auth, pid, **body):
    r = client.post(f"/projects/{pid}/report", json=body, headers=auth)
    assert r.status_code == 202, r.text
    rep = get(client, auth, f"/reports/{r.json()['id']}")
    assert rep["status"] == "ready", rep
    data = client.get(rep["download_url"].replace("http://localhost:8000", "")).content
    doc = pdfium.PdfDocument(data)
    try:
        return rep, "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc))), len(doc)
    finally:
        doc.close()


def test_action_plan_in_pdf(client, auth):
    p = demo(client, auth)
    rep, text, pages_without = _pdf_text(client, auth, p["id"], language="en", include_action_plan=False)
    assert not rep["action_plan"] and "Your personal action plan" not in text
    # Without customer settings: score drivers + reliability, plus a hint to personalise.
    rep, text, _ = _pdf_text(client, auth, p["id"], language="en")
    assert rep["action_plan"] and "Your personal action plan" in text
    assert "What moves your score most" in text and "How reliable this result is" in text
    assert "Remedies that fit your situation" not in text and "Insights" in text
    client.put(f"/projects/{p['id']}/insights/context", headers=auth, json={
        "fit_constraints": {"ownership": "tenant", "budget": "medium", "allow_services": True},
        "construction_stage": "planning", "family_profile": {"members": ["elderly"]}})
    _, text, pages_with = _pdf_text(client, auth, p["id"], language="en")
    for heading in ("Remedies that fit your situation", "At your construction stage", "Your family's priorities"):
        assert heading in text
    assert pages_with > pages_without
    # Marathi glyphs are shaped (not extractable as plain text); check the section is laid out.
    rep_mr, _, pages_mr = _pdf_text(client, auth, p["id"], language="mr")
    assert rep_mr["action_plan"] and pages_mr >= pages_with


def test_video_script_scenes():
    from app.videos.script import first_sentence

    assert first_sentence("One. Two.") == "One."
    assert first_sentence("एक वाक्य. दुसरे.") == "एक वाक्य."


@pytest.fixture
def fast_voice(monkeypatch):
    """One second of silence per scene keeps the test quick."""
    from app.videos import tts

    def synth(self, text, language, out):
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(b"\x00\x00" * 24000)
        return 1.0
    monkeypatch.setattr(tts.SilentNarrator, "synth", synth)


@pytest.mark.parametrize("language", ["en", "mr"])
def test_video_report(client, auth, other_auth, fast_voice, language):
    p = demo(client, auth)
    client.put(f"/projects/{p['id']}/insights/context", headers=auth,
               json={"fit_constraints": {"budget": "low"}, "construction_stage": "occupied"})
    r = client.post(f"/projects/{p['id']}/video", json={"language": language}, headers=auth)
    assert r.status_code == 202, r.text
    v = get(client, auth, f"/videos/{r.json()['id']}")
    assert v["status"] == "ready", v
    assert v["narration"] == "silent" and v["scenes"] >= 10 and v["is_current"]
    kinds = [t["title"] for t in v["transcript"]]
    assert len(kinds) == v["scenes"]
    mp4 = client.get(v["video_url"].replace("http://localhost:8000", ""))
    assert mp4.status_code == 200 and mp4.content[4:8] == b"ftyp"
    part = client.get(v["video_url"].replace("http://localhost:8000", ""), headers={"Range": "bytes=0-1023"})
    assert part.status_code == 206 and len(part.content) == 1024
    srt = client.get(v["subtitles_url"].replace("http://localhost:8000", "")).content.decode()
    assert "-->" in srt and ("100 पैकी" in srt if language == "mr" else "out of 100" in srt)
    vtt = client.get(v["captions_url"].replace("http://localhost:8000", ""))
    assert vtt.text.startswith("WEBVTT") and vtt.headers["content-type"].startswith("text/vtt")
    assert get(client, auth, f"/projects/{p['id']}/videos")[0]["id"] == v["id"]
    assert client.get(f"/videos/{v['id']}", headers=other_auth).status_code == 404


def test_video_needs_analysis(client, auth):
    from tests.test_api import create_project

    p = create_project(client, auth)
    r = client.post(f"/projects/{p['id']}/video", json={"language": "en"}, headers=auth)
    assert r.status_code == 409


def test_shaped_heading_helper():
    """Devanagari headings are drawn through Paragraph shaping (the canvas's own shaping misplaces ि)."""
    from reportlab.pdfgen import canvas

    from app.reports.pdf import _fonts, draw_text

    f = _fonts("mr")
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    w = draw_text(c, 10, 10, "आपली वैयक्तिक कृती योजना", f["bold"], 14, True)
    c.save()
    assert w > 50
    assert pdfium.PdfDocument(buf.getvalue())[0].get_width() > 0
