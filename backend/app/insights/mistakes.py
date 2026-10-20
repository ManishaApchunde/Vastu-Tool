"""AI Mistake Catcher: flags likely detection or verification mistakes before they reach the analysis.

Pure function over plain dicts so it can check a saved plan or a draft from the editor. It never
changes the plan; every check says what looks wrong and how to fix it."""
import math
import re

from shapely.geometry import Point as SPoint
from shapely.ops import unary_union

from app.geometry.primitives import GeometryError, to_polygon
from app.vastu.room_types import ROOM_TYPES, infer_room_type

RESIDENTIAL = {"apartment", "villa", "independent_house"}
GENERIC = re.compile(r"^\s*(room|space|area|untitled|unknown|new room|r)\s*[-#]?\s*\d*\s*$", re.IGNORECASE)
LOW_CONFIDENCE = 0.7
# Types that legitimately share a label word with another type (a "master bed" is also a "bed").
COMPATIBLE = {("bedroom", "master_bedroom"), ("living", "dining"), ("foyer", "living"), ("utility", "balcony")}


def _check(code, severity, title, message, hint, category, subject_ids=()):
    return {"code": code, "severity": severity, "title": title, "message": message, "hint": hint,
            "category": category, "subject_ids": [s for s in subject_ids if s]}


def check_plan(*, rooms: list[dict], openings: list[dict], boundary: list | None, width: int, height: int,
               detection: dict | None = None, property_type: str | None = None,
               north: dict | None = None) -> dict:
    out: list[dict] = []
    diag = math.hypot(width, height)

    if not rooms:
        out.append(_check("no_rooms", "error", "No rooms on the plan",
                          "The plan has no rooms, so there is nothing to analyse.",
                          "Draw or accept at least one room.", "rooms"))
        return _summary(out)

    polys = {}
    for i, r in enumerate(rooms):
        rid = r.get("id") or f"draft-{i}"
        try:
            polys[rid] = (r, to_polygon(r["polygon"], name=f"Room '{r['label']}'"))
        except GeometryError as exc:
            out.append(_check("invalid_shape", "error", f"{r['label']}: shape can't be used", exc.message,
                              "Redraw the room outline.", "rooms", [r.get("id")]))

    try:
        outline = to_polygon(boundary, name="Plan boundary") if boundary else None
    except GeometryError:
        outline = None
    rooms_union = unary_union([p for _, p in polys.values()]) if polys else None
    plan_area = (outline.area if outline is not None else (rooms_union.area if rooms_union else 0)) or 1

    # --- room labels and types ------------------------------------------------------------------
    for rid, (r, poly) in polys.items():
        label, rtype = r["label"].strip(), r.get("room_type") or "other"
        if GENERIC.match(label) or rtype == "other":
            out.append(_check("unclassified_room", "warning", f"'{label}' has no clear room type",
                              f"'{label}' is {'typed as Other' if rtype == 'other' else 'only a generic name'}; "
                              "rooms without a type are not scored.",
                              "Rename the room and pick its type (bedroom, toilet, store…).", "rooms", [r.get("id")]))
        else:
            inferred = infer_room_type(label)
            if inferred not in ("other", rtype) and (inferred, rtype) not in COMPATIBLE \
                    and (rtype, inferred) not in COMPATIBLE:
                out.append(_check("label_type_mismatch", "warning", f"'{label}' looks like a {ROOM_TYPES[inferred]}",
                                  f"The name suggests {ROOM_TYPES[inferred]}, but the type is {ROOM_TYPES.get(rtype, rtype)}. "
                                  "Rules use the type, not the name.",
                                  "Check which one is right and correct the other.", "rooms", [r.get("id")]))
        if r.get("source") == "ai" and r.get("confidence") is not None and r["confidence"] < LOW_CONFIDENCE:
            out.append(_check("low_confidence_room", "warning", f"'{label}' was a low-confidence AI guess",
                              f"The AI was {r['confidence']:.0%} sure about this room and it hasn't been edited.",
                              "Compare its outline and type with the drawing.", "rooms", [r.get("id")]))
        share = poly.area / plan_area
        if share < 0.004:
            out.append(_check("tiny_room", "warning", f"'{label}' is unusually small",
                              f"It covers {share:.1%} of the plan; it may be a stray click or a duct.",
                              "Delete it or redraw it at the right size.", "rooms", [r.get("id")]))
        elif share > 0.55 and rtype not in ("living", "other", "parking"):
            out.append(_check("huge_room", "warning", f"'{label}' covers most of the plan",
                              f"It covers {share:.0%} of the plan; rooms inside it may have been merged.",
                              "Split it into the real rooms.", "rooms", [r.get("id")]))
        if outline is not None:
            outside = poly.difference(outline).area / poly.area
            if outside > 0.15:
                out.append(_check("room_outside_outline", "warning", f"'{label}' sticks out of the outline",
                                  f"{outside:.0%} of the room is outside the plan outline.",
                                  "Adjust the room or the outline.", "rooms", [r.get("id")]))

    # --- overlaps -------------------------------------------------------------------------------
    items = list(polys.items())
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (_, (ra, pa)), (_, (rb, pb)) = items[i], items[j]
            inter = pa.intersection(pb).area
            if inter and inter / min(pa.area, pb.area) > 0.10:
                out.append(_check("overlapping_rooms", "error", f"'{ra['label']}' and '{rb['label']}' overlap",
                                  f"{inter / min(pa.area, pb.area):.0%} of the smaller room lies inside the other, "
                                  "so both would claim the same zone.",
                                  "Move the shared edge so the rooms only touch.", "rooms",
                                  [ra.get("id"), rb.get("id")]))

    # --- completeness ---------------------------------------------------------------------------
    if outline is not None and rooms_union is not None:
        covered = rooms_union.intersection(outline).area / outline.area
        if covered < 0.7:
            out.append(_check("incomplete_plan", "warning", "Part of the plan has no room",
                              f"Only {covered:.0%} of the outline is covered by rooms. Passages, balconies or a "
                              "room may be missing.",
                              "Add the missing spaces (use Foyer / passage or Balcony for circulation).", "outline"))
    types = [r.get("room_type") for r, _ in polys.values()]
    if (property_type or "") in RESIDENTIAL:
        for needed, name in (("kitchen", "kitchen"), ("toilet", "toilet or bathroom")):
            if needed not in types:
                out.append(_check(f"missing_{needed}", "warning", f"No {name} on the plan",
                                  f"A home usually has a {name}; the AI may have missed it or it may be typed wrongly.",
                                  f"Add the {name} or correct its type.", "rooms"))
    if types.count("master_bedroom") > 1:
        out.append(_check("several_master_bedrooms", "info", "More than one master bedroom",
                          "Several rooms are typed Master bedroom; rules for the principal bedroom apply to each.",
                          "Keep one master bedroom and type the rest as Bedroom if that's how they're used.", "rooms"))
    if detection:
        if detection.get("stairs") and "staircase" not in types:
            out.append(_check("stairs_missing", "warning", "Stairs were detected but aren't on the plan",
                              "The AI found a staircase that isn't among the verified rooms.",
                              "Add it as a Staircase if it exists.", "rooms"))
        detected = len(detection.get("rooms", []))
        if detected and len(rooms) < 0.6 * detected:
            out.append(_check("rooms_dropped", "info", "Several AI rooms were removed",
                              f"The AI found {detected} rooms; the plan now has {len(rooms)}.",
                              "That's fine if they were mistakes; otherwise re-add them.", "rooms"))

    # --- openings -------------------------------------------------------------------------------
    mains = [o for o in openings if o.get("is_main_entrance") and o.get("kind") == "door"]
    if not mains:
        out.append(_check("no_main_entrance", "warning", "Main entrance not marked",
                          "Entrance rules can't run until one door is marked as the main entrance.",
                          "Select the main door and tick 'Main entrance'.", "openings"))
    elif len(mains) > 1:
        out.append(_check("several_main_entrances", "error", "More than one main entrance",
                          f"{len(mains)} doors are marked as the main entrance.",
                          "Keep only the door people actually use to enter the home.", "openings",
                          [o.get("id") for o in mains]))
    edge = outline.exterior if outline is not None else (rooms_union.exterior if getattr(rooms_union, "exterior", None) else None)
    for o in mains:
        if edge is not None and edge.distance(SPoint(*o["position"])) > 0.04 * diag:
            out.append(_check("entrance_inside", "warning", "Main entrance is not on an outer wall",
                              "The door marked as the main entrance sits inside the plan, away from the outline.",
                              "Check that the right door is marked; usually it is on an outer wall.", "openings",
                              [o.get("id")]))
        if o.get("source") == "ai" and o.get("confidence") is not None and o["confidence"] < LOW_CONFIDENCE:
            out.append(_check("low_confidence_entrance", "warning", "Main entrance is an unconfirmed AI guess",
                              f"The AI was {o['confidence']:.0%} sure this is the main door.",
                              "Confirm or move it; entrance rules carry a lot of weight.", "openings", [o.get("id")]))
    if not any(o.get("kind") == "window" for o in openings):
        out.append(_check("no_windows", "info", "No windows marked",
                          "Window-direction rules will be skipped.", "Mark windows if the drawing shows them.",
                          "openings"))
    walls = [p.exterior for _, p in polys.values()]
    for o in openings:
        if o.get("kind") == "door" and walls and min(w.distance(SPoint(*o["position"])) for w in walls) > 0.03 * diag:
            out.append(_check("floating_door", "info", "A door isn't on any room wall",
                              "One door is far from every room edge, so its zone may be misleading.",
                              "Drag it onto the wall it belongs to.", "openings", [o.get("id")]))

    # --- North ----------------------------------------------------------------------------------
    if not north:
        out.append(_check("north_not_set", "info", "North not set yet",
                          "Zones depend entirely on North.", "Set North after confirming the plan.", "north"))
    else:
        if not north.get("confirmed"):
            out.append(_check("north_unconfirmed", "warning", "North is not confirmed",
                              "The North direction hasn't been confirmed.", "Confirm it on the North step.", "north"))
        elif abs(float(north.get("north_angle", 0)) % 360) < 0.01:
            out.append(_check("north_is_image_top", "info", "North is exactly the top of the image",
                              "That's right only if the drawing's North arrow points straight up. Many plans are "
                              "drawn rotated.",
                              "Check the North arrow on the drawing, or take a compass reading on site.", "north"))
    return _summary(out)


def _summary(checks: list[dict]) -> dict:
    order = {"error": 0, "warning": 1, "info": 2}
    checks.sort(key=lambda c: order[c["severity"]])
    counts = {k: sum(1 for c in checks if c["severity"] == k) for k in order}
    return {"checks": checks, "counts": counts, "ok": counts["error"] == 0}
