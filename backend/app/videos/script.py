"""Video script: turns the report model (and the personal action plan) into scenes.

Every sentence is assembled from the stored analysis and catalogue text that the PDF already uses,
so the video never says anything the report doesn't. Each scene has narration (spoken), a title and
a few short on-screen points, plus which visual to show (title card, plan, score, a room, lists)."""
import re
from dataclasses import dataclass, field

MAX_ROOMS = 12


@dataclass
class Scene:
    kind: str  # title | method | score | drags | rooms | room | beyond | remedies | fit | stage | family | trust | close
    title: str
    narration: str
    points: list[dict] = field(default_factory=list)  # {"text", "tone"}
    data: dict = field(default_factory=dict)


L = {
    "en": {
        "intro_t": "Your Vastu report, explained",
        "intro": "Namaste. This is the video guide to the Vastu evaluation of {name}. In the next few minutes we "
                 "will go through your score, the rooms that need care, and a clear plan of what to do. Everything "
                 "you hear is also written in your PDF report.",
        "method_t": "How your plan was read",
        "method": "First, how it was done. Every room on your plan was confirmed by a person before analysis, and "
                  "true North was set at {north}. The plan was then divided into nine zones: the eight directions "
                  "and the centre, the Brahmasthan. Each room is judged by the zone it mostly sits in.",
        "method_p": ["Rooms confirmed by a person", "North: {north}", "9 zones: 8 directions + Brahmasthan",
                     "Rule set: {rule_set}"],
        "score_t": "Your overall score",
        "score": "Your overall Vastu score is {score} out of 100. In this report that reads as: {band}. {strong}"
                 "{weak}Altogether we found {p} positive {p_s}, {w} {w_s} that {w_v} attention, and {m} major {m_s}.",
        "strong": "Your strongest areas are {items}. ", "weak": "The area that needs the most attention is {items}. ",
        "no_score": "This plan could not be scored under the current rule set, so let's go straight to the rooms.",
        "drags_t": "What moves your score",
        "drags": "So what holds the score back? The single biggest factor is {subject}: {text} If this were resolved, "
                 "the score would rise by about {gain} points. {more}Keep in mind that everyday remedies ease an "
                 "issue but don't move a room, so they don't change the score. Only a change in placement does.",
        "drags_more": "Next comes {subject}, worth about {gain} points. ",
        "pts": "+{gain} points",
        "rooms_t": "Your rooms at a glance",
        "rooms": "Now your rooms. The plan has {n} {n_s}: {good} {good_v} well placed, {attn} {attn_v} attention, "
                 "and {bad} {bad_v} unfavourable. Let's start with the ones that need care. The numbers match your PDF.",
        "good_t": "Rooms that are well placed",
        "good": "These rooms are well placed under the rule set: {items}. Nothing needs to change in them. {unscored}",
        "good_item": "{label} in the {zone}",
        "unscored": "No rule covers {items}, so {pron} not scored.",
        "room_t": "Room {n}: {label}",
        "room_do": "What you can do: {text}",
        "room_p": ["Zone: {zone}", "Result: {result}"],
        "rooms_more": "The remaining {n} rooms are covered in your PDF report.",
        "beyond_t": "Beyond the rooms",
        "beyond": "Beyond individual rooms, the report also checks the entrance, the zones and the windows. {items}",
        "remedies_t": "Your remedies, step by step",
        "remedies": "Here is how the remedies are arranged in time. {phases}Any structural change should only be "
                    "planned with a qualified Vastu practitioner and a structural engineer.",
        "phase": "{label}: {items}. ",
        "fit_t": "What fits your situation",
        "fit": "You told us about your situation: {situation} {summary} {items}",
        "fit_item": "For {subject}, the suggested step is the {option}: {action}",
        "stage_t": "At your construction stage",
        "stage": "You are at the {stage} stage. {desc} {act}{check}",
        "stage_act": "Do these before they get expensive: {items}. ",
        "stage_none": "Nothing in this report gets more expensive at this stage. ",
        "stage_check": "Also, on site: {items}",
        "family_t": "Your family comes first",
        "family": "You also told us who lives here: {members}. With their needs in mind, start with {first}{rest}",
        "family_rest": ", then {items}.",
        "trust_t": "How reliable is this result?",
        "trust": "How much can you rely on this result? Confidence is {level}. {reasons}If anything looks wrong, "
                 "correct the plan in the app and run the analysis again; your report and this video will update.",
        "trust_none": "Nothing lowers confidence in this result. ",
        "trust_more": "In the app, you can also set your budget, construction stage and family needs; the next version "
                      "of this video will then include a personal action plan. ",
        "close_t": "Your next steps",
        "close": "To finish, your next steps. {steps}Thank you for watching. Vastu is traditional guidance, not "
                 "structural, legal or financial advice; before any structural change, consult a qualified "
                 "practitioner and a structural engineer.",
        "and": " and ", "sep": ", ",
    },
    "mr": {
        "intro_t": "आपला वास्तु अहवाल, सोप्या भाषेत",
        "intro": "नमस्कार. {name} च्या वास्तु मूल्यांकनाचा हा व्हिडिओ मार्गदर्शक आहे. पुढील काही मिनिटांत आपण "
                 "आपले गुण, काळजी घ्यावी अशा खोल्या आणि पुढे काय करायचे याची स्पष्ट योजना पाहू. येथे ऐकलेली प्रत्येक "
                 "गोष्ट आपल्या PDF अहवालातही लिहिलेली आहे.",
        "method_t": "आपला आराखडा कसा वाचला गेला",
        "method": "प्रथम, विश्लेषण कसे केले ते पाहू. विश्लेषणापूर्वी आराखड्यातील प्रत्येक खोली व्यक्तीने तपासून "
                  "निश्चित केली, आणि खरी उत्तर दिशा {north} अशी ठरवली. त्यानंतर आराखडा नऊ क्षेत्रांमध्ये विभागला: आठ "
                  "दिशा आणि मध्यभाग, म्हणजे ब्रह्मस्थान. प्रत्येक खोली ज्या क्षेत्रात मुख्यतः आहे, त्यानुसार तपासली जाते.",
        "method_p": ["प्रत्येक खोली व्यक्तीने तपासलेली", "उत्तर दिशा: {north}", "9 क्षेत्रे: 8 दिशा + ब्रह्मस्थान",
                     "नियम-संच: {rule_set}"],
        "score_t": "आपले एकूण गुण",
        "score": "आपले एकूण वास्तु गुण 100 पैकी {score} आहेत. या अहवालानुसार याचा अर्थ: {band}. {strong}{weak}"
                 "एकूण {p} चांगल्या बाबी, लक्ष देण्यासारख्या {w} बाबी आणि {m} मोठ्या समस्या आढळल्या.",
        "strong": "{items} या श्रेणींमध्ये आपले घर सर्वाधिक सक्षम आहे. ",
        "weak": "{items} या श्रेणीकडे सर्वाधिक लक्ष देणे आवश्यक आहे. ",
        "no_score": "सध्याच्या नियम-संचानुसार या आराखड्याला गुण देता आले नाहीत, म्हणून आपण थेट खोल्यांकडे वळू.",
        "drags_t": "आपल्या गुणांवर कशाचा परिणाम होतो",
        "drags": "मग गुण कमी का आहेत? सर्वात मोठे कारण म्हणजे {subject}: {text} ही समस्या सुटल्यास गुण साधारण "
                 "{gain} ने वाढतील. {more}लक्षात ठेवा, दैनंदिन उपायांनी समस्या कमी होते, पण खोलीची जागा बदलत नाही, "
                 "त्यामुळे गुण बदलत नाहीत. फक्त जागेतील बदलानेच गुण बदलतात.",
        "drags_more": "त्यानंतर {subject}, ज्याचे मूल्य साधारण {gain} गुण आहे. ",
        "pts": "+{gain} गुण",
        "rooms_t": "आपल्या खोल्या एका नजरेत",
        "rooms": "आता आपल्या खोल्या. आराखड्यातील एकूण खोल्या: {n}. योग्य ठिकाणी: {good}, लक्ष देणे आवश्यक: {attn}, "
                 "आणि प्रतिकूल: {bad}. काळजी घ्यावी अशा खोल्यांपासून सुरुवात करू. क्रमांक PDF अहवालाप्रमाणेच आहेत.",
        "good_t": "योग्य ठिकाणी असलेल्या खोल्या",
        "good": "नियम-संचानुसार या खोल्या योग्य ठिकाणी आहेत: {items}. त्यांच्यात काहीही बदल करण्याची गरज नाही. {unscored}",
        "good_item": "{label} {zone} क्षेत्रात",
        "unscored": "{items} साठी कोणताही नियम लागू होत नाही, त्यामुळे त्यांना गुण दिलेले नाहीत.",
        "room_t": "खोली {n}: {label}",
        "room_do": "आपण हे करू शकता: {text}",
        "room_p": ["क्षेत्र: {zone}", "निष्कर्ष: {result}"],
        "rooms_more": "उर्वरित {n} खोल्यांची माहिती आपल्या PDF अहवालात आहे.",
        "beyond_t": "खोल्यांपलीकडे",
        "beyond": "खोल्यांव्यतिरिक्त अहवालात प्रवेशद्वार, क्षेत्रे आणि खिडक्या यांचीही तपासणी केली आहे. {items}",
        "remedies_t": "आपले उपाय, टप्प्याटप्प्याने",
        "remedies": "उपाय वेळेनुसार असे मांडले आहेत. {phases}कोणताही संरचनात्मक बदल फक्त पात्र वास्तुतज्ज्ञ आणि "
                    "स्ट्रक्चरल इंजिनिअर यांच्या सल्ल्यानेच करावा.",
        "phase": "{label}: {items}. ",
        "fit_t": "आपल्या परिस्थितीला काय जमेल",
        "fit": "आपण आपली परिस्थिती सांगितली आहे: {situation} {summary} {items}",
        "fit_item": "{subject} साठी सुचवलेले पाऊल म्हणजे {option}: {action}",
        "stage_t": "आपल्या बांधकामाच्या टप्प्यानुसार",
        "stage": "आपले घर {stage} या टप्प्यावर आहे. {desc} {act}{check}",
        "stage_act": "खर्च वाढण्यापूर्वी हे करा: {items}. ",
        "stage_none": "या टप्प्यावर या अहवालातील कोणतीही बाब महाग होणार नाही. ",
        "stage_check": "तसेच जागेवर: {items}",
        "family_t": "आपल्या कुटुंबाला प्राधान्य",
        "family": "घरात कोण राहते हेही आपण सांगितले आहे: {members}. त्यांच्या गरजा लक्षात घेऊन सुरुवात करा: {first}{rest}",
        "family_rest": "; त्यानंतर {items}.",
        "trust_t": "हा निष्कर्ष किती विश्वासार्ह आहे?",
        "trust": "या निष्कर्षावर किती विश्वास ठेवता येईल? विश्वासार्हता: {level}. {reasons}काही चुकीचे वाटल्यास, ॲपमध्ये "
                 "आराखडा दुरुस्त करा आणि विश्लेषण पुन्हा चालवा; आपला अहवाल आणि हा व्हिडिओ अद्ययावत होईल.",
        "trust_none": "या निष्कर्षाची विश्वासार्हता कमी करणारी कोणतीही बाब नाही. ",
        "trust_more": "ॲपमध्ये आपण आपले बजेट, बांधकामाचा टप्पा आणि कुटुंबाच्या गरजाही नोंदवू शकता; त्यानंतर या "
                      "व्हिडिओच्या पुढील आवृत्तीत आपली वैयक्तिक कृती योजना असेल. ",
        "close_t": "आपली पुढील पावले",
        "close": "शेवटी, आपली पुढील पावले. {steps}व्हिडिओ पाहिल्याबद्दल धन्यवाद. वास्तुशास्त्र हे पारंपरिक मार्गदर्शन "
                 "आहे, संरचनात्मक, कायदेशीर किंवा आर्थिक सल्ला नाही; कोणताही संरचनात्मक बदल करण्यापूर्वी पात्र "
                 "वास्तुतज्ज्ञ आणि स्ट्रक्चरल इंजिनिअर यांचा सल्ला घ्या.",
        "and": " आणि ", "sep": ", ",
    },
}


def _join(items: list[str], lang: str) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return L[lang]["sep"].join(items[:-1]) + L[lang]["and"] + items[-1]


def first_sentence(text: str, limit: int = 220) -> str:
    text = (text or "").strip()
    m = re.match(r"(.+?[.।!?])(\s|$)", text)
    s = m.group(1) if m else text
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + "…"
    return s


def _end(text: str) -> str:
    text = (text or "").strip()
    return text if not text or text[-1] in ".।!?…" else text + "."


def _en_plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _unique(items: list[dict], key: str = "subject") -> list[dict]:
    seen, out = set(), []
    for i in items:
        if i[key] not in seen:
            seen.add(i[key])
            out.append(i)
    return out


def build_scenes(r: dict, ap: dict | None, language: str) -> list[Scene]:
    T = L[language]
    name = r["property"]["name"]
    a = r["assessment"]
    scenes = [Scene("title", T["intro_t"], T["intro"].format(name=name),
                    data={"name": name, "client": r["property"]["client_name"], "date": a["date"],
                          "score": r["overall_score"], "band": r["score_band"], "tone": r["score_tone"]})]

    rs_name = a["rule_set"]["name"]
    scenes.append(Scene("method", T["method_t"], T["method"].format(north=a["north_text"], rule_set=rs_name),
                        points=[{"text": p.format(north=a["north_text"], rule_set=rs_name), "tone": "neutral"}
                                for p in T["method_p"]], data={"image": "plan"}))

    c = r["counts"]
    cats = [x for x in r["categories"] if x["score"] is not None]
    if r["overall_score"] is None:
        scenes.append(Scene("score", T["score_t"], T["no_score"]))
    else:
        strong = [x["label"] for x in cats if x["score"] >= 75]
        weak = [x["label"] for x in sorted(cats, key=lambda x: x["score"]) if x["score"] < 50][:1]
        words = {"p_s": _en_plural(c["positive"], "point", "points"),
                 "w_s": _en_plural(c["warning"], "thing", "things"), "w_v": _en_plural(c["warning"], "needs", "need"),
                 "m_s": _en_plural(c["major"], "issue", "issues")}
        scenes.append(Scene("score", T["score_t"], T["score"].format(
            score=r["overall_score"], band=r["score_band"],
            strong=T["strong"].format(items=_join(strong, language)) if strong else "",
            weak=T["weak"].format(items=_join(weak, language)) if weak else "",
            p=c["positive"], w=c["warning"], m=c["major"], **words),
            data={"score": r["overall_score"], "band": r["score_band"], "tone": r["score_tone"], "categories": cats,
                  "counts": c}))

    if ap and ap["score"]["items"]:
        items = ap["score"]["items"]
        gain = lambda i: i["gain"].split()[0].lstrip("+")  # noqa: E731
        more = "".join(T["drags_more"].format(subject=i["subject"], gain=gain(i)) for i in items[1:3])
        scenes.append(Scene("drags", T["drags_t"], T["drags"].format(subject=items[0]["subject"],
                                                                      text=_end(items[0]["text"]), gain=gain(items[0]),
                                                                      more=more),
                            points=[{"text": f"{i['subject']}: {i['text']}", "tone": i.get("bucket") or "warning",
                                     "badge": i["gain"]} for i in items[:4]]))

    rooms = r["rooms"]
    if rooms:
        good = sum(1 for x in rooms if x["tone"] == "positive")
        attn = sum(1 for x in rooms if x["tone"] == "warning")
        bad = sum(1 for x in rooms if x["tone"] == "major")
        n = len(rooms)
        verbs = {"n_s": _en_plural(n, "room", "rooms"), "good_v": _en_plural(good, "is", "are"),
                 "attn_v": _en_plural(attn, "needs", "need"), "bad_v": _en_plural(bad, "is", "are")}
        scenes.append(Scene("rooms", T["rooms_t"], T["rooms"].format(n=n, good=good, attn=attn, bad=bad, **verbs),
                            points=[{"text": f"{x['number']}. {x['label']} · {x['zone_name'] or '-'}", "tone": x["tone"]}
                                    for x in rooms], data={"image": "plan"}))
        care = [x for x in rooms if x["tone"] in ("major", "warning")]
        for room in care[:MAX_ROOMS]:
            say = " ".join(_end(x) for x in room["introduction"][:3])
            rec = room["recommendations"][0] if room["recommendations"] else None
            if rec:
                say += " " + T["room_do"].format(text=_end(first_sentence(rec["action"])))
            pts = [{"text": p.format(zone=room["zone_name"] or "-", result=room["result"]), "tone": room["tone"] if i else "neutral"}
                   for i, p in enumerate(T["room_p"])]
            if rec:
                pts.append({"text": first_sentence(rec["action"], 160), "tone": "action"})
            scenes.append(Scene("room", T["room_t"].format(n=room["number"], label=room["label"]), say, points=pts,
                                data={"room_id": room["id"], "tone": room["tone"], "score": room["score"],
                                      "number": room["number"], "type": room["room_type_label"]}))
        if len(care) > MAX_ROOMS:
            scenes[-1].narration += " " + T["rooms_more"].format(n=len(care) - MAX_ROOMS)
        good_rooms = [x for x in rooms if x["tone"] == "positive"]
        unscored = [x["label"] for x in rooms if x["tone"] == "neutral"]
        if good_rooms or unscored:
            items = _join([T["good_item"].format(label=x["label"], zone=x["zone_name"]) for x in good_rooms], language)
            uns = T["unscored"].format(items=_join(unscored, language), pron="it is" if len(unscored) == 1 else "they are") \
                if unscored else ""
            say = T["good"].format(items=items, unscored=uns) if good_rooms else uns
            scenes.append(Scene("rooms", T["good_t"], say.strip(), data={"image": "plan"},
                                points=[{"text": f"{x['number']}. {x['label']} · {x['zone_name']}", "tone": "positive"}
                                        for x in good_rooms] + [{"text": u, "tone": "neutral"} for u in unscored]))

    room_labels = {x["label"] for x in rooms}
    beyond = [f for b in ("major", "warning", "positive") for f in r["findings"][b] if f["subject"] not in room_labels]
    if beyond:
        beyond = beyond[:4]
        scenes.append(Scene("beyond", T["beyond_t"], T["beyond"].format(items=" ".join(_end(f["text"]) for f in beyond)),
                            points=[{"text": f["text"], "tone": {"positive": "positive", "high": "major"}.get(
                                f["severity"], "warning")} for f in beyond]))

    phases = [p for p in r["remedy_plan"] if p["items"]]
    if phases:
        said = ""
        for p in phases:
            subjects = list(dict.fromkeys(i["subject"] for i in p["items"]))
            said += T["phase"].format(label=p["label"], items=_join(
                [f"{s}, {first_sentence(next(i['text'] for i in p['items'] if i['subject'] == s), 120).rstrip('.')}"
                 for s in subjects[:2]], language))
        scenes.append(Scene("remedies", T["remedies_t"], T["remedies"].format(phases=said),
                            data={"phases": [{"label": p["label"], "items": [
                                {"text": f"{i['subject']}: {first_sentence(i['text'], 110)}", "structural": i["structural"]}
                                for i in p["items"][:3]]} for p in phases]}))

    if ap and ap.get("fit"):
        fit = ap["fit"]
        items = [T["fit_item"].format(subject=i["subject"], option=i["option"].lower() if language == "en" else i["option"],
                                      action=_end(first_sentence(i["action"])))
                 for i in fit["items"] if i["action"]][:3]
        scenes.append(Scene("fit", T["fit_t"], T["fit"].format(situation=_end(fit["situation"].split(": ", 1)[-1]),
                                                                summary=fit["summary"], items=" ".join(items)),
                            points=[{"text": f"{i['subject']}: {first_sentence(i['action'] or i['problem'], 150)}",
                                     "tone": i["tone"], "badge": i["verdict_label"], "badge_tone": i["tone"]}
                                    for i in _unique(fit["items"])[:5]]))
    if ap and ap.get("stage"):
        st = ap["stage"]
        stage_label = st["heading"].split(": ", 1)[-1]
        act = (T["stage_act"].format(items=_join([f"{i['subject']}, {i['deadline']}" for i in st["act_now"][:3]], language))
               if st["act_now"] else T["stage_none"])
        check = T["stage_check"].format(items=" ".join(_end(x) for x in st["checklist"][:2])) if st["checklist"] else ""
        scenes.append(Scene("stage", T["stage_t"], T["stage"].format(stage=stage_label, desc=_end(st["description"]),
                                                                      act=act, check=check),
                            points=[{"text": f"{i['subject']}: {first_sentence(i['text'], 130)}", "tone": "action",
                                     "badge": i["deadline"], "badge_tone": "warning"} for i in _unique(st["act_now"])[:2]]
                            + [{"text": x, "tone": "neutral"} for x in st["checklist"][:3]],
                            data={"stage": stage_label}))
    if ap and ap.get("family"):
        fam = ap["family"]
        members = fam["intro"].split(": ", 1)[-1].split(".")[0]
        order = fam["order"]
        if order:
            first = f"{order[0]['subject']}: {_end(first_sentence(order[0]['text']))}"
            rest = T["family_rest"].format(items=_join([o["subject"] for o in order[1:4]], language)) if len(order) > 1 else ""
            scenes.append(Scene("family", T["family_t"], T["family"].format(members=members, first=first, rest=rest),
                                points=[{"text": f"{k}. {o['subject']}: {first_sentence(o['text'], 140)}", "tone": "action"}
                                        for k, o in enumerate(order[:4], 1)]))

    if ap:
        tr = ap["trust"]
        reasons = "".join(_end(x["text"]) + " " for x in tr["reasons"][:2]) if tr["reasons"] else T["trust_none"]
        if not ap.get("personalised"):
            reasons += T["trust_more"]
        scenes.append(Scene("trust", T["trust_t"], T["trust"].format(level=tr["label"], reasons=reasons),
                            points=[{"text": x["text"], "tone": x["tone"]} for x in tr["reasons"][:4]],
                            data={"level": tr["label"], "tone": tr["tone"]}))

    steps = r["final_summary"]["next_steps"][:2]
    scenes.append(Scene("close", T["close_t"], T["close"].format(steps="".join(_end(s) + " " for s in steps)),
                        points=[{"text": s, "tone": "action"} for s in steps]))
    return scenes
