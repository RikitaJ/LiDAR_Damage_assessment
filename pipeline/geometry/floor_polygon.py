from __future__ import annotations

from shapely.geometry import LineString, box
from shapely.ops import polygonize, unary_union


def floor_area_m2(walls: list[dict]) -> float:
    lines = [
        LineString([(p[0], p[1]) for p in w["polyline_m"]])
        for w in walls
        if len(w.get("polyline_m", [])) >= 2
    ]
    if not lines:
        return 0.0
    polys = list(polygonize(unary_union(lines)))
    if polys:
        return float(max(polys, key=lambda x: x.area).area)
    return _bbox_area(walls)


def stitched_footprint_area_m2(rooms: list[dict]) -> float:
    """Union of per-room world footprints (multi-room; avoids max-single-polygon bug)."""
    parts = []
    for r in rooms:
        tx, _, tz = r["pose_world"]["translation_m"]
        pts: list[tuple[float, float]] = []
        for w in r.get("walls", []):
            for p in w.get("polyline_m") or []:
                pts.append((float(p[0]) + tx, float(p[1]) + tz))
        if len(pts) < 2:
            continue
        xs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        parts.append(box(min(xs), min(zs), max(xs), max(zs)))
    if not parts:
        return 0.0
    if len(parts) == 1:
        return float(parts[0].area)
    return float(unary_union(parts).area)


def _bbox_area(walls: list[dict]) -> float:
    """Fallback when wall segments do not polygonize (gap at corners). RoomPlan scans."""
    pts = [p for w in walls for p in w.get("polyline_m", [])]
    if len(pts) < 2:
        return 0.0
    xs = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    w = max(xs) - min(xs)
    h = max(zs) - min(zs)
    return float(w * h) if w > 0 and h > 0 else 0.0
