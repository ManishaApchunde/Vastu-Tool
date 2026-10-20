"""Voice Report Explainer: a short, plain-language spoken summary in English or Marathi.

The script is built from the stored analysis (in Marathi through the same catalogue translations
as the Marathi PDF), so the audio says exactly what the report says. Audio is produced by the
listener's browser (Web Speech API, en-IN / mr-IN voices), so nothing is sent to a third-party
speech service; the text is also returned for reading or downloading."""
import re

from app.reports.i18n import texts_for

LINES = {
    "en": {
        "intro": "Here is a simple summary of the Vastu report for {name}.",
        "score": "The overall Vastu score is {score} out of 100. That means: {band}.",
        "no_score": "This plan could not be scored under the current rule set.",
        "counts": "We found {p} good {p_s}, {w} {w_s} that {w_v} attention, and {m} major {m_s}.",
        "good": "What works well. {items}",
        "issue": "Point {n}. {finding}",
        "fix": "What you can do: {text}",
        "no_issues": "No warnings or major issues were found under this rule set.",
        "next": "Start with the high-priority steps, and talk to a Vastu practitioner before any structural change.",
        "close": "This summary follows the selected Vastu rule set. It is traditional guidance, not structural, "
                 "legal or financial advice.",
        "percent": " percent",
        "titles": {"intro": "Introduction", "score": "Score", "good": "What works well", "issues": "Main issues",
                   "next": "Next steps"},
    },
    "mr": {
        "intro": "{name} साठी वास्तु अहवालाचा हा सोपा सारांश आहे.",
        "score": "एकूण वास्तु गुण 100 पैकी {score} आहेत. याचा अर्थ: {band}.",
        "no_score": "सध्याच्या नियम-संचानुसार या आराखड्याला गुण देता आले नाहीत.",
        "counts": "{p} चांगल्या बाबी, लक्ष देण्यासारख्या {w} बाबी आणि {m} मोठ्या समस्या आढळल्या.",
        "good": "चांगल्या बाबी. {items}",
        "issue": "मुद्दा {n}. {finding}",
        "fix": "आपण हे करू शकता: {text}",
        "no_issues": "या नियम-संचानुसार कोणतेही इशारे किंवा मोठ्या समस्या आढळल्या नाहीत.",
        "next": "सर्वात आधी उच्च प्राधान्याचे उपाय करा, आणि कोणताही संरचनात्मक बदल करण्यापूर्वी वास्तुतज्ज्ञांचा "
                "सल्ला घ्या.",
        "close": "हा सारांश निवडलेल्या वास्तु नियम-संचावर आधारित आहे. हे पारंपरिक मार्गदर्शन आहे; संरचनात्मक, "
                 "कायदेशीर किंवा आर्थिक सल्ला नाही.",
        "percent": " टक्के",
        "titles": {"intro": "ओळख", "score": "गुण", "good": "चांगल्या बाबी", "issues": "मुख्य समस्या",
                   "next": "पुढील पावले"},
    },
}
VOICE_LANG = {"en": "en-IN", "mr": "mr-IN"}
MAX_ISSUES = 3


def speakable(text: str, lang: str) -> str:
    """Tidy text for speech: no brackets, symbols read as words."""
    text = re.sub(r"\s*\(([^)]*)\)", r", \1,", text or "")
    text = text.replace("%", LINES[lang]["percent"]).replace("×", " by ").replace("°", " degrees" if lang == "en" else " अंश")
    text = re.sub(r"\s*,\s*([,.])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _first_sentence(text: str, limit: int = 180) -> str:
    if len(text) <= limit:
        return text
    m = re.match(r"(.+?[.।])\s", text)
    return m.group(1) if m and len(m.group(1)) <= limit * 1.5 else text[:limit].rsplit(" ", 1)[0] + "…"


def _count_words(counts: dict) -> dict:
    p, w, m = counts.get("positive", 0), counts.get("warning", 0), counts.get("major", 0)
    return {"p": p, "w": w, "m": m, "p_s": "point" if p == 1 else "points", "w_s": "thing" if w == 1 else "things",
            "w_v": "needs" if w == 1 else "need", "m_s": "issue" if m == 1 else "issues"}


def voice_script(a: dict, project_name: str, language: str, rule_templates: dict[str, str]) -> dict:
    t = texts_for(language)
    a = t.localise_analysis(a, rule_templates)
    L = LINES[language]
    name = t.label(project_name) if hasattr(t, "label") else project_name
    counts = a.get("counts") or {}
    segs = [{"id": "intro", "title": L["titles"]["intro"], "text": L["intro"].format(name=name)}]
    if a["overall_score"] is None:
        segs.append({"id": "score", "title": L["titles"]["score"], "text": L["no_score"]})
    else:
        band, _ = t.score_band(a["overall_score"])
        segs.append({"id": "score", "title": L["titles"]["score"],
                     "text": L["score"].format(score=a["overall_score"], band=band) + " " + L["counts"].format(**_count_words(counts))})
    good = sorted((f for f in a["findings"] if f["bucket"] == "positive"), key=lambda f: -(f["weight"] or 0))[:2]
    if good:
        segs.append({"id": "good", "title": L["titles"]["good"],
                     "text": L["good"].format(items=" ".join(f["finding"] for f in good))})
    issues, seen = [], set()
    for f in sorted((f for f in a["findings"] if f["bucket"] in ("major", "warning")),
                    key=lambda f: (f["bucket"] != "major", -(f["weight"] or 0))):
        if f["subject_label"] in seen:  # one point per room keeps the audio short
            continue
        seen.add(f["subject_label"])
        issues.append(f)
    issues = issues[:MAX_ISSUES]
    if issues:
        parts = []
        for n, f in enumerate(issues, 1):
            parts.append(L["issue"].format(n=n, finding=f["finding"]))
            if f.get("remedy"):
                parts.append(L["fix"].format(text=_first_sentence(f["remedy"]["recommendation"])))
        segs.append({"id": "issues", "title": L["titles"]["issues"], "text": " ".join(parts)})
    else:
        segs.append({"id": "issues", "title": L["titles"]["issues"], "text": L["no_issues"]})
    segs.append({"id": "next", "title": L["titles"]["next"], "text": L["next"] + " " + L["close"]})
    for s in segs:
        s["speech"] = speakable(s["text"], language)
    return {"language": language, "voice_lang": VOICE_LANG[language], "segments": segs,
            "full_text": "\n\n".join(s["text"] for s in segs),
            "speech_text": " ".join(s["speech"] for s in segs),
            "analysis_id": a["id"]}
