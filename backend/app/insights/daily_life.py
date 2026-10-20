"""Vastu vs Daily-Life Conflict Detector.

Checks whether following a remedy would get in the way of how the room is used: furniture pushed
against a doorway, a heavy wardrobe in front of the only window, a bed squeezed into a room that is
too narrow, a toilet kept shut with no window, or a 'keep the centre open' remedy in a room whose
centre normally holds the dining table or the bed. It uses the verified geometry only."""
import math

from app.geometry.primitives import GeometryError
from app.insights.common import openings_in_cell, remedy_fit, room_cells

CENTRE_USE = {"dining": "the dining table", "bedroom": "the bed", "master_bedroom": "the bed",
              "living": "the main seating", "kitchen": "the working area", "study": "the desk"}
CORNER_WORDS = {"N": "North side", "NE": "North-East corner", "E": "East side", "SE": "South-East corner",
                "S": "South side", "SW": "South-West corner", "W": "West side", "NW": "North-West corner",
                "C": "centre"}


def detect_conflicts(a: dict, snapshot: dict, north_angle: float, ft_per_px: float | None) -> dict:
    rooms = {r["id"]: r for r in snapshot.get("rooms", [])}
    openings = snapshot.get("openings", [])
    centre = snapshot.get("centre")
    conflicts, clear, disruptions = [], [], []
    checked = 0
    for f in a["findings"]:
        r = f.get("remedy")
        room = rooms.get(f.get("subject_ref") or "")
        if f["status"] != "issue" or not r:
            continue
        meta = remedy_fit(r)
        if meta["structural"]:
            disruptions.append({
                "finding_id": f["id"], "subject": f["subject_label"],
                "message": f"The structural option for {f['subject_label']} means the "
                           f"{'room' if room else 'area'} can't be used normally while work is under way, and "
                           "involves noise, dust and contractors in the home.",
                "requires": meta["structural"]["requires"]})
        if not room or not centre:
            continue
        checked += 1
        before = len(conflicts)
        try:
            up, cells = room_cells(room["polygon"], centre, north_angle)
        except GeometryError:
            continue
        minx, miny, maxx, maxy = up.bounds
        tol = 0.06 * math.hypot(maxx - minx, maxy - miny)
        everyday = meta["everyday"]
        anchor = everyday.get("anchor")
        base = {"finding_id": f["id"], "room_id": room["id"], "room": room["label"], "remedy_code": r.get("code")}
        if anchor:
            corner, item = anchor["corner"], anchor["item"]
            near = openings_in_cell(cells[corner], up, openings, centre, north_angle, tol)
            doors = [o for o in near if o["kind"] == "door"]
            windows = [o for o in near if o["kind"] == "window"]
            where = CORNER_WORDS[corner]
            if doors:
                conflicts.append({**base, "kind": "blocks_door", "severity": "high" if anchor.get("heavy") else "medium",
                                  "message": f"The remedy puts the {item} in the {where} of {room['label']}, but a door "
                                             "opens there. It would block the way in or the door swing.",
                                  "suggestion": f"Keep the {item} as close to the {where} as the door allows, or "
                                                "ask a practitioner about the nearest acceptable position."})
            if windows and anchor.get("heavy"):
                conflicts.append({**base, "kind": "blocks_window", "severity": "medium",
                                  "message": f"A window is in the {where} of {room['label']}; a {item} there could "
                                             "block daylight and ventilation.",
                                  "suggestion": f"Use a low {item} under the window, or shift it along the wall."})
            if anchor.get("min_side_ft") and ft_per_px:
                short_ft = min(maxx - minx, maxy - miny) * ft_per_px
                if short_ft < anchor["min_side_ft"]:
                    conflicts.append({**base, "kind": "tight_space", "severity": "medium",
                                      "message": f"{room['label']} is about {short_ft:.0f} ft across at its narrowest. "
                                                 f"Moving the {item} into the {where} may leave too little room to "
                                                 "walk around it.",
                                      "suggestion": "Measure on site first; a smaller piece or a different wall may "
                                                    "work better."})
        for zone in everyday.get("keep_clear", []):
            if zone == "C" and room["room_type"] in CENTRE_USE:
                use = CENTRE_USE[room["room_type"]]
                conflicts.append({**base, "kind": "centre_furniture", "severity": "medium",
                                  "message": f"Keeping the centre of {room['label']} open conflicts with where "
                                             f"{use} normally goes.",
                                  "suggestion": f"Shift {use} off-centre or choose a lighter, movable piece; keep the "
                                                "exact centre point clear."})
        if room["room_type"] == "toilet" and "habit" in everyday.get("requires", []):
            has_window = bool(openings_in_cell(up.envelope.buffer(tol), up, [o for o in openings if o["kind"] == "window"],
                                               centre, north_angle, tol))
            if not has_window:
                conflicts.append({**base, "kind": "ventilation", "severity": "low",
                                  "message": f"The remedy asks to keep {room['label']} closed and dry, but no window "
                                             "is marked there.",
                                  "suggestion": "Fit an exhaust fan or a ventilator so the space stays dry with the "
                                                "door closed."})
        if len(conflicts) == before:
            clear.append({"finding_id": f["id"], "room": room["label"], "remedy": r["recommendation"]})
    seen, unique = set(), []
    for c in conflicts:  # two findings on one room can trigger the same practical clash
        key = (c["room_id"], c["kind"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    conflicts = unique
    by_subject = {}
    for d in disruptions:
        by_subject.setdefault(d["subject"], d)
    disruptions = list(by_subject.values())
    order = {"high": 0, "medium": 1, "low": 2}
    conflicts.sort(key=lambda c: order[c["severity"]])
    return {"conflicts": conflicts, "clear": clear, "disruptions": disruptions, "checked_rooms": checked,
            "scale_known": ft_per_px is not None,
            "note": "Checks use the verified plan. Door swings and furniture sizes aren't drawn, so treat these as "
                    "prompts to measure on site."}

