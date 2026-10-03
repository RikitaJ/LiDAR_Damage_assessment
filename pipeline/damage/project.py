"""Surface UV placement, multi-frame merge, opening-corner cues (Phase 5 accuracy)."""

from __future__ import annotations

import math
from pathlib import Path

from pipeline.config import InputTier, SIGMA
from pipeline.measure.intervals import with_interval


def room_for_image(capture_root: Path, image_path: Path, rooms: list[dict]) -> dict | None:
    try:
        resolved = image_path.resolve()
    except OSError:
        resolved = image_path
    for room in rooms:
        photos = (capture_root / "rooms" / room["room_id"] / "photos").resolve()
        if photos in resolved.parents or resolved.parent == photos:
            return room
    if len(rooms) == 1:
        return rooms[0]
    return None


def pick_wall_id(room: dict, *, cls: str, hit: dict | None = None) -> str | None:
    hit = hit or {}
    if hit.get("surface_type") == "ceiling":
        return f"{room['room_id']}-ceiling"
    walls = room.get("walls") or []
    if not walls:
        return None
    idx = wall_index_from_image_x(hit.get("u_center_frac"), len(walls))
    src = hit.get("source", "")
    if idx is not None and (str(src).endswith("_v2") or "azure_damage" in str(src)):
        return walls[idx]["id"]
    if cls == "water_stain" and not hit.get("u0_frac"):
        for w in walls:
            for op in w.get("openings") or []:
                if op.get("kind") == "door":
                    return w["id"]
    if cls == "crack" and hit.get("diagonal_from_opening"):
        for w in walls:
            for op in w.get("openings") or []:
                if op.get("kind") in ("door", "window"):
                    return w["id"]
    if idx is not None:
        return walls[idx]["id"]
    return max(walls, key=lambda w: float(w.get("length_m", {}).get("value_m", 0)))["id"]


def wall_index_from_image_x(x_frac: float | None, n_walls: int) -> int | None:
    if x_frac is None or n_walls <= 0:
        return None
    try:
        x = max(0.0, min(0.999, float(x_frac)))
    except (TypeError, ValueError):
        return None
    return min(int(x * n_walls), n_walls - 1)


def wall_length_m(room: dict, wall_id: str) -> float:
    for w in room.get("walls") or []:
        if w["id"] == wall_id:
            return max(float(w.get("length_m", {}).get("value_m", 3.0)), 0.5)
    return 3.0


def hit_to_region(
    hit: dict,
    room: dict,
    tier: InputTier,
    region_id: str,
) -> dict | None:
    cls = hit.get("class") or "water_stain"
    wall_id = pick_wall_id(room, cls=cls, hit=hit)
    if not wall_id:
        return None
    is_ceiling = hit.get("surface_type") == "ceiling" or wall_id.endswith("-ceiling")
    try:
        wl = wall_length_m(room, wall_id) if not is_ceiling else max(
            float(room.get("floor_area_m2", {}).get("value_m", 9)) ** 0.5, 2.0
        )
        ceil_m = float(room.get("ceiling_height_m", {}).get("value_m", 2.5))
        if math.isnan(ceil_m) or ceil_m <= 0:
            ceil_m = 2.5
        u0f, u1f = hit.get("u0_frac"), hit.get("u1_frac")
        if u0f is not None and u1f is not None:
            u0 = max(0.0, float(u0f)) * wl * 0.92
            u1 = min(wl, max(float(u1f) * wl * 0.92, u0 + 0.08))
            w = u1 - u0
        else:
            u_frac = max(0.05, min(0.92, float(hit.get("u_center_frac", 0.35))))
            u0 = u_frac * wl * 0.85
            area_tmp = max(float(hit.get("area_m2", 0.1)), 0.04)
            w = min((area_tmp**0.5) * 1.15, wl * 0.45)
        h = min((max(float(hit.get("area_m2", 0.1)), 0.04) ** 0.5) * 0.85, (ceil_m * 0.55 if not is_ceiling else wl * 0.35))
        area = max(w * h, 0.04)
        bottom_m = float(hit.get("bottom_above_floor_m", 0.15))
        if is_ceiling:
            bottom_m = 0.05
            h = min(h, wl * 0.4)
        else:
            bottom_m = max(0.05, min(bottom_m, max(ceil_m - h - 0.05, 0.05)))
        score = float(hit.get("score", 0.45))
        source = str(hit.get("source", "damage_detect_v3"))
    except (TypeError, ValueError):
        return None
    sig = max(area * 0.26, SIGMA[tier].footprint_rel)
    if score >= 0.65:
        sig *= 0.82
    elif score >= 0.58:
        sig *= 0.9
    poly = [
        [u0, bottom_m],
        [u0 + w, bottom_m],
        [u0 + w, bottom_m + h],
        [u0, bottom_m + h],
    ]
    out = {
        "id": region_id,
        "surface_id": wall_id,
        "class": cls,
        "polygon_surface": poly,
        "area_m2": with_interval(area, sig, notes=source, tier=tier, kind="footprint"),
        "width_m": with_interval(w, sig, notes=source, tier=tier, kind="wall"),
        "height_m": with_interval(h, sig * 0.9, notes=source, tier=tier, kind="height"),
        "bottom_above_floor_m": with_interval(bottom_m, 0.07, notes=source, tier=tier, kind="height"),
        "score": score,
        "source": source,
        "view_count": int(hit.get("view_count", 1)),
    }
    if hit.get("diagonal_from_opening"):
        out["diagonal_from_opening"] = True
    return out


def merge_regions_on_surface(regions: list[dict], tier: InputTier) -> list[dict]:
    """Merge overlapping UV boxes on the same surface + class."""
    if len(regions) < 2:
        return regions
    buckets: dict[tuple[str, str], list[dict]] = {}
    for r in regions:
        key = (r.get("surface_id", ""), r.get("class", ""))
        buckets.setdefault(key, []).append(r)

    out: list[dict] = []
    seq = 0
    for (_sid, _cls), group in buckets.items():
        merged = _merge_group(group, tier)
        for m in merged:
            seq += 1
            m["id"] = f"D{seq}"
            out.append(m)
    return out


def fuse_vision_with_regions(regions: list[dict], tags: list[str], room: dict, tier: InputTier) -> list[dict]:
    if not tags:
        return regions
    out = list(regions)
    for tag in tags:
        cls = "crack" if tag == "crack" else "water_stain" if tag in ("stain", "damage", "peeling", "rust") else "mold" if tag == "mold" else ""
        if not cls:
            continue
        wall_id = pick_wall_id(room, cls=cls)
        if not wall_id:
            continue
        if _tag_overlaps_existing(out, wall_id, cls):
            for r in out:
                if r.get("surface_id") == wall_id and r.get("class") == cls:
                    r["score"] = min(0.95, float(r.get("score", 0.5)) + 0.15)
                    notes = str(r.get("source", ""))
                    if "vision_fused" not in notes:
                        r["source"] = notes + "+vision_fused"
            continue
        hit = {
            "class": cls,
            "u_center_frac": 0.4,
            "area_m2": 0.09,
            "bottom_above_floor_m": 0.18 if cls == "water_stain" else 1.1,
            "score": 0.58,
            "source": "azure_vision_optional",
        }
        reg = hit_to_region(hit, room, tier, f"D{len(out) + 1}")
        if reg:
            out.append(reg)
    return out


def annotate_opening_geometry(regions: list[dict], rooms: list[dict]) -> None:
    """Set diagonal_from_opening for cracks near a door/window corner (CD-05)."""
    by_wall: dict[str, dict] = {}
    for room in rooms:
        for w in room.get("walls") or []:
            by_wall[w["id"]] = w

    for reg in regions:
        if reg.get("class") != "crack":
            continue
        wall = by_wall.get(reg.get("surface_id", ""))
        if not wall:
            continue
        wl = wall_length_m({"walls": [wall]}, wall["id"])
        u0 = float((reg.get("polygon_surface") or [[0, 0]])[0][0])
        for op in wall.get("openings") or []:
            if op.get("kind") not in ("door", "window"):
                continue
            ou = _opening_center_u(wall, op, wl)
            if ou is None:
                continue
            half = float(op.get("width_m", {}).get("value_m", 0.9)) / 2.0
            if abs(u0 - (ou - half)) < 0.55 or abs(u0 - (ou + half)) < 0.55:
                reg["diagonal_from_opening"] = True
                break


def _opening_center_u(wall: dict, op: dict, wall_len: float) -> float | None:
    anchor = op.get("anchor_m")
    pl = wall.get("polyline_m") or []
    if anchor and len(pl) >= 2:
        import numpy as np

        p0 = np.array(pl[0], float)
        p1 = np.array(pl[1], float)
        a = np.array(anchor[:2], float)
        u = p1 - p0
        length = float(np.linalg.norm(u))
        if length > 1e-6:
            return float(np.dot(a - p0, u / length))
    off = op.get("offset_m")
    if isinstance(off, dict):
        try:
            return float(off.get("value_m", off.get("value")))
        except (TypeError, ValueError):
            pass
    return wall_len * 0.5


def _tag_overlaps_existing(regions: list[dict], wall_id: str, cls: str) -> bool:
    return any(r.get("surface_id") == wall_id and r.get("class") == cls for r in regions)


def _merge_group(group: list[dict], tier: InputTier) -> list[dict]:
    if len(group) == 1:
        return group
    used = [False] * len(group)
    merged: list[dict] = []
    for i, a in enumerate(group):
        if used[i]:
            continue
        box = _uv_box(a)
        cluster = [a]
        used[i] = True
        for j, b in enumerate(group[i + 1 :], start=i + 1):
            if used[j]:
                continue
            if _iou(box, _uv_box(b)) >= 0.2:
                cluster.append(b)
                used[j] = True
                box = _union_box(box, _uv_box(b))
        merged.append(_combine_cluster(cluster, tier))
    return merged


def _uv_box(reg: dict) -> tuple[float, float, float, float]:
    poly = reg.get("polygon_surface") or [[0, 0], [0.2, 0], [0.2, 0.2], [0, 0.2]]
    us = [float(p[0]) for p in poly]
    vs = [float(p[1]) for p in poly]
    return min(us), min(vs), max(us), max(vs)


def _union_box(a: tuple[float, float, float, float], b: tuple[float, float, float, float]):
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _combine_cluster(cluster: list[dict], tier: InputTier) -> dict:
    base = dict(cluster[0])
    box = _uv_box(cluster[0])
    for c in cluster[1:]:
        box = _union_box(box, _uv_box(c))
    u0, v0, u1, v1 = box
    w = max(u1 - u0, 0.08)
    h = max(v1 - v0, 0.08)
    area = w * h
    base["polygon_surface"] = [[u0, v0], [u1, v0], [u1, v1], [u0, v1]]
    src = str(base.get("source", "damage_merge_v2"))
    sig = max(area * 0.22, 0.06)
    base["view_count"] = sum(int(c.get("view_count", 1)) for c in cluster)
    if len(cluster) > 1:
        src = src.split("+")[0] + "+merge_v2"
        base["score"] = min(0.92, max(float(c.get("score", 0.4)) for c in cluster) + 0.08)
    base["source"] = src
    base["area_m2"] = with_interval(area, sig, notes=src, tier=tier, kind="footprint")
    base["width_m"] = with_interval(w, sig, notes=src, tier=tier, kind="wall")
    base["height_m"] = with_interval(h, sig, notes=src, tier=tier, kind="height")
    base["bottom_above_floor_m"] = with_interval(v0, 0.06, notes=src, tier=tier, kind="height")
    return base
