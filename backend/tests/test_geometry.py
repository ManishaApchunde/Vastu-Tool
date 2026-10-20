import pytest

from app.geometry.engine import (
    OpeningInput, PlanInput, RoomInput, boundary_from_rooms, compute_centre, compute_zones,
)
from app.geometry.primitives import GeometryError, bearing_from, direction_8, rotate_point

SQUARE = [[0, 0], [300, 0], [300, 300], [0, 300]]


def plan(rooms, openings=()):
    return PlanInput(SQUARE, [RoomInput(i, i, t, p) for i, t, p in rooms],
                     [OpeningInput(i, k, m, p) for i, k, m, p in openings])


def test_centre_of_rectangle():
    assert compute_centre([[0, 0], [400, 0], [400, 200], [0, 200]]) == (200, 100)


def test_centre_of_l_shape_is_area_weighted():
    cx, cy = compute_centre([[0, 0], [200, 0], [200, 100], [100, 100], [100, 200], [0, 200]])
    assert cx == pytest.approx(83.33, abs=0.01) and cy == pytest.approx(83.33, abs=0.01)


def test_rotation_clockwise_in_screen_coords():
    x, y = rotate_point((1, 0), (0, 0), 90)  # right -> down
    assert (round(x, 6), round(y, 6)) == (0, 1)


def test_bearing_and_direction():
    assert direction_8(bearing_from((0, 0), (0, -10))) == "N"
    assert direction_8(bearing_from((0, 0), (10, 0))) == "E"
    assert direction_8(bearing_from((0, 0), (-10, 10))) == "SW"


@pytest.mark.parametrize("north,expected", [(0, "SE"), (90, "NE"), (180, "NW"), (270, "SW")])
def test_zone_follows_north(north, expected):
    zr = compute_zones(plan([("k", "kitchen", [[200, 200], [300, 200], [300, 300], [200, 300]])]), north)
    assert zr.rooms[0].primary_zone == expected


def test_grid_has_nine_full_zones_for_rectangle():
    zr = compute_zones(plan([("a", "living", SQUARE)]), 0)
    assert sorted(z.code for z in zr.zones) == sorted(["N", "NE", "E", "SE", "S", "SW", "W", "NW", "C"])
    assert all(z.coverage == pytest.approx(1.0) for z in zr.zones)
    assert zr.rooms[0].overlaps["C"] == pytest.approx(1 / 9, abs=1e-3)


def test_cut_corner_reduces_coverage():
    boundary = [[0, 0], [200, 0], [200, 100], [300, 100], [300, 300], [0, 300]]  # NE corner cut
    zr = compute_zones(PlanInput(boundary, [RoomInput("a", "a", "living", [[0, 0], [100, 0], [100, 100], [0, 100]])]), 0)
    assert zr.zone_coverage("NE") < 0.6


def test_opening_zone():
    zr = compute_zones(plan([("a", "living", SQUARE)], [("d", "door", True, [150, 0])]), 0)
    assert zr.openings[0].zone == "N"


def test_invalid_geometry_raises():
    with pytest.raises(GeometryError):
        compute_zones(PlanInput([[0, 0], [1, 1]], [RoomInput("a", "a", "x", SQUARE)]), 0)
    with pytest.raises(GeometryError):
        compute_zones(PlanInput(SQUARE, []), 0)


def test_boundary_from_rooms():
    b = boundary_from_rooms([[[0, 0], [100, 0], [100, 100], [0, 100]], [[100, 0], [200, 0], [200, 100], [100, 100]]])
    assert compute_centre(b) == (100, 50)
