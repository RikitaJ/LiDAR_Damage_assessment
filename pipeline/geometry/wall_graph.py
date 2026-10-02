"""Snap wall endpoints and build floor polygons (rectangles + L-shapes)."""

from __future__ import annotations

from shapely.geometry import LineString, Point
from shapely.ops import polygonize, snap, unary_union

SNAP_M = 0.08


def polygon_area_from_walls(walls: list[dict]) -> float:
    lines = _wall_lines(walls)
    if not lines:
        return 0.0
    merged = unary_union(lines)
    snapped = snap(merged, merged, SNAP_M)
    polys = list(polygonize(snapped))
    if polys:
        return float(max(polys, key=lambda p: p.area).area)
    return 0.0


def _wall_lines(walls: list[dict]) -> list[LineString]:
    out: list[LineString] = []
    for w in walls:
        pl = w.get("polyline_m") or []
        if len(pl) >= 2:
            out.append(LineString([(float(pl[0][0]), float(pl[0][1])), (float(pl[1][0]), float(pl[1][1]))]))
    return out
