import json
from pathlib import Path

from app.geometry.engine import OpeningInput, PlanInput, RoomInput, compute_zones
from app.remedies.engine import attach_remedies
from app.scoring.engine import DEFAULT_SCORING, score
from app.vastu.engine import evaluate
from app.vastu.room_types import infer_room_type
from app.vastu.types import FindingResult, RemedySpec, RuleSpec

DATA = Path(__file__).parents[1] / "app" / "seed" / "data"
SQUARE = [[0, 0], [300, 0], [300, 300], [0, 300]]


def load_rules():
    return [RuleSpec(None, r["code"], r["category"], r["subject_type"], r["subject"], r["condition"], r["outcome"],
                     r["severity"], r["weight"], r["finding_template"], r["explanation"], r["remedy_code"])
            for r in json.loads((DATA / "rules.json").read_text())["rules"]]


def cell(zone):
    col = {"W": 0, "NW": 0, "SW": 0, "N": 1, "C": 1, "S": 1, "E": 2, "NE": 2, "SE": 2}[zone]
    row = {"NW": 0, "N": 0, "NE": 0, "W": 1, "C": 1, "E": 1, "SW": 2, "S": 2, "SE": 2}[zone]
    x, y = col * 100, row * 100
    return [[x + 5, y + 5], [x + 95, y + 5], [x + 95, y + 95], [x + 5, y + 95]]


def run(rooms, openings=()):
    zr = compute_zones(PlanInput(SQUARE, [RoomInput(f"r{i}", l, t, cell(z)) for i, (l, t, z) in enumerate(rooms)],
                                 [OpeningInput(f"o{i}", k, m, p) for i, (k, m, p) in enumerate(openings)]), 0)
    return evaluate(zr, load_rules())


def room_finding(findings, label):
    return next(f for f in findings if f.subject_label == label and f.category == "rooms")


def test_every_room_type_rule_covers_all_zones_once():
    rules = load_rules()
    by_type = {}
    for r in rules:
        if r.condition["type"] == "room_in_zone":
            by_type.setdefault(r.subject, []).extend(r.condition["zones"])
    for zones in by_type.values():
        assert sorted(zones) == sorted(["N", "NE", "E", "SE", "S", "SW", "W", "NW", "C"])


def test_kitchen_south_east_is_preferred():
    f = room_finding(run([("Kitchen", "kitchen", "SE")]), "Kitchen")
    assert (f.status, f.bucket) == ("preferred", "positive")
    assert "South-East" in f.finding


def test_toilet_north_east_is_major():
    f = room_finding(run([("Toilet", "toilet", "NE")]), "Toilet")
    assert (f.status, f.severity, f.bucket) == ("issue", "high", "major")
    assert f.remedy_code == "toilet_ne_centre"


def test_unknown_room_type_is_not_scored():
    f = room_finding(run([("Gym", "other", "N")]), "Gym")
    assert f.status == "not_evaluated" and f.weight == 0


def test_centre_obstruction_and_open_centre():
    blocked = run([("Bath", "toilet", "C")])
    assert any(f.rule_code == "brahmasthan_obstructed" for f in blocked)
    assert not any(f.rule_code == "brahmasthan_open" for f in blocked)
    open_ = run([("Living", "living", "N")])
    assert any(f.rule_code == "brahmasthan_open" for f in open_)


def test_entrance_rules_and_missing_entrance():
    f = run([("Living", "living", "N")], [("door", True, [150, 0])])
    assert any(x.category == "entrance" and x.status == "preferred" for x in f)
    f2 = run([("Living", "living", "N")])
    assert any(x.rule_code == "entrance_not_marked" and x.weight == 0 for x in f2)


def test_score_is_derived_from_findings():
    good = score(run([("Kitchen", "kitchen", "SE"), ("MB", "master_bedroom", "SW")], [("door", True, [150, 0])]),
                 DEFAULT_SCORING)
    bad = score(run([("Kitchen", "kitchen", "NE"), ("MB", "master_bedroom", "C")], [("door", True, [0, 300])]),
                DEFAULT_SCORING)
    assert good["category_scores"]["rooms"] == 100
    assert bad["category_scores"]["rooms"] == 0
    assert good["overall"] > bad["overall"]


def test_score_math_is_transparent():
    f1 = FindingResult(None, "a", "rooms", "room", "x", "A", "kitchen", "SE", "SE", "preferred", "positive", 2, "", None)
    f2 = FindingResult(None, "b", "rooms", "room", "y", "B", "toilet", "NE", "NE", "issue", "medium", 2, "", None)
    out = score([f1, f2], DEFAULT_SCORING)
    assert out["category_scores"]["rooms"] == round(100 * (2 * 1.0 + 2 * 0.25) / 4)
    assert out["overall"] == out["category_scores"]["rooms"]  # only category with data


def test_remedy_only_from_catalogue():
    f = FindingResult(None, "a", "rooms", "room", "x", "T", "toilet", "NE", "NE", "issue", "high", 3, "t", None,
                      remedy_code="toilet_ne_centre")
    g = FindingResult(None, "b", "rooms", "room", "y", "K", "kitchen", "NE", "NE", "issue", "high", 3, "k", None,
                      remedy_code="missing_code")
    cat = {"toilet_ne_centre": RemedySpec("id1", "toilet_ne_centre", "P", "E", "R", "high")}
    attach_remedies([f, g], cat)
    assert f.remedy["approved"] and f.remedy["recommendation"] == "R"
    assert not g.remedy["approved"] and "practitioner" in g.remedy["recommendation"]


def test_room_type_inference():
    assert infer_room_type("Master Bedroom") == "master_bedroom"
    assert infer_room_type("W.C.") == "toilet"
    assert infer_room_type("Puja") == "pooja"
    assert infer_room_type("Kids Room") == "bedroom"
