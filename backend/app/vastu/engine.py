"""Vastu rule engine.

Input : verified geometry already assigned to zones (ZoneResult) + a list of approved RuleSpec.
Output: FindingResult per evaluated subject.

Rules are data. Each rule has a `condition` whose `type` selects an evaluator below. To support a
new kind of rule, add an evaluator function and register it in EVALUATORS - no rule text lives here.
"""
from collections import defaultdict
from collections.abc import Callable

from app.geometry.engine import ZoneResult
from app.geometry.zones import ZONE_NAMES
from app.vastu.room_types import ROOM_TYPES
from app.vastu.types import FindingResult, RuleSpec

SEVERITY_RANK = {"high": 4, "medium": 3, "low": 2, "positive": 1, "info": 0}


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _render(template: str, **ctx) -> str:
    return template.format_map(_SafeDict(**ctx))


def _finding(rule: RuleSpec, *, subject_ref, label, room_type, zone, direction, **ctx) -> FindingResult:
    zone_name = ZONE_NAMES.get(zone, zone) if zone else ""
    return FindingResult(
        rule_id=rule.id, rule_code=rule.code, category=rule.category, subject_type=rule.subject_type,
        subject_ref=subject_ref, subject_label=label, room_type=room_type, zone=zone, direction=direction,
        status=rule.outcome, severity=rule.severity, weight=rule.weight,
        finding=_render(rule.finding_template, room=label, zone=zone or "", zone_name=zone_name, **ctx),
        explanation=rule.explanation, remedy_code=rule.remedy_code,
    )


# --- evaluators --------------------------------------------------------------------------------
# Placement rules (room_in_zone, entrance_in_zone) are resolved together per subject so each room
# gets exactly one placement finding. The rest are evaluated independently.

def _eval_room_overlaps_zone(rule: RuleSpec, zr: ZoneResult) -> list[FindingResult]:
    zone, min_overlap = rule.condition["zone"], float(rule.condition.get("min_overlap", 0.25))
    types = rule.condition.get("room_types") or [rule.subject]
    out = []
    for r in zr.rooms:
        share = r.overlaps.get(zone, 0.0)
        if r.room_type in types and share >= min_overlap:
            out.append(_finding(rule, subject_ref=r.id, label=r.label, room_type=r.room_type, zone=zone,
                                direction=r.direction, share=f"{share:.0%}"))
    return out


def _eval_zone_free_of(rule: RuleSpec, zr: ZoneResult) -> list[FindingResult]:
    zone, min_overlap = rule.condition["zone"], float(rule.condition.get("min_overlap", 0.25))
    types = set(rule.condition["room_types"])
    blocking = [r for r in zr.rooms if r.room_type in types and r.overlaps.get(zone, 0) >= min_overlap]
    if blocking:
        return []
    return [_finding(rule, subject_ref=None, label=ZONE_NAMES.get(zone, zone), room_type=None, zone=zone,
                     direction=None)]


def _eval_zone_coverage(rule: RuleSpec, zr: ZoneResult) -> list[FindingResult]:
    zone = rule.condition["zone"]
    cov = zr.zone_coverage(zone)
    if cov is None:
        return []
    lo, hi = float(rule.condition.get("min", 0.0)), float(rule.condition.get("max", 1.0))
    if lo <= cov <= hi:
        return [_finding(rule, subject_ref=None, label=f"{ZONE_NAMES.get(zone, zone)} zone", room_type=None,
                         zone=zone, direction=None, coverage=f"{cov:.0%}")]
    return []


def _eval_opening_share(rule: RuleSpec, zr: ZoneResult) -> list[FindingResult]:
    kind, zones = rule.condition.get("kind", "window"), set(rule.condition["zones"])
    items = [o for o in zr.openings if o.kind == kind]
    if not items:
        return []
    share = sum(1 for o in items if o.zone in zones) / len(items)
    lo, hi = float(rule.condition.get("min_share", 0.0)), float(rule.condition.get("max_share", 1.0))
    if lo <= share <= hi:
        return [_finding(rule, subject_ref=None, label=f"{kind.capitalize()}s", room_type=None, zone=None,
                         direction=None, share=f"{share:.0%}", count=len(items))]
    return []


def _eval_element_missing(rule: RuleSpec, zr: ZoneResult) -> list[FindingResult]:
    if rule.condition.get("element") == "main_entrance" and not any(o.is_main_entrance for o in zr.openings):
        return [_finding(rule, subject_ref=None, label="Main entrance", room_type=None, zone=None, direction=None)]
    return []


EVALUATORS: dict[str, Callable[[RuleSpec, ZoneResult], list[FindingResult]]] = {
    "room_overlaps_zone": _eval_room_overlaps_zone,
    "zone_free_of": _eval_zone_free_of,
    "zone_coverage": _eval_zone_coverage,
    "opening_share": _eval_opening_share,
    "element_missing": _eval_element_missing,
}
PLACEMENT_TYPES = {"room_in_zone", "entrance_in_zone"}


def _pick(candidates: list[RuleSpec]) -> RuleSpec:
    # Rule sets should use disjoint zones per subject. If they overlap, the most severe rule wins,
    # so a conflict never hides an issue.
    return max(candidates, key=lambda r: (r.outcome == "issue", SEVERITY_RANK.get(r.severity, 0), r.weight))


def evaluate(zr: ZoneResult, rules: list[RuleSpec]) -> list[FindingResult]:
    findings: list[FindingResult] = []
    room_rules: dict[str, list[RuleSpec]] = defaultdict(list)
    entrance_rules: list[RuleSpec] = []

    for rule in rules:
        ctype = rule.condition.get("type")
        if ctype == "room_in_zone":
            room_rules[rule.subject].append(rule)
        elif ctype == "entrance_in_zone":
            entrance_rules.append(rule)
        elif ctype in EVALUATORS:
            findings.extend(EVALUATORS[ctype](rule, zr))

    # Room placement: exactly one finding per room.
    for room in zr.rooms:
        candidates = [r for r in room_rules.get(room.room_type, []) if room.primary_zone in r.condition["zones"]]
        if candidates:
            findings.append(_finding(_pick(candidates), subject_ref=room.id, label=room.label,
                                     room_type=room.room_type, zone=room.primary_zone, direction=room.direction))
        else:
            reason = ("has no placement rule in this rule set" if room.room_type not in room_rules
                      else f"has no rule for the {ZONE_NAMES.get(room.primary_zone, room.primary_zone)} zone")
            findings.append(FindingResult(
                rule_id=None, rule_code=None, category="rooms", subject_type="room", subject_ref=room.id,
                subject_label=room.label, room_type=room.room_type, zone=room.primary_zone,
                direction=room.direction, status="not_evaluated", severity="info", weight=0,
                finding=f"{room.label} ({ROOM_TYPES.get(room.room_type, room.room_type)}) {reason}; not scored.",
                explanation=None,
            ))

    # Main entrance placement
    for op in (o for o in zr.openings if o.is_main_entrance):
        candidates = [r for r in entrance_rules if op.zone in r.condition["zones"]]
        if candidates:
            findings.append(_finding(_pick(candidates), subject_ref=op.id, label="Main entrance",
                                     room_type=None, zone=op.zone, direction=op.direction))

    order = {"major": 0, "warning": 1, "positive": 2, "info": 3}
    findings.sort(key=lambda f: (order[f.bucket], -f.weight, f.category, f.subject_label))
    return findings
