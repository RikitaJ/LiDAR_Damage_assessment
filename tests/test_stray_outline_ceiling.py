"""Fix-loop regression: furnished rooms keep their wall outline; an unseen ceiling is not clamped."""

import numpy as np

from pipeline.geometry.stray_room import room_from_point_cloud


def _furnished_room(width=4.0, depth=5.0, ceiling=2.8, wall_top=None, step=0.05):
    """Walls all round, a ceiling, and only a strip of visible floor (furniture hides the rest)."""
    top = ceiling if wall_top is None else wall_top
    hs = np.arange(0.05, top, step)
    pts = []
    for x in np.arange(0, width, step):
        pts += [(x, h, 0.0) for h in hs] + [(x, h, depth) for h in hs]
    for z in np.arange(0, depth, step):
        pts += [(0.0, h, z) for h in hs] + [(width, h, z) for h in hs]
    pts += [(x, 0.0, z) for x in np.arange(1.6, 2.4, 0.02) for z in np.arange(0.2, 4.8, 0.02)]
    if wall_top is None:
        pts += [(x, ceiling, z) for x in np.arange(0.5, 3.5, 0.05) for z in np.arange(0.5, 4.5, 0.05)]
    path = np.array([(x, 1.4, z) for x, z in [(1.0, 1.0), (3.0, 1.0), (3.0, 4.0), (1.0, 4.0), (1.0, 1.0)]])
    return np.array(pts), path


def _lengths(room):
    return sorted(round(w["length_m"]["value"], 2) for w in room["walls"])


def test_floor_strip_falls_back_to_wall_outline():
    pts, path = _furnished_room()
    room, warnings = room_from_point_cloud(pts, "R1", "r", scale_sigma_rel=0.01, camera_positions=path)
    assert room["floor_area_m2"]["confidence"]["notes"] == "stray_wall_band_box"
    assert _lengths(room) == [4.0, 4.0, 5.0, 5.0]
    assert any("does not enclose the camera path" in w for w in warnings)


def test_observed_ceiling_is_measured_not_clamped():
    pts, path = _furnished_room(ceiling=2.1)
    room, _ = room_from_point_cloud(pts, "R1", "r", scale_sigma_rel=0.01, camera_positions=path)
    ceiling = room["ceiling_height_m"]
    assert ceiling["confidence"]["notes"] == "stray_depth_planes"
    assert abs(ceiling["value"] - 2.1) < 0.06


def test_unseen_ceiling_reports_prior_with_wide_interval():
    pts, path = _furnished_room(wall_top=1.7)
    room, warnings = room_from_point_cloud(pts, "R1", "r", scale_sigma_rel=0.01, camera_positions=path)
    ceiling = room["ceiling_height_m"]
    assert ceiling["confidence"]["notes"] == "ceiling_not_observed_prior"
    assert ceiling["lo"] <= 2.4 and ceiling["hi"] >= 3.2
    assert any("ceiling not observed" in w for w in warnings)


def test_points_beyond_reach_do_not_inflate_outline():
    pts, path = _furnished_room()
    seen_through = np.array([(x, 1.2, 9.0) for x in np.arange(0, 4, 0.05)])
    room, _ = room_from_point_cloud(np.vstack([pts, seen_through]), "R1", "r", scale_sigma_rel=0.01,
                                    camera_positions=path)
    assert _lengths(room) == [4.0, 4.0, 5.0, 5.0]
