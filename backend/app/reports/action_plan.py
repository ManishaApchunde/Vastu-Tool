"""Personal action plan: the insight tools turned into a report section, in English or Marathi.

Always included: what moves the score most, and how reliable the result is. Included only when the
customer has set them up in Insights: remedies that fit their situation (FitCheck), what to do at
their construction stage, and their family's priorities. Nothing here changes the analysis."""
from app.insights.common import load_data
from app.insights.context import Ctx
from app.insights.passport import LEVEL_LABELS, reason_text

TEXT = {
    "en": {
        "title": "Your personal action plan",
        "intro": "This section applies the findings in this report to your situation, as set up in the app. "
                 "The score, findings and remedies above are unchanged.",
        "drags_h": "What moves your score most",
        "drags_intro": "If the rule for each item below passed (for example after a relocation), the overall score "
                       "would rise by about the points shown. Everyday remedies ease an issue but do not move a room, "
                       "so they do not change the score.",
        "gain": "+{gain} points",
        "ceiling": "Highest score this plan can reach if every issue were resolved: {ceiling} / 100.",
        "trust_h": "How reliable this result is",
        "trust_none": "Nothing lowers confidence in this result.",
        "fit_h": "Remedies that fit your situation",
        "fit_intro": "Your situation: {situation}.",
        "fit_counts": "{fits} of {total} issues have a remedy that fits; {cond} need approval or a planned renovation; "
                      "{out} are outside your limits.",
        "do_this": "Suggested", "why_not": "Not possible now",
        "stage_h": "At your construction stage: {stage}",
        "act_now": "Do before it gets expensive", "before": "before '{stage}'",
        "act_none": "Nothing in this report is about to get more expensive at this stage.",
        "checklist": "Site checklist for this stage",
        "family_h": "Your family's priorities",
        "family_intro": "Living here: {members}. Family view score {family} (priority rooms counted double); "
                        "official score {official}.",
        "family_order": "Fix in this order",
        "not_set": "Set your budget and limits, construction stage and family priorities in the app's Insights "
                   "to add personalised advice here.",
        "option": {"everyday": "Everyday adjustment", "structural": "Structural change"},
        "verdict": {"fits": "Fits you", "conditional": "Needs approval", "out_of_scope": "Outside your limits"},
        "ownership": {"owner": "own home", "tenant": "rented home", "buying": "home being bought"},
        "budget": {"none": "no budget for changes", "low": "low budget", "medium": "moderate budget",
                   "high": "high budget"},
        "civil": {True: "civil work allowed", False: "no civil work"},
        "services": {True: "plumbing/electrical work allowed", False: "no plumbing/electrical work"},
        "codes": {
            "over_budget": "above your budget", "no_civil": "needs civil work, which you've ruled out",
            "no_services": "needs plumbing or electrical work, which you've ruled out",
            "too_disruptive": "more disruption than you accept", "society_rules": "society rules don't allow it",
            "civil_with_renovation": "only during your planned renovation",
            "services_with_renovation": "plan it with the renovation",
            "owner_permission": "needs the owner's written permission",
            "buying": "factor the cost into the purchase", "expert": "confirm on site with a practitioner",
        },
    },
    "mr": {
        "title": "आपली वैयक्तिक कृती योजना",
        "intro": "हा विभाग या अहवालातील निष्कर्ष ॲपमध्ये नोंदवलेल्या आपल्या परिस्थितीला लागू करतो. "
                 "वरील गुण, निष्कर्ष आणि उपाय यांत कोणताही बदल होत नाही.",
        "drags_h": "आपल्या गुणांवर सर्वाधिक परिणाम करणाऱ्या बाबी",
        "drags_intro": "खालील प्रत्येक बाबीचा नियम पूर्ण झाल्यास (उदा. खोलीचे स्थलांतर केल्यानंतर) एकूण गुण "
                       "साधारण दाखवलेल्या गुणांनी वाढतील. दैनंदिन उपायांनी समस्या कमी होते, पण खोलीची जागा बदलत "
                       "नाही, त्यामुळे गुण बदलत नाहीत.",
        "gain": "+{gain} गुण",
        "ceiling": "सर्व समस्या सुटल्यास हा आराखडा जास्तीत जास्त {ceiling} / 100 गुणांपर्यंत पोहोचू शकतो.",
        "trust_h": "हा निष्कर्ष किती विश्वासार्ह आहे",
        "trust_none": "या निष्कर्षाची विश्वासार्हता कमी करणारी कोणतीही बाब नाही.",
        "fit_h": "आपल्या परिस्थितीला जमणारे उपाय",
        "fit_intro": "आपली परिस्थिती: {situation}.",
        "fit_counts": "{total} पैकी {fits} समस्यांसाठी आपल्याला जमेल असा उपाय आहे; {cond} साठी परवानगी किंवा नियोजित "
                      "नूतनीकरण आवश्यक आहे; {out} आपल्या मर्यादेबाहेर आहेत.",
        "do_this": "सुचवलेला उपाय", "why_not": "सध्या शक्य नाही",
        "stage_h": "आपल्या बांधकामाच्या टप्प्यानुसार: {stage}",
        "act_now": "खर्च वाढण्यापूर्वी हे करा", "before": "'{stage}' टप्प्यापूर्वी",
        "act_none": "या टप्प्यावर या अहवालातील कोणतीही बाब महाग होणार नाही.",
        "checklist": "या टप्प्यासाठी जागेवरील तपासणी यादी",
        "family_h": "आपल्या कुटुंबाचे प्राधान्य",
        "family_intro": "घरात राहणारे: {members}. कुटुंब-केंद्रित गुण {family} (प्राधान्याच्या खोल्यांना दुप्पट "
                        "महत्त्व); अधिकृत गुण {official}.",
        "family_order": "या क्रमाने उपाय करा",
        "not_set": "येथे वैयक्तिक सल्ला मिळवण्यासाठी ॲपमधील 'इनसाइट्स' मध्ये आपले बजेट व मर्यादा, बांधकामाचा "
                   "टप्पा आणि कुटुंबाचे प्राधान्य नोंदवा.",
        "option": {"everyday": "दैनंदिन बदल", "structural": "संरचनात्मक बदल"},
        "verdict": {"fits": "आपल्याला जमेल", "conditional": "परवानगी आवश्यक", "out_of_scope": "आपल्या मर्यादेबाहेर"},
        "ownership": {"owner": "स्वतःचे घर", "tenant": "भाड्याचे घर", "buying": "खरेदी प्रक्रियेतील घर"},
        "budget": {"none": "बदलांसाठी बजेट नाही", "low": "कमी बजेट", "medium": "मध्यम बजेट", "high": "जास्त बजेट"},
        "civil": {True: "बांधकामात बदल चालतील", False: "बांधकामात बदल नाहीत"},
        "services": {True: "प्लंबिंग/वीज बदल चालतील", False: "प्लंबिंग/वीज बदल नाहीत"},
        "codes": {
            "over_budget": "आपल्या बजेटबाहेर", "no_civil": "बांधकामात बदल आवश्यक, जो आपल्याला नको आहे",
            "no_services": "प्लंबिंग किंवा वीज बदल आवश्यक, जो आपल्याला नको आहे",
            "too_disruptive": "आपल्याला चालेल त्यापेक्षा जास्त गैरसोय", "society_rules": "सोसायटीचे नियम परवानगी देत नाहीत",
            "civil_with_renovation": "फक्त नियोजित नूतनीकरणाच्या वेळी",
            "services_with_renovation": "नूतनीकरणासोबत नियोजन करा",
            "owner_permission": "घरमालकाची लेखी परवानगी आवश्यक",
            "buying": "हा खर्च खरेदी किमतीत विचारात घ्या", "expert": "वास्तुतज्ज्ञांकडून जागेवर खात्री करा",
        },
    },
}
LEVEL_TONE = {"high": "positive", "medium": "warning", "low": "major"}
VERDICT_TONE = {"fits": "positive", "conditional": "warning", "out_of_scope": "neutral"}


def _family_set(profile: dict | None) -> bool:
    return bool(profile and (profile.get("members") or profile.get("focus") or profile.get("room_priority")))


def build_action_plan(ctx: Ctx, language: str = "en") -> dict:
    T = TEXT[language]
    prop = ctx.prop
    explain = ctx.explain()
    gains = {d["finding_id"]: d["overall_gain"] for d in explain["drags"]}
    out: dict = {"title": T["title"], "intro": T["intro"], "language": language}

    out["score"] = {
        "heading": T["drags_h"], "intro": T["drags_intro"],
        "items": [{"subject": d["subject"], "text": d["finding"], "gain": T["gain"].format(gain=f"{d['overall_gain']:g}"),
                   "bucket": d["bucket"]} for d in explain["drags"][:4] if d["overall_gain"] >= 0.5],
        "ceiling": T["ceiling"].format(ceiling=explain["ceiling_if_all_issues_resolved"])
        if explain["ceiling_if_all_issues_resolved"] is not None else None,
    }

    pp = ctx.passport()
    out["trust"] = {"heading": T["trust_h"], "level": pp["level"], "label": LEVEL_LABELS[language][pp["level"]],
                    "tone": LEVEL_TONE[pp["level"]],
                    "reasons": [{"tone": "major" if r["severity"] == "critical" else "warning",
                                 "text": reason_text(r["code"], r["params"], language)} for r in pp["reasons"]],
                    "none": T["trust_none"]}

    out["fit"] = None
    if prop and prop.fit_constraints:
        fc = ctx.fit(gains)
        c = fc["constraints"]
        situation = ", ".join([T["ownership"][c["ownership"]], T["budget"][c["budget"]],
                               T["civil"][bool(c["allow_structural"])], T["services"][bool(c["allow_services"])]])
        items = []
        for it in fc["items"]:
            best = next((o for o in it["options"] if o["kind"] == it["recommended"]), None)
            other = [o for o in it["options"] if o is not best and o["verdict"] != "fits"]
            reasons = [T["codes"][code] for o in ([best] if best else []) for code in o["codes"]["conditions"]]
            blocked = [f"{T['option'][o['kind']]}: " + "; ".join(T["codes"][code] for code in o["codes"]["blocked"])
                       for o in other if o["codes"]["blocked"]]
            items.append({"subject": it["subject"], "problem": it["finding"], "bucket": it["bucket"],
                          "verdict": it["verdict"], "verdict_label": T["verdict"][it["verdict"]],
                          "tone": VERDICT_TONE[it["verdict"]],
                          "option": T["option"][best["kind"]] if best else None,
                          "action": best["text"] if best else None,
                          "conditions": reasons, "not_possible": blocked})
        out["fit"] = {"heading": T["fit_h"], "situation": T["fit_intro"].format(situation=situation),
                      "summary": T["fit_counts"].format(fits=fc["counts"]["fits"], total=len(fc["items"]),
                                                        cond=fc["counts"]["conditional"],
                                                        out=fc["counts"]["out_of_scope"]),
                      "items": items, "do_this": T["do_this"], "why_not": T["why_not"]}

    out["stage"] = None
    if prop and prop.construction_stage:
        st = ctx.stage(gains)
        cur = st["current"]
        label = cur["label_mr"] if language == "mr" else cur["label"]
        out["stage"] = {
            "heading": T["stage_h"].format(stage=label),
            "description": cur["description_mr"] if language == "mr" else cur["description"],
            "act_now_h": T["act_now"], "act_none": T["act_none"],
            "act_now": [{"subject": i["subject"], "text": i["text"], "bucket": i["bucket"], "tone": "action",
                         "deadline": T["before"].format(stage=i["deadline_label_mr"] if language == "mr"
                                                        else i["deadline_label"])} for i in st["act_now"]],
            "checklist_h": T["checklist"], "checklist": st["checklist"],
        }

    out["family"] = None
    if prop and _family_set(prop.family_profile):
        fam = ctx.family()
        roles = load_data("family")["roles"]
        key = "label_mr" if language == "mr" else "label"
        members = ", ".join(roles[m][key] for m in fam["profile"]["members"]) or "—"
        out["family"] = {
            "heading": T["family_h"],
            "intro": T["family_intro"].format(members=members, family=fam["family_score"],
                                              official=fam["official_score"]),
            "order_h": T["family_order"],
            "order": [{"subject": f["subject"], "text": f["recommendation"] or f["finding"], "bucket": f["bucket"],
                       "priority": f["priority"]} for f in fam["priority_actions"][:6]],
        }
    out["personalised"] = any(out[k] for k in ("fit", "stage", "family"))
    out["not_set"] = None if out["personalised"] else T["not_set"]
    return out
