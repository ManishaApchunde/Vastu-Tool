"""Remedy engine: Finding -> Rule -> approved Remedy.

Remedies come only from the approved remedy catalogue. If a rule points to a remedy that is
missing or not approved, the finding gets an explicit 'consult a practitioner' placeholder
instead of generated text."""
from app.vastu.types import FindingResult, RemedySpec

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def attach_remedies(findings: list[FindingResult], catalogue: dict[str, RemedySpec]) -> list[FindingResult]:
    for f in findings:
        if f.status != "issue":
            continue
        remedy = catalogue.get(f.remedy_code) if f.remedy_code else None
        if remedy:
            f.remedy = {
                "id": remedy.id, "code": remedy.code, "problem": remedy.problem,
                "explanation": remedy.explanation, "recommendation": remedy.recommendation,
                "priority": remedy.priority, "visual_instruction": remedy.visual_instruction, "approved": True,
                "kind": remedy.kind or "non_structural", "phase": remedy.phase,
                "structural_note": remedy.structural_note,
            }
        else:
            f.remedy = {
                "id": None, "code": None, "problem": f.finding,
                "explanation": "No approved remedy is on file for this rule yet.",
                "recommendation": "Consult a qualified Vastu practitioner before making changes.",
                "priority": "high" if f.severity == "high" else "medium", "visual_instruction": None,
                "approved": False, "kind": "non_structural", "phase": None, "structural_note": None,
            }
    return findings


def remedy_list(findings: list[FindingResult]) -> list[dict]:
    items = [dict(f.remedy, subject=f.subject_label, zone=f.zone, severity=f.severity)
             for f in findings if f.remedy]
    return sorted(items, key=lambda r: PRIORITY_ORDER.get(r["priority"], 3))


# --- Implementation phases ----------------------------------------------------------------------
# A remedy's phase is curated in the catalogue when it matters (e.g. "mark the entrance" is
# immediate even though it is low priority). Otherwise it is derived from kind + priority:
#   non-structural: high -> immediate, medium -> short term, low -> medium term
#   optional -> medium term; structural -> long term
# A remedy's structural_note is always a separate long-term item, because structural work needs
# planning with qualified professionals.
PHASES = ("immediate", "short_term", "medium_term", "long_term")
PHASE_LABELS = {"immediate": "Immediate", "short_term": "Short term", "medium_term": "Medium term",
                "long_term": "Long term"}
_BY_PRIORITY = {"high": "immediate", "medium": "short_term", "low": "medium_term"}


def phase_for(remedy: dict) -> str:
    if remedy.get("phase") in PHASES:
        return remedy["phase"]
    kind = remedy.get("kind") or "non_structural"
    if kind == "structural":
        return "long_term"
    if kind == "optional":
        return "medium_term"
    return _BY_PRIORITY.get(remedy.get("priority"), "medium_term")
