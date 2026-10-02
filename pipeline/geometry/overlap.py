"""Detect overlapping room footprints after stitch (QA)."""

from __future__ import annotations

from shapely.geometry import box


def room_bbox_polygon(room: dict):
    pts = [p for w in room.get("walls", []) for p in w.get("polyline_m", [])]
    if not pts:
        return None
    tx, _, tz = room["pose_world"]["translation_m"]
    xs = [p[0] + tx for p in pts]
    zs = [p[1] + tz for p in pts]
    return box(min(xs), min(zs), max(xs), max(zs))


def pairwise_overlap_m2(rooms: list[dict]) -> float:
    """Substantial overlap only (shared wall touch ≠ failure)."""
    polys = [room_bbox_polygon(r) for r in rooms]
    polys = [p for p in polys if p is not None]
    total = 0.0
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            inter = polys[i].intersection(polys[j])
            if inter.area <= 0.05:
                continue
            smaller = min(polys[i].area, polys[j].area)
            if smaller > 0 and inter.area / smaller > 0.15:
                total += inter.area
    return float(total)
