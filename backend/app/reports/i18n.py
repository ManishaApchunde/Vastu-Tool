"""Report language support (English / Marathi).

Only the *presentation* language of the report changes. Analysis, scores, findings, severities and
remedy selection are read from the stored analysis and never recomputed here.

    report_data.build_report_data(language)  ──► texts_for(language)  ──► wording for the report model
    pdf.build_pdf(language)                  ──► texts_for(language).ui(...)  ──► PDF labels / headings

`EnglishTexts` reproduces the original English wording exactly, so the English PDF is unchanged.
`MarathiTexts` overrides it. Catalogue text (rule finding templates, rule explanations, remedies,
rule-set name/disclaimer) is translated from `locales/mr.json`, keyed by code; anything without a
Marathi entry (e.g. a rule a practitioner added later) falls back to the stored English text.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from app.geometry.zones import ZONE_NAMES
from app.vastu.room_types import ROOM_TYPES

log = logging.getLogger(__name__)

LANGUAGES = ("en", "mr")
LANGUAGE_NAMES = {"en": "English", "mr": "Marathi"}
LOCALES_DIR = Path(__file__).parent / "locales"


def _plural(n: int, suffix: str = "s") -> str:
    return "" if n == 1 else suffix


# ==================================================================================================
# English (original wording, unchanged)
# ==================================================================================================
# How a room type reads inside a sentence ("acceptable for a dining area"); defaults to the label.
ROOM_NOUNS = {"dining": "dining area", "toilet": "toilet or bathroom", "foyer": "foyer or passage",
              "utility": "utility area", "parking": "parking area", "store": "store room", "other": "room",
              "living": "living room", "pooja": "pooja room"}
KIND_LABELS = {"non_structural": "Non-structural", "structural": "Structural", "optional": "Optional"}
# Room result vocabulary (see report_data for how a result is chosen).
RESULT_LABELS = {"major": "Unfavourable", "warning": "Needs attention", "preferred": "Highly auspicious",
                 "acceptable": "Auspicious", "neutral": "Not evaluated"}
PHASE_LABELS = {"immediate": "Immediate", "short_term": "Short term", "medium_term": "Medium term",
                "long_term": "Long term"}

DISCLAIMER_POINTS = [
    "Vastu Shastra is a traditional system of architectural guidance. This report applies it as a methodology; "
    "it is not a scientific assessment.",
    "The findings depend entirely on the floor plan, room types, main entrance and North direction supplied and "
    "verified by the user. Errors in those inputs change the results.",
    "Results reflect the rules of the selected rule set. Other practitioners and texts may interpret the same "
    "layout differently.",
    "Recommendations are informational. They are not guaranteed to produce any outcome for health, finances, "
    "relationships or wellbeing.",
    "Any structural change must be planned with qualified professionals such as an architect or structural "
    "engineer, and should comply with local building regulations.",
    "This report does not replace architectural, engineering, legal or financial advice.",
]

SCORING_METHOD = ("Each rule has a weight. A finding earns its full weight when the placement is "
                  "preferred, 75% when acceptable, and 50%, 25% or 0% for low, medium or high issues. "
                  "A category score is earned ÷ possible points; the overall score is the weighted mean "
                  "of the categories that have scored findings. A room score uses the same points for "
                  "that room's own findings.")

# PDF labels and fixed sentences. Values are str.format templates; unused keyword arguments are ignored,
# so a language that does not pluralise can simply leave out {s}.
UI_EN = {
    # sections / document
    "sec_executive": "Executive summary",
    "sec_layout": "Property layout & directional assessment",
    "sec_overview": "Room-wise Vastu compliance overview",
    "sec_rooms": "Room-by-room detailed analysis",
    "sec_findings": "Vastu findings",
    "sec_remedies": "Phase-wise remedial implementation plan",
    "sec_summary": "Vastu evaluation summary",
    "sec_disclaimer": "Disclaimer",
    "doc_title": "Vastu Evaluation Report - {name}",
    "doc_subject": "Vastu evaluation report",
    "footer_note": "{name}  ·  Vastu evaluation report  ·  {date}",
    "cover_kicker": "Vastu Shastra evaluation",
    # cover
    "cover_lead": ("This report evaluates the verified floor plan of {name} with the <b>{rule_set}</b> "
                   "({methodology}). Each room, the main entrance and the nine zones of the plan are checked against "
                   "the rule set, scored with a transparent weighted method, and paired with remedies from an "
                   "approved catalogue."),
    "customer_name": "Customer name", "not_specified": "Not specified", "property": "Property",
    "property_type": "Property type", "assessment_date": "Assessment date", "overall_compliance": "Overall compliance",
    "score_card_title": "Overall Vastu compliance score",
    # layout
    "address": "Address", "built_up_area": "Built-up area", "rooms_analysed": "Rooms analysed", "north": "North",
    "main_entrance": "Main entrance", "marked": "Marked", "not_marked": "Not marked", "rule_set": "Rule set",
    "rule_set_value": "{name} v{version}",
    "eval_line": "<b>{label}</b>: {n} finding{s}, {weight} of the overall score",
    "legend_positive": "Preferred or acceptable", "legend_warning": "Needs attention",
    "legend_major": "Unfavourable", "legend_neutral": "Not evaluated",
    "layout_intro": ("Each room of the verified plan is mapped to one of nine zones (the eight directions and the "
                     "centre) using the confirmed North direction. Numbers on the plan match the room tables; colours "
                     "show each room's result under the rule set."),
    "what_evaluated": "What the rule set evaluates",
    "plan_note_start": "The brass crosshair marks the Brahmasthan (geometric centre)",
    "plan_note_entrance": ", the dark “E” marks the main entrance",
    "plan_note_no_entrance": "; no main entrance was marked, so entrance rules were not applied",
    "plan_note_end": (", and brass lines show the 3 × 3 zone grid aligned to true North. Directions around the plan "
                      "follow the confirmed North, not the page."),
    # overview
    "th_no": "No.", "th_room": "Room", "th_room_type": "Room type", "th_direction_zone": "Direction (zone)",
    "th_result": "Vastu result", "th_room_score": "Room score",
    "overview_intro": ("{n} room{s}, listed with those needing attention first. Numbers match the plan and the "
                       "detailed analysis."),
    "tile_positive": "Positive findings", "tile_warning": "Warnings", "tile_major": "Major issues",
    "th_category": "Category", "th_score": "Score", "th_earned": "Earned / possible", "th_findings": "Findings",
    "th_weight": "Weight", "score_breakdown": "Score breakdown",
    "th_zone": "Zone", "th_coverage": "Built coverage", "th_zone_rooms": "Rooms (primary zone)",
    "zone_summary": "Zone summary",
    "zone_summary_note": ("Built coverage is how much of each zone lies inside the plan outline; low coverage indicates "
                          "a cut corner."),
    # room card
    "not_scored": "Not scored", "score_chip": "Score {score}/100",
    "room_title": "Room {number}: {label} assessment",
    "meta_room_type": "Room type", "meta_zone": "Zone", "meta_direction": "Direction from centre",
    "meta_result": "Vastu result", "room_intro": "Room introduction",
    "priority_tag": "{priority} priority", "placeholder_tag": " · placeholder: no approved remedy for this rule yet",
    "on_plan_tag": " · On the plan: {visual}",
    "structural_option_needs": "Structural option, needs professional advice:",
    "no_corrective": "No corrective step is suggested by the rule set for this room.",
    "considerations": "Considerations", "recommendations": "Recommendations",
    # findings
    "findings_intro": ("Every finding below comes from a rule in the selected rule set applied to the verified plan. "
                       "The short note under each finding is the rule's own explanation."),
    "findings_positive": "Positive findings", "findings_warning": "Warnings", "findings_major": "Major issues",
    "findings_empty_positive": "No positive findings under this rule set.",
    "findings_empty_warning": "No warnings under this rule set.",
    "findings_empty_major": "No major issues under this rule set.",
    # remedies
    "remedies_intro": ("Remedies come only from the approved catalogue of the selected rule set and are grouped by "
                       "when they can reasonably be carried out. Non-structural steps come first; structural options "
                       "are listed under Long term and always need professional advice."),
    "structural_needed": "(structural, professional advice needed)",
    "nothing_scheduled": "Nothing scheduled in this phase.",
    "remedy_details": "Remedy details", "why_it_matters": "Why it matters", "recommended_action": "Recommended action",
    "on_the_plan": "On the plan", "structural_option": "Structural option",
    "consult_professional": " <b>Consult a qualified architect or structural engineer before any structural work.</b>",
    "note": "Note", "no_approved_remedy": "No approved remedy is on file for this rule yet.",
    "priority_chip": "{priority} priority",
    # summary
    "summary_lead": ("This property scores <b>{score} / 100</b> under the {rule_set}. {pos} positive finding{ps}, "
                     "{warn} warning{ws} and {maj} major issue{ms} were recorded across {rooms} rooms, the main "
                     "entrance and the nine zones."),
    "strongest": "Strongest areas", "no_positive": "No positive findings were recorded.",
    "needing_attention": "Areas needing attention", "nothing_flagged": "Nothing was flagged under this rule set.",
    "top_priorities": "Top priorities to review", "next_steps": "Recommended next steps",
    # disclaimer
    "generated_by": "Generated by {brand} on {date} from the analysis of {plan}, using the {rule_set} v{version}.",
}


class EnglishTexts:
    """Original English wording. Every method returns exactly what the report produced before languages."""

    code = "en"
    ui_strings = UI_EN

    # -- generic ----------------------------------------------------------------------------------
    def ui(self, key: str, **kw) -> str:
        return self.ui_strings[key].format(**kw)

    def join(self, items: list[str]) -> str:
        items = [i for i in items if i]
        if len(items) <= 1:
            return "".join(items)
        return ", ".join(items[:-1]) + " and " + items[-1]

    def date(self, dt: datetime) -> str:
        return f"{dt:%d %B %Y}"

    def priority(self, p: str) -> str:
        return p

    def priority_chip(self, p: str) -> str:
        return self.ui("priority_chip", priority=p.capitalize())

    # -- vocabulary -------------------------------------------------------------------------------
    def zone(self, code: str | None) -> str | None:
        return ZONE_NAMES.get(code, code) if code else None

    def room_noun(self, room_type: str, type_label: str) -> str:
        return ROOM_NOUNS.get(room_type, type_label.lower())

    def result_label(self, key: str) -> str:
        return RESULT_LABELS[key]

    def kind_label(self, kind: str) -> str:
        return KIND_LABELS.get(kind, kind.replace("_", " ").capitalize())

    def phase_label(self, phase: str) -> str:
        return PHASE_LABELS[phase]

    def category_label(self, key: str, label: str) -> str:
        return label

    def score_band(self, score: float | None) -> tuple[str, str]:
        if score is None:
            return "Not scored", "neutral"
        if score >= 75:
            return "Largely aligned", "positive"
        if score >= 50:
            return "Partly aligned", "warning"
        return "Needs attention", "major"

    def property_type(self, raw: str) -> str:
        return raw.replace("_", " ").capitalize()

    def built_up_area(self, sqft: float) -> str:
        return f"{sqft:,.0f} sq ft"

    report_title = "Vastu Evaluation Report"
    zone_system = "3 × 3 grid: eight directions and the centre (Brahmasthan)"
    scoring_method = SCORING_METHOD
    disclaimer_points = DISCLAIMER_POINTS

    def north_text(self, north: float) -> str:
        return f"{north:.0f}° clockwise from the top of the drawing"

    # -- stored analysis (identity in English) ------------------------------------------------------
    def localise_analysis(self, a: dict, rule_templates: dict[str, str]) -> dict:
        return a

    # -- room sentences ---------------------------------------------------------------------------
    def room_name(self, label: str, room_type: str, type_label: str) -> str:
        type_lower = self.room_noun(room_type, type_label)
        return label if label.lower() in type_lower or type_lower in label.lower() else f"{label} ({type_lower})"

    def room_where(self, name: str, zone_name: str, share: int, others: list[tuple[str, int]]) -> str:
        if share >= 98:
            return f"{name} lies entirely in the {zone_name} zone of the plan."
        return (f"{name} lies mainly in the {zone_name} zone, which holds {share}% of its floor area"
                + (f"; {self.join([f'{p}% falls in the {z} zone' for z, p in others])}." if others else "."))

    def room_verdict(self, status: str, rule_set_name: str, zone_name: str, room_type: str, type_label: str,
                     severity: str) -> str:
        type_lower = self.room_noun(room_type, type_label)
        if status == "issue":
            return (f"Under the {rule_set_name}, the {zone_name} is a flagged placement for a "
                    f"{type_lower} ({severity} severity).")
        return f"Under the {rule_set_name}, the {zone_name} is a {status} placement for a {type_lower}."

    def room_prefs(self, preferred: list[str], acceptable: list[str], room_type: str, type_label: str) -> str:
        type_lower = self.room_noun(room_type, type_label)
        sentence = f"The rule set lists {self.join(preferred)} as preferred"
        if acceptable:
            sentence += f" and {self.join(acceptable)} as acceptable"
        return sentence + f" for a {type_lower}."

    def room_unscored(self, type_label: str) -> str:
        return (f"The room type is set to “{type_label}”, which has no placement rule in this rule set, so "
                "the room is shown on the plan but not scored. Choose a specific room type during "
                "verification to include it in the analysis.")

    def room_straddles(self, share: int, zone_name: str) -> str:
        return f"{share}% of the room also lies in the {zone_name} zone, so its placement straddles two zones."

    def room_no_issues(self) -> str:
        return "No issues were flagged for this room under the selected rule set."

    # -- executive summary ------------------------------------------------------------------------
    def exec_intro(self, name, date, rule_set_name, version, n_rooms, has_entrance, north) -> str:
        return (f"{name} was assessed on {date} against the "
                f"{rule_set_name}, version {version}. The verified plan has {n_rooms} room"
                f"{'s' if n_rooms != 1 else ''}"
                f"{', a marked main entrance' if has_entrance else ' and no marked main entrance'}, and North was "
                f"confirmed at {north:.0f}° clockwise from the top of the drawing.")

    def exec_score(self, overall, band, strong: list[str], weak: list[str]) -> str:
        s = f"The plan scores {overall} out of 100, which this report reads as “{band.lower()}”."
        if strong:
            s += f" It is strongest on {self.join([x.lower() for x in strong])}."
        if weak:
            s += (f" The {self.join([x.lower() for x in weak])} "
                  f"{'category needs' if len(weak) == 1 else 'categories need'} the most attention.")
        return s

    def exec_counts(self, counts: dict, top: list[str]) -> str:
        s = (f"The rule engine recorded {counts['positive']} positive finding{'s' if counts['positive'] != 1 else ''}, "
             f"{counts['warning']} warning{'s' if counts['warning'] != 1 else ''} and {counts['major']} major "
             f"issue{'s' if counts['major'] != 1 else ''}.")
        if top:
            s += " The most significant: " + "; ".join(t.rstrip(".") for t in top) + "."
        return s

    def exec_remedies(self, n: int, n_imm: int, n_struct: int) -> str:
        s = f"{n} remed{'ies are' if n != 1 else 'y is'} suggested from the approved catalogue"
        s += f", {n_imm} of them immediate and non-structural" if n_imm else ""
        s += (f"; {n_struct} include{'s' if n_struct == 1 else ''} a structural option that needs professional advice."
              if n_struct else ".")
        return s

    # -- final summary ----------------------------------------------------------------------------
    def subject_line(self, subject: str, text: str) -> str:
        # avoid "Kitchen: Kitchen sits ..." when the finding already names its subject
        return text if text.startswith(subject) else f"{subject}: {text}"

    def next_immediate(self) -> str:
        return "Start with the Immediate items in the remedial plan; none of them needs construction work."

    def next_structural(self) -> str:
        return ("Discuss the structural options listed under Long term with a Vastu practitioner and a "
                "qualified architect or engineer before any work is planned.")

    def next_unscored(self, names: list[str]) -> str:
        return (f"Set a specific room type for {self.join(names)} and re-run the analysis so "
                f"{'it is' if len(names) == 1 else 'they are'} scored.")

    def next_entrance(self) -> str:
        return "Mark the main entrance on the verification screen; entrance rules are skipped without it."

    def next_rerun(self) -> str:
        return ("Re-run the analysis after any change to the plan, room types or North direction so the "
                "report stays accurate.")


# ==================================================================================================
# Marathi
# ==================================================================================================
MR_ZONES = {
    "N": "उत्तर", "NE": "ईशान्य (उत्तर-पूर्व)", "E": "पूर्व", "SE": "आग्नेय (दक्षिण-पूर्व)", "S": "दक्षिण",
    "SW": "नैऋत्य (दक्षिण-पश्चिम)", "W": "पश्चिम", "NW": "वायव्य (उत्तर-पश्चिम)", "C": "मध्य (ब्रह्मस्थान)",
}
MR_ROOM_TYPES = {
    "living": "दिवाणखाना", "kitchen": "स्वयंपाकघर", "master_bedroom": "मुख्य शयनकक्ष", "bedroom": "शयनकक्ष",
    "toilet": "शौचालय / स्नानगृह", "pooja": "देवघर", "dining": "भोजनकक्ष", "study": "अभ्यासिका",
    "staircase": "जिना", "store": "साठवण खोली", "balcony": "बाल्कनी", "utility": "युटिलिटी क्षेत्र",
    "foyer": "प्रवेशिका / पॅसेज", "parking": "पार्किंग", "other": "इतर",
}
# "for a <room>" (oblique case + साठी), used inside sentences.
MR_ROOM_FOR = {
    "living": "दिवाणखान्यासाठी", "kitchen": "स्वयंपाकघरासाठी", "master_bedroom": "मुख्य शयनकक्षासाठी",
    "bedroom": "शयनकक्षासाठी", "toilet": "शौचालय किंवा स्नानगृहासाठी", "pooja": "देवघरासाठी",
    "dining": "भोजनकक्षासाठी", "study": "अभ्यासिकेसाठी", "staircase": "जिन्यासाठी", "store": "साठवण खोलीसाठी",
    "balcony": "बाल्कनीसाठी", "utility": "युटिलिटी क्षेत्रासाठी", "foyer": "प्रवेशिका किंवा पॅसेजसाठी",
    "parking": "पार्किंगसाठी", "other": "खोलीसाठी",
}
MR_RESULTS = {"major": "प्रतिकूल", "warning": "लक्ष देणे आवश्यक", "preferred": "अत्यंत शुभ", "acceptable": "शुभ",
              "neutral": "मूल्यांकन नाही"}
MR_KINDS = {"non_structural": "बांधकामविरहित", "structural": "संरचनात्मक", "optional": "ऐच्छिक"}
MR_PHASES = {"immediate": "तात्काळ", "short_term": "अल्प मुदत", "medium_term": "मध्यम मुदत",
             "long_term": "दीर्घ मुदत"}
MR_LEVELS = {"high": "उच्च", "medium": "मध्यम", "low": "कमी", "positive": "सकारात्मक", "info": "माहिती"}
MR_STATUS = {"preferred": "पसंतीचे", "acceptable": "स्वीकार्य"}
MR_CATEGORIES = {"rooms": "खोल्या", "entrance": "प्रवेशद्वार", "zones": "क्षेत्रे", "layout": "रचना",
                 "directions": "दिशा"}
MR_PROPERTY_TYPES = {"apartment": "सदनिका (अपार्टमेंट)", "villa": "व्हिला", "independent_house": "स्वतंत्र घर",
                     "plot": "भूखंड", "office": "कार्यालय", "other": "इतर"}
MR_MONTHS = ["जानेवारी", "फेब्रुवारी", "मार्च", "एप्रिल", "मे", "जून", "जुलै", "ऑगस्ट", "सप्टेंबर", "ऑक्टोबर",
             "नोव्हेंबर", "डिसेंबर"]
# Common English room labels a user types, and the labels the rule engine generates. Anything else
# (a custom name) is kept exactly as the user wrote it. A trailing number ("Bedroom 2") is preserved.
MR_LABELS = {
    "living room": "दिवाणखाना", "living": "दिवाणखाना", "drawing room": "दिवाणखाना", "hall": "हॉल",
    "family room": "कौटुंबिक खोली", "kitchen": "स्वयंपाकघर", "master bedroom": "मुख्य शयनकक्ष",
    "master bed room": "मुख्य शयनकक्ष", "master bed": "मुख्य शयनकक्ष", "bedroom": "शयनकक्ष",
    "bed room": "शयनकक्ष", "guest room": "अतिथी कक्ष", "guest bedroom": "अतिथी शयनकक्ष",
    "kids room": "मुलांची खोली", "children room": "मुलांची खोली", "toilet": "शौचालय", "wc": "शौचालय",
    "bath": "स्नानगृह", "bathroom": "स्नानगृह", "washroom": "स्नानगृह", "pooja": "देवघर",
    "pooja room": "देवघर", "puja": "देवघर", "puja room": "देवघर", "prayer room": "देवघर", "dining": "भोजनकक्ष",
    "dining room": "भोजनकक्ष", "dining area": "भोजनकक्ष", "study": "अभ्यासिका", "study room": "अभ्यासिका",
    "office": "कार्यालय", "stairs": "जिना", "staircase": "जिना", "store": "साठवण खोली",
    "store room": "साठवण खोली", "storage": "साठवण खोली", "balcony": "बाल्कनी", "terrace": "गच्ची",
    "utility": "युटिलिटी", "laundry": "धुलाई कक्ष", "foyer": "प्रवेशिका", "passage": "पॅसेज",
    "corridor": "पॅसेज", "lobby": "लॉबी", "parking": "पार्किंग", "garage": "गॅरेज",
    # labels created by the rule engine
    "main entrance": "मुख्य प्रवेशद्वार", "windows": "खिडक्या", "doors": "दारे",
}
_ZONE_BY_ENGLISH = {v.lower(): k for k, v in ZONE_NAMES.items()}
_LABEL_RE = re.compile(r"^(?P<base>.*?)(?P<num>\s*[-#]?\s*\d+[a-z]?)?$", re.IGNORECASE)

UI_MR = {
    "sec_executive": "कार्यकारी सारांश",
    "sec_layout": "मालमत्तेची रचना आणि दिशात्मक मूल्यांकन",
    "sec_overview": "खोलीनिहाय वास्तु अनुपालन आढावा",
    "sec_rooms": "प्रत्येक खोलीचे सविस्तर विश्लेषण",
    "sec_findings": "वास्तु निष्कर्ष",
    "sec_remedies": "टप्प्याटप्प्याने उपाय अंमलबजावणी योजना",
    "sec_summary": "वास्तु मूल्यांकन सारांश",
    "sec_disclaimer": "अस्वीकरण",
    "doc_title": "वास्तु मूल्यांकन अहवाल - {name}",
    "doc_subject": "वास्तु मूल्यांकन अहवाल",
    "footer_note": "{name}  ·  वास्तु मूल्यांकन अहवाल  ·  {date}",
    "cover_kicker": "वास्तुशास्त्र मूल्यांकन",
    "cover_lead": ("हा अहवाल {name} च्या पडताळलेल्या आराखड्याचे <b>{rule_set}</b> ({methodology}) नुसार मूल्यांकन "
                   "करतो. प्रत्येक खोली, मुख्य प्रवेशद्वार आणि आराखड्यातील नऊ क्षेत्रे नियम-संचानुसार तपासली जातात, "
                   "पारदर्शक भारित पद्धतीने त्यांना गुण दिले जातात आणि मान्यताप्राप्त सूचीतील उपाय सुचवले जातात."),
    "customer_name": "ग्राहकाचे नाव", "not_specified": "नमूद नाही", "property": "मालमत्ता",
    "property_type": "मालमत्तेचा प्रकार", "assessment_date": "मूल्यांकन दिनांक", "overall_compliance": "एकूण अनुपालन",
    "score_card_title": "एकूण वास्तु अनुपालन गुण",
    "address": "पत्ता", "built_up_area": "बांधकाम क्षेत्रफळ", "rooms_analysed": "विश्लेषित खोल्या",
    "north": "उत्तर दिशा", "main_entrance": "मुख्य प्रवेशद्वार", "marked": "चिन्हांकित", "not_marked": "चिन्हांकित नाही",
    "rule_set": "नियम-संच", "rule_set_value": "{name} आवृत्ती {version}",
    "eval_line": "<b>{label}</b>: {n} निष्कर्ष, एकूण गुणांपैकी {weight}",
    "legend_positive": "पसंतीचे किंवा स्वीकार्य", "legend_warning": "लक्ष देणे आवश्यक",
    "legend_major": "प्रतिकूल", "legend_neutral": "मूल्यांकन नाही",
    "layout_intro": ("निश्चित केलेल्या उत्तर दिशेच्या आधारे पडताळलेल्या आराखड्यातील प्रत्येक खोली नऊपैकी एका "
                     "क्षेत्रात (आठ दिशा आणि मध्य) ठेवली जाते. आराखड्यावरील क्रमांक खोल्यांच्या तक्त्यांशी जुळतात; "
                     "रंग नियम-संचानुसार प्रत्येक खोलीचा निकाल दर्शवतात."),
    "what_evaluated": "नियम-संच काय तपासतो",
    "plan_note_start": "पितळी रंगाची अधिक-खूण ब्रह्मस्थान (भौमितिक मध्य) दर्शवते",
    "plan_note_entrance": ", गडद “E” मुख्य प्रवेशद्वार दर्शवते",
    "plan_note_no_entrance": "; मुख्य प्रवेशद्वार चिन्हांकित नसल्याने प्रवेशद्वाराचे नियम लागू केले नाहीत",
    "plan_note_end": (", आणि पितळी रेषा खऱ्या उत्तरेनुसार मांडलेली 3 × 3 क्षेत्र-जाळी दर्शवतात. आराखड्याभोवतीच्या "
                      "दिशा पानानुसार नव्हे, तर निश्चित केलेल्या उत्तर दिशेनुसार आहेत."),
    "th_no": "क्र.", "th_room": "खोली", "th_room_type": "खोलीचा प्रकार", "th_direction_zone": "दिशा (क्षेत्र)",
    "th_result": "वास्तु निकाल", "th_room_score": "खोलीचे गुण",
    "overview_intro": ("{n} खोल्या; लक्ष देणे आवश्यक असलेल्या खोल्या आधी दिल्या आहेत. क्रमांक आराखडा आणि सविस्तर "
                       "विश्लेषणाशी जुळतात."),
    "tile_positive": "सकारात्मक निष्कर्ष", "tile_warning": "इशारे", "tile_major": "प्रमुख दोष",
    "th_category": "श्रेणी", "th_score": "गुण", "th_earned": "मिळालेले / शक्य", "th_findings": "निष्कर्ष",
    "th_weight": "भार", "score_breakdown": "गुणांचे विवरण",
    "th_zone": "क्षेत्र", "th_coverage": "बांधकाम व्याप्ती", "th_zone_rooms": "खोल्या (मुख्य क्षेत्र)",
    "zone_summary": "क्षेत्र सारांश",
    "zone_summary_note": ("बांधकाम व्याप्ती म्हणजे प्रत्येक क्षेत्राचा किती भाग आराखड्याच्या सीमेच्या आत आहे; कमी "
                          "व्याप्ती कापलेला कोपरा दर्शवते."),
    "not_scored": "गुण दिलेले नाहीत", "score_chip": "गुण {score}/100",
    "room_title": "खोली {number}: {label} मूल्यांकन",
    "meta_room_type": "खोलीचा प्रकार", "meta_zone": "क्षेत्र", "meta_direction": "मध्यापासून दिशा",
    "meta_result": "वास्तु निकाल", "room_intro": "खोलीचा परिचय",
    "priority_tag": "{priority} प्राधान्य", "placeholder_tag": " · तात्पुरती नोंद: या नियमासाठी अद्याप मान्यताप्राप्त उपाय नाही",
    "on_plan_tag": " · आराखड्यावर: {visual}",
    "structural_option_needs": "संरचनात्मक पर्याय, व्यावसायिक सल्ला आवश्यक:",
    "no_corrective": "या खोलीसाठी नियम-संचाने कोणताही सुधारात्मक उपाय सुचवलेला नाही.",
    "considerations": "विचारात घ्यावयाच्या बाबी", "recommendations": "शिफारसी",
    "findings_intro": ("खालील प्रत्येक निष्कर्ष निवडलेल्या नियम-संचातील एखादा नियम पडताळलेल्या आराखड्याला लागू करून "
                       "काढला आहे. प्रत्येक निष्कर्षाखालील छोटी टीप हे त्या नियमाचेच स्पष्टीकरण आहे."),
    "findings_positive": "सकारात्मक निष्कर्ष", "findings_warning": "इशारे", "findings_major": "प्रमुख दोष",
    "findings_empty_positive": "या नियम-संचानुसार कोणतेही सकारात्मक निष्कर्ष नाहीत.",
    "findings_empty_warning": "या नियम-संचानुसार कोणतेही इशारे नाहीत.",
    "findings_empty_major": "या नियम-संचानुसार कोणतेही प्रमुख दोष नाहीत.",
    "remedies_intro": ("उपाय केवळ निवडलेल्या नियम-संचाच्या मान्यताप्राप्त सूचीतूनच घेतले आहेत आणि ते केव्हा करता "
                       "येतील त्यानुसार गटबद्ध केले आहेत. बांधकामविरहित उपाय आधी दिले आहेत; संरचनात्मक पर्याय "
                       "‘दीर्घ मुदत’ अंतर्गत दिले आहेत आणि त्यांसाठी नेहमी व्यावसायिक सल्ला आवश्यक आहे."),
    "structural_needed": "(संरचनात्मक, व्यावसायिक सल्ला आवश्यक)",
    "nothing_scheduled": "या टप्प्यात काहीही नियोजित नाही.",
    "remedy_details": "उपायांचा तपशील", "why_it_matters": "हे का महत्त्वाचे", "recommended_action": "शिफारस केलेली कृती",
    "on_the_plan": "आराखड्यावर", "structural_option": "संरचनात्मक पर्याय",
    "consult_professional": " <b>कोणतेही संरचनात्मक काम करण्यापूर्वी पात्र वास्तुविशारद किंवा संरचना अभियंत्याचा सल्ला घ्या.</b>",
    "note": "टीप", "no_approved_remedy": "या नियमासाठी अद्याप मान्यताप्राप्त उपाय नोंदवलेला नाही.",
    "priority_chip": "{priority} प्राधान्य",
    "summary_lead": ("{rule_set} नुसार या मालमत्तेला <b>100 पैकी {score}</b> गुण मिळाले आहेत. {rooms} खोल्या, "
                     "मुख्य प्रवेशद्वार आणि नऊ क्षेत्रांमध्ये {pos} सकारात्मक निष्कर्ष, {warn} {warn_word} आणि {maj} प्रमुख "
                     "दोष नोंदवले गेले."),
    "strongest": "सर्वात सक्षम बाबी", "no_positive": "कोणतेही सकारात्मक निष्कर्ष नोंदवले गेले नाहीत.",
    "needing_attention": "लक्ष देणे आवश्यक असलेल्या बाबी", "nothing_flagged": "या नियम-संचानुसार कोणताही दोष आढळला नाही.",
    "top_priorities": "प्राधान्याने तपासाव्यात अशा बाबी", "next_steps": "पुढील शिफारस केलेली पावले",
    "generated_by": ("{brand} द्वारे {date} रोजी {plan} च्या विश्लेषणावरून, {rule_set} आवृत्ती {version} वापरून "
                     "तयार केला."),
}

MR_DISCLAIMER_POINTS = [
    "वास्तुशास्त्र ही वास्तुरचनेसंबंधी मार्गदर्शनाची एक पारंपरिक पद्धत आहे. हा अहवाल ती एक पद्धत म्हणून लागू करतो; "
    "हे वैज्ञानिक मूल्यांकन नाही.",
    "निष्कर्ष पूर्णपणे वापरकर्त्याने दिलेल्या व पडताळलेल्या आराखडा, खोल्यांचे प्रकार, मुख्य प्रवेशद्वार आणि उत्तर "
    "दिशा यांवर अवलंबून आहेत. या माहितीतील चुकांमुळे निष्कर्ष बदलतात.",
    "निष्कर्ष निवडलेल्या नियम-संचाच्या नियमांनुसार आहेत. इतर वास्तुतज्ज्ञ आणि ग्रंथ त्याच रचनेचा वेगळा अर्थ लावू "
    "शकतात.",
    "शिफारसी केवळ माहितीसाठी आहेत. आरोग्य, आर्थिक स्थिती, नातेसंबंध किंवा स्वास्थ्य यांबाबत कोणत्याही परिणामाची "
    "हमी त्या देत नाहीत.",
    "कोणत्याही संरचनात्मक बदलाचे नियोजन वास्तुविशारद किंवा संरचना अभियंता यांसारख्या पात्र व्यावसायिकांसोबत करावे "
    "आणि ते स्थानिक बांधकाम नियमांनुसार असावे.",
    "हा अहवाल वास्तुविशारद, अभियांत्रिकी, कायदेशीर किंवा आर्थिक सल्ल्याची जागा घेत नाही.",
]

MR_SCORING_METHOD = (
    "प्रत्येक नियमाला एक भार असतो. स्थान पसंतीचे असल्यास निष्कर्षाला पूर्ण भार मिळतो, स्वीकार्य असल्यास 75%, आणि "
    "कमी, मध्यम किंवा उच्च दोषांसाठी अनुक्रमे 50%, 25% किंवा 0%. श्रेणीचे गुण = मिळालेले ÷ शक्य गुण; एकूण गुण "
    "म्हणजे गुणांकित निष्कर्ष असलेल्या श्रेणींची भारित सरासरी. खोलीचे गुण त्या खोलीच्या स्वतःच्या निष्कर्षांसाठी "
    "याच पद्धतीने काढले जातात.")

# Fixed English strings created outside the catalogue (remedy engine placeholder, rule engine).
_EN_PLACEHOLDER_EXPLANATION = "No approved remedy is on file for this rule yet."
_EN_PLACEHOLDER_RECOMMENDATION = "Consult a qualified Vastu practitioner before making changes."


@lru_cache(maxsize=None)
def load_catalogue(code: str) -> dict:
    path = LOCALES_DIR / f"{code}.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _template_regex(template: str) -> re.Pattern:
    """English finding template -> regex that recovers the values substituted into it."""
    out, seen, pos = [], set(), 0
    for m in re.finditer(r"\{(\w+)\}", template):
        out.append(re.escape(template[pos:m.start()]))
        name = m.group(1)
        out.append(f"(?P={name})" if name in seen else f"(?P<{name}>.+?)")
        seen.add(name)
        pos = m.end()
    out.append(re.escape(template[pos:]))
    return re.compile("".join(out), re.DOTALL)


class MarathiTexts(EnglishTexts):
    code = "mr"
    ui_strings = UI_MR
    report_title = "वास्तु मूल्यांकन अहवाल"
    zone_system = "3 × 3 ग्रिड: आठ दिशा आणि मध्य (ब्रह्मस्थान)"
    scoring_method = MR_SCORING_METHOD
    disclaimer_points = MR_DISCLAIMER_POINTS

    def __init__(self):
        self.cat = load_catalogue("mr")
        self.missing: set[str] = set()  # catalogue codes without Marathi text (logged once per report)

    # -- generic ----------------------------------------------------------------------------------
    def ui(self, key: str, **kw) -> str:
        if "warn" in kw:  # इशारा (one) / इशारे (several); the other count nouns do not change
            kw["warn_word"] = self.warnings(kw["warn"])
        return super().ui(key, **kw)

    @staticmethod
    def warnings(n: int) -> str:
        return "इशारा" if n == 1 else "इशारे"

    def join(self, items: list[str]) -> str:
        items = [i for i in items if i]
        if len(items) <= 1:
            return "".join(items)
        return ", ".join(items[:-1]) + " आणि " + items[-1]

    def date(self, dt: datetime) -> str:
        return f"{dt.day:02d} {MR_MONTHS[dt.month - 1]} {dt.year}"

    def priority(self, p: str) -> str:
        return MR_LEVELS.get(p, p)

    def priority_chip(self, p: str) -> str:
        return self.ui("priority_chip", priority=self.priority(p))

    # -- vocabulary -------------------------------------------------------------------------------
    def zone(self, code: str | None) -> str | None:
        return MR_ZONES.get(code, code) if code else None

    def room_type_label(self, room_type: str, fallback: str) -> str:
        return MR_ROOM_TYPES.get(room_type, fallback)

    def room_for(self, room_type: str) -> str:
        return MR_ROOM_FOR.get(room_type, MR_ROOM_FOR["other"])

    def room_noun(self, room_type: str, type_label: str) -> str:
        return MR_ROOM_TYPES.get(room_type, type_label)

    def result_label(self, key: str) -> str:
        return MR_RESULTS[key]

    def kind_label(self, kind: str) -> str:
        return MR_KINDS.get(kind, kind.replace("_", " "))

    def phase_label(self, phase: str) -> str:
        return MR_PHASES[phase]

    def category_label(self, key: str, label: str) -> str:
        return MR_CATEGORIES.get(key, label)

    def score_band(self, score: float | None) -> tuple[str, str]:
        if score is None:
            return "गुण दिलेले नाहीत", "neutral"
        if score >= 75:
            return "बहुतांश अनुरूप", "positive"
        if score >= 50:
            return "अंशतः अनुरूप", "warning"
        return "लक्ष देणे आवश्यक", "major"

    def property_type(self, raw: str) -> str:
        return MR_PROPERTY_TYPES.get(raw, raw.replace("_", " "))

    def built_up_area(self, sqft: float) -> str:
        return f"{sqft:,.0f} चौ. फूट"

    def north_text(self, north: float) -> str:
        return f"रेखाचित्राच्या वरच्या बाजूपासून घड्याळाच्या दिशेने {north:.0f}°"

    def label(self, label: str | None) -> str | None:
        """A room / subject label in Marathi when it is a standard name; custom names are kept as typed."""
        if not label:
            return label
        text = label.strip()
        low = text.lower()
        if low in _ZONE_BY_ENGLISH:
            return MR_ZONES[_ZONE_BY_ENGLISH[low]]
        if low.endswith(" zone") and low[:-5] in _ZONE_BY_ENGLISH:
            return MR_ZONES[_ZONE_BY_ENGLISH[low[:-5]]] + " क्षेत्र"
        m = _LABEL_RE.match(text)
        base = (m.group("base") or "").strip().lower() if m else low
        if base in MR_LABELS:
            return MR_LABELS[base] + (m.group("num") or "")
        return label

    # -- catalogue --------------------------------------------------------------------------------
    def _rule(self, code: str | None) -> dict | None:
        entry = self.cat["rules"].get(code) if code else None
        if code and entry is None:
            self.missing.add(f"rule:{code}")
        return entry

    def rule_set(self, rs: dict) -> dict:
        tr = self.cat["rule_sets"].get(rs.get("code"))
        if not tr:
            self.missing.add(f"rule_set:{rs.get('code')}")
            return rs
        return {**rs, **{k: tr[k] for k in ("name", "methodology", "disclaimer") if tr.get(k)}}

    def finding_text(self, f: dict, en_template: str | None) -> str:
        if f["status"] == "not_evaluated" and not f.get("rule_code"):
            # Built by the rule engine, not the catalogue (see vastu.engine.evaluate).
            name = self.label(f["subject_label"])
            kind = self.room_type_label(f.get("room_type") or "other", f.get("room_type") or "")
            if "has no placement rule" in f["finding"]:
                return f"{name} ({kind}) साठी या नियम-संचात स्थान-नियम नाही; गुण दिलेले नाहीत."
            return f"{name} ({kind}) साठी {self.zone(f.get('zone'))} क्षेत्राचा नियम नाही; गुण दिलेले नाहीत."
        entry = self._rule(f.get("rule_code"))
        if not entry or not entry.get("finding_template"):
            return f["finding"]
        tpl = entry["finding_template"]
        values = {"room": self.label(f["subject_label"]), "zone": f.get("zone") or "",
                  "zone_name": self.zone(f.get("zone")) or ""}
        needs = set(re.findall(r"\{(\w+)\}", tpl)) - set(values)
        if needs:  # numbers (share, coverage, count) are recovered from the stored English sentence
            m = _template_regex(en_template).fullmatch(f["finding"]) if en_template else None
            if not m or not needs <= set(m.groupdict()):
                self.missing.add(f"template:{f.get('rule_code')}")
                return f["finding"]
            values.update({k: m.group(k) for k in needs})
        return tpl.format(**values)

    def rule_explanation(self, f: dict) -> str | None:
        if not f.get("explanation"):
            return f.get("explanation")
        entry = self._rule(f.get("rule_code"))
        return entry.get("explanation") or f["explanation"] if entry else f["explanation"]

    def remedy(self, remedy: dict | None, finding_text: str) -> dict | None:
        if not remedy:
            return remedy
        out = dict(remedy)
        if not remedy.get("code"):  # remedy engine placeholder: no approved remedy on file
            out["problem"] = finding_text
            if remedy.get("explanation") == _EN_PLACEHOLDER_EXPLANATION:
                out["explanation"] = UI_MR["no_approved_remedy"]
            if remedy.get("recommendation") == _EN_PLACEHOLDER_RECOMMENDATION:
                out["recommendation"] = "कोणताही बदल करण्यापूर्वी पात्र वास्तुतज्ज्ञांचा सल्ला घ्या."
            return out
        tr = self.cat["remedies"].get(remedy["code"])
        if not tr:
            self.missing.add(f"remedy:{remedy['code']}")
            return out
        for k in ("problem", "explanation", "recommendation", "visual_instruction", "structural_note"):
            if remedy.get(k) and tr.get(k):
                out[k] = tr[k]
        return out

    def localise_analysis(self, a: dict, rule_templates: dict[str, str]) -> dict:
        """Translated copy of analysis_out(): same ids, codes, numbers and buckets; Marathi wording."""
        a = dict(a)
        a["rule_set"] = self.rule_set(a["rule_set"])
        findings = []
        for f in a["findings"]:
            f = dict(f)
            text = self.finding_text(f, rule_templates.get(f.get("rule_code") or ""))
            f["remedy"] = self.remedy(f.get("remedy"), text)
            f["finding"], f["explanation"] = text, self.rule_explanation(f)
            f["subject_label"] = self.label(f["subject_label"])
            f["zone_name"] = self.zone(f.get("zone"))
            findings.append(f)
        a["findings"] = findings
        a["rooms"] = [dict(r, label=self.label(r["label"]),
                           room_type_label=self.room_type_label(r["room_type"], r["room_type_label"]),
                           zone_name=self.zone(r["zone"])) for r in a["rooms"]]
        a["zones"] = [dict(z, name=self.zone(z["code"]) or z["name"]) for z in a["zones"]]
        if self.missing:
            log.warning("Marathi report: no translation for %s; English text used", sorted(self.missing))
        return a

    # -- room sentences ---------------------------------------------------------------------------
    def room_name(self, label: str, room_type: str, type_label: str) -> str:
        noun = self.room_noun(room_type, type_label)
        return label if label in noun or noun in label else f"{label} ({noun})"

    def room_where(self, name: str, zone_name: str, share: int, others: list[tuple[str, int]]) -> str:
        if share >= 98:
            return f"{name} पूर्णपणे आराखड्याच्या {zone_name} क्षेत्रात आहे."
        return (f"{name} मुख्यतः {zone_name} क्षेत्रात आहे; खोलीच्या क्षेत्रफळापैकी {share}% भाग या क्षेत्रात येतो"
                + (f"; {self.join([f'{p}% भाग {z} क्षेत्रात येतो' for z, p in others])}." if others else "."))

    def room_verdict(self, status, rule_set_name, zone_name, room_type, type_label, severity) -> str:
        if status == "issue":
            return (f"{rule_set_name} नुसार {zone_name} हे {self.room_for(room_type)} योग्य स्थान मानले जात नाही "
                    f"({self.priority(severity)} तीव्रता).")
        return f"{rule_set_name} नुसार {zone_name} हे {self.room_for(room_type)} {MR_STATUS.get(status, status)} स्थान आहे."

    def room_prefs(self, preferred, acceptable, room_type, type_label) -> str:
        parts = []
        if preferred:
            parts.append(f"{self.join(preferred)} {'हे क्षेत्र' if len(preferred) == 1 else 'ही क्षेत्रे'} पसंतीची")
        if acceptable:
            parts.append(f"{self.join(acceptable)} {'हे क्षेत्र' if len(acceptable) == 1 else 'ही क्षेत्रे'} स्वीकार्य")
        return f"हा नियम-संच {self.room_for(room_type)} " + " आणि ".join(parts) + " मानतो."

    def room_unscored(self, type_label: str) -> str:
        return (f"खोलीचा प्रकार “{type_label}” असा निवडला आहे; या प्रकारासाठी या नियम-संचात स्थान-नियम नाही, त्यामुळे "
                "खोली आराखड्यावर दाखवली आहे पण तिला गुण दिलेले नाहीत. ती विश्लेषणात समाविष्ट करण्यासाठी पडताळणीच्या "
                "वेळी खोलीचा नेमका प्रकार निवडा.")

    def room_straddles(self, share: int, zone_name: str) -> str:
        return f"खोलीचा {share}% भाग {zone_name} क्षेत्रातही येतो, त्यामुळे तिचे स्थान दोन क्षेत्रांमध्ये विभागलेले आहे."

    def room_no_issues(self) -> str:
        return "निवडलेल्या नियम-संचानुसार या खोलीसाठी कोणताही दोष आढळला नाही."

    # -- executive summary ------------------------------------------------------------------------
    def exec_intro(self, name, date, rule_set_name, version, n_rooms, has_entrance, north) -> str:
        rooms = "1 खोली आहे" if n_rooms == 1 else f"{n_rooms} खोल्या आहेत"
        entrance = ", मुख्य प्रवेशद्वार चिन्हांकित आहे" if has_entrance else " आणि मुख्य प्रवेशद्वार चिन्हांकित नाही"
        return (f"{name} चे मूल्यांकन {date} रोजी {rule_set_name}, आवृत्ती {version} नुसार करण्यात आले. पडताळलेल्या "
                f"आराखड्यात {rooms}{entrance}, आणि उत्तर दिशा रेखाचित्राच्या वरच्या बाजूपासून घड्याळाच्या दिशेने "
                f"{north:.0f}° वर निश्चित करण्यात आली.")

    def exec_score(self, overall, band, strong, weak) -> str:
        s = f"आराखड्याला 100 पैकी {overall} गुण मिळाले आहेत; हा अहवाल याचा अर्थ “{band}” असा लावतो."
        if strong:
            s += f" {self.join(strong)} या {'श्रेणीत' if len(strong) == 1 else 'श्रेणींमध्ये'} आराखडा सर्वाधिक सक्षम आहे."
        if weak:
            s += f" {self.join(weak)} या {'श्रेणीकडे' if len(weak) == 1 else 'श्रेणींकडे'} सर्वाधिक लक्ष देणे आवश्यक आहे."
        return s

    def exec_counts(self, counts, top) -> str:
        s = (f"नियम-इंजिनने {counts['positive']} सकारात्मक निष्कर्ष, {counts['warning']} "
             f"{self.warnings(counts['warning'])} आणि "
             f"{counts['major']} प्रमुख दोष नोंदवले.")
        if top:
            s += " सर्वात महत्त्वाचे: " + "; ".join(t.rstrip(".") for t in top) + "."
        return s

    def exec_remedies(self, n, n_imm, n_struct) -> str:
        s = f"मान्यताप्राप्त सूचीमधून {n} उपाय सुचवले आहेत"
        s += f", त्यापैकी {n_imm} तात्काळ आणि बांधकामविरहित आहेत" if n_imm else ""
        s += (f"; {n_struct} उपायांमध्ये संरचनात्मक पर्याय आहे, ज्यासाठी व्यावसायिक सल्ला आवश्यक आहे."
              if n_struct else ".")
        return s

    # -- final summary ----------------------------------------------------------------------------
    def next_immediate(self) -> str:
        return "उपाय-योजनेतील ‘तात्काळ’ उपायांपासून सुरुवात करा; त्यांपैकी कोणत्याही उपायासाठी बांधकाम आवश्यक नाही."

    def next_structural(self) -> str:
        return ("‘दीर्घ मुदत’ अंतर्गत दिलेल्या संरचनात्मक पर्यायांबाबत कोणतेही काम ठरवण्यापूर्वी वास्तुतज्ज्ञ आणि पात्र "
                "वास्तुविशारद किंवा अभियंत्याशी चर्चा करा.")

    def next_unscored(self, names) -> str:
        return (f"{self.join(names)} साठी खोलीचा नेमका प्रकार निवडा आणि विश्लेषण पुन्हा चालवा, म्हणजे "
                f"{'तिला' if len(names) == 1 else 'त्यांना'} गुण दिले जातील.")

    def next_entrance(self) -> str:
        return "पडताळणी स्क्रीनवर मुख्य प्रवेशद्वार चिन्हांकित करा; त्याशिवाय प्रवेशद्वाराचे नियम तपासले जात नाहीत."

    def next_rerun(self) -> str:
        return ("आराखडा, खोल्यांचे प्रकार किंवा उत्तर दिशा यांमध्ये कोणताही बदल केल्यानंतर विश्लेषण पुन्हा चालवा, "
                "म्हणजे अहवाल अचूक राहील.")


def texts_for(language: str) -> EnglishTexts:
    if language == "en":
        return EnglishTexts()
    if language == "mr":
        return MarathiTexts()
    raise ValueError(f"Unsupported report language '{language}'. Available: {LANGUAGES}")
