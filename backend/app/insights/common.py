"""Shared helpers for the insight tools."""
import json
import math
from functools import lru_cache
from pathlib import Path

from shapely.geometry import Point as SPoint
from shapely.geometry import Polygon, box
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.geometry.engine import OpeningInput, PlanInput, RoomInput, compute_zones
from app.geometry.primitives import rotate_points, to_polygon
from app.models import Analysis, FloorPlan, Project
from app.remedies.engine import attach_remedies
from app.scoring.engine import DEFAULT_SCORING, score
from app.vastu.engine import evaluate

DATA = Path(__file__).parent / "data"
LEVELS = ("none", "low", "medium", "high")


@lru_cache
def load_data(name: str) -> dict:
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def latest_analysis(project: Project) -> Analysis:
    if not project.analyses:
        raise AppError("no_analysis", "This project has not been analysed yet.", 404,
                       "Verify the plan, set North and run the analysis.")
    return project.analyses[-1]


def is_stale(project: Project, analysis: Analysis) -> bool:
    """True when the plan or North changed after this analysis (the UI shows the same warning)."""
    fp = project.floor_plans[-1] if project.floor_plans else None
    return fp is None or fp.id != analysis.floor_plan_id or fp.status != "analyzed"


# --- remedy practical metadata ------------------------------------------------------------------
def remedy_fit(remedy: dict | None) -> dict:
    """Everyday / structural option metadata for a remedy snapshot (see data/remedy_fit.json)."""
    doc = load_data("remedy_fit")
    entry = doc["remedies"].get((remedy or {}).get("code") or "", {})
    everyday = {**doc["defaults"]["everyday"], **entry.get("everyday", {})}
    if (remedy or {}).get("kind") == "structural" and "everyday" not in entry:
        everyday = {**doc["defaults"]["structural"]}
    if (remedy or {}).get("kind") == "optional" and "everyday" not in entry:
        everyday = {**everyday, "cost_band": "none"}
    structural = None
    if remedy and remedy.get("structural_note"):
        structural = {**doc["defaults"]["structural"], **entry.get("structural", {})}
    if remedy and not remedy.get("approved", True):
        # Placeholder remedy (no approved catalogue entry): the only step is to consult an expert.
        everyday = {"cost_band": "low", "requires": ["expert"], "disruption": "none"}
    return {"everyday": everyday, "structural": structural}


# --- simulation ---------------------------------------------------------------------------------
def plan_input_from_snapshot(snapshot: dict, room_types: dict[str, str] | None = None) -> PlanInput:
    room_types = room_types or {}
    return PlanInput(
        boundary=snapshot["boundary"],
        rooms=[RoomInput(r["id"], r["label"], room_types.get(r["id"], r["room_type"]), r["polygon"])
               for r in snapshot["rooms"]],
        openings=[OpeningInput(o["id"], o["kind"], o["is_main_entrance"], o["position"])
                  for o in snapshot.get("openings", [])],
    )


def simulate(plan: PlanInput, north_angle: float, system: str, rules, catalogue, cfg: dict | None) -> dict:
    """Run zones -> rules -> remedies -> score in memory. Nothing is stored."""
    zr = compute_zones(plan, north_angle, system)
    findings = attach_remedies(evaluate(zr, rules), catalogue)
    scored = score(findings, cfg or DEFAULT_SCORING)
    return {"zr": zr, "findings": findings, "overall": scored["overall"],
            "category_scores": scored["category_scores"], "counts": scored["counts"]}


# --- score arithmetic ---------------------------------------------------------------------------
def points_for(status: str, severity: str, cfg: dict) -> float | None:
    if status in cfg["status_points"]:
        return float(cfg["status_points"][status])
    if status == "issue":
        return float(cfg["issue_points"].get(severity, 0.0))
    return None


def overall_from(findings: list[dict], cfg: dict, weight_of=None) -> tuple[float | None, dict]:
    """Overall score from finding dicts (status, severity, weight, category), unrounded.
    `weight_of(f)` can scale a finding's weight (Family Priority Mode)."""
    cats: dict[str, list[float]] = {}
    for f in findings:
        pts = points_for(f["status"], f["severity"], cfg)
        w = (f.get("weight") or 0) * (weight_of(f) if weight_of else 1.0)
        if pts is None or w <= 0:
            continue
        c = cats.setdefault(f["category"], [0.0, 0.0])
        c[0] += w * pts
        c[1] += w
    weighted = total = 0.0
    cat_scores = {}
    for code, (earned, possible) in cats.items():
        value = 100 * earned / possible if possible else None
        cat_scores[code] = value
        cw = float(cfg["category_weights"].get(code, 0.0))
        if value is not None and cw > 0:
            weighted += value * cw
            total += cw
    return (weighted / total if total else None), cat_scores


def scoring_cfg(analysis: Analysis) -> dict:
    cfg = dict(DEFAULT_SCORING)
    cfg.update((analysis.score_breakdown or {}).get("config") or {})
    return cfg


# --- room geometry ------------------------------------------------------------------------------
GRID = [["NW", "N", "NE"], ["W", "C", "E"], ["SW", "S", "SE"]]


def north_up(points: list, centre, north_angle: float) -> list:
    return rotate_points(points, tuple(centre), -north_angle)


def room_cells(room_polygon: list, centre, north_angle: float) -> tuple[Polygon, dict[str, Polygon]]:
    """The room in the North-up frame and its own 3x3 grid (corner code -> cell)."""
    up = to_polygon(north_up(room_polygon, centre, north_angle), name="Room")
    minx, miny, maxx, maxy = up.bounds
    w, h = (maxx - minx) / 3, (maxy - miny) / 3
    cells = {code: box(minx + c * w, miny + r * h, minx + (c + 1) * w, miny + (r + 1) * h)
             for r, row in enumerate(GRID) for c, code in enumerate(row)}
    return up, cells


def openings_in_cell(cell: Polygon, room_up: Polygon, openings: list[dict], centre, north_angle: float,
                     tolerance: float) -> list[dict]:
    """Openings on or near the room's walls that fall inside a room grid cell."""
    out = []
    for o in openings:
        (px, py), = north_up([o["position"]], centre, north_angle)
        pt = SPoint(px, py)
        if room_up.exterior.distance(pt) <= tolerance and cell.buffer(tolerance).covers(pt):
            out.append(o)
    return out


def ft_per_px(fp: FloorPlan, built_up_area_sqft: float | None) -> float | None:
    """Scale from the customer's built-up area and the verified outline. None when unknown."""
    if not built_up_area_sqft or not fp.boundary:
        return None
    try:
        area_px = to_polygon(fp.boundary, name="Plan boundary").area
    except Exception:  # noqa: BLE001
        return None
    return math.sqrt(built_up_area_sqft / area_px) if area_px else None


def angle_diff(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def get_owned_context(db: Session, project: Project) -> tuple[Analysis, FloorPlan]:
    analysis = latest_analysis(project)
    fp = db.get(FloorPlan, analysis.floor_plan_id)
    return analysis, fp
