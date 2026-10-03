"""Stray depth point cloud → single-room walls, ceiling, openings (Manhattan v1)."""

from __future__ import annotations

from typing import Any

import numpy as np
from shapely.geometry import MultiPoint

from pipeline.config import InputTier, SIGMA
from pipeline.geometry.floor_footprint import (
    ceiling_height_from_planes,
    fit_floor_plane,
    floor_slice_xz,
    footprint_from_floor_xz,
)
from pipeline.measure.confidence import area_m2, m
from pipeline.measure.intervals import with_interval


def room_from_point_cloud(
    pts: np.ndarray,
    room_id: str,
    name: str,
    *,
    scale_sigma_rel: float,
    rng: np.random.Generator | None = None,
    tier: InputTier = InputTier.LIDAR,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    gen = rng if rng is not None else np.random.default_rng(0)

    floor_n, floor_d = fit_floor_plane(pts, gen)
    floor_xz = floor_slice_xz(pts, floor_n, floor_d)
    ceiling_h = ceiling_height_from_planes(pts, floor_n, floor_d)

    floor_y = float(np.median(pts[np.abs(pts @ floor_n - floor_d) <= 0.06, 1]))
    if not np.isfinite(floor_y):
        floor_y = float(np.percentile(pts[:, 1], 4))

    wall_band = pts[(pts[:, 1] > floor_y + 0.35) & (pts[:, 1] < floor_y + ceiling_h - 0.2)]
    xz_walls = wall_band[:, [0, 2]] if len(wall_band) >= 200 else floor_xz

    corners, area_val, fp_warn = footprint_from_floor_xz(floor_xz, rng=gen)
    warnings.extend(fp_warn)

    if len(xz_walls) < 80:
        warnings.append("too few wall-band points; widening intervals")
        sig_extra = 2.0
    else:
        sig_extra = 1.0

    walls, open_warn = _walls_with_openings(corners, room_id, tier, xz_walls, floor_y, scale_sigma_rel)
    warnings.extend(open_warn)

    xs = [c[0] for c in corners]
    zs = [c[1] for c in corners]
    cx, cz = float(np.mean(xs)), float(np.mean(zs))

    sig_area = max(
        area_val * SIGMA[tier].footprint_rel * sig_extra,
        area_val * scale_sigma_rel * 2,
    )
    sig_h = max(SIGMA[tier].height_m, ceiling_h * scale_sigma_rel)

    return (
        {
            "room_id": room_id,
            "name": name,
            "floor_area_m2": with_interval(
                area_val, sig_area, notes="stray_floor_occupancy", tier=tier, kind="footprint"
            ),
            "ceiling_height_m": with_interval(
                ceiling_h, sig_h, notes="stray_depth_planes", tier=tier, kind="height"
            ),
            "walls": walls,
            "pose_world": {"translation_m": [cx, 0.0, cz], "rotation_quat": [0.0, 0.0, 0.0, 1.0]},
            "_orphan_openings": [],
        },
        warnings,
    )


def _manhattan_corners(xz: np.ndarray) -> list[list[float]] | None:
    try:
        mp = MultiPoint([(float(x), float(z)) for x, z in xz])
        hull = mp.convex_hull
        if hull.is_empty or hull.area < 0.8:
            return None
        rect = hull.minimum_rotated_rectangle
        coords = list(rect.exterior.coords)
        if len(coords) < 4:
            return None
        raw = [[float(coords[i][0]), float(coords[i][1])] for i in range(4)]
        return _snap_to_manhattan(raw)
    except Exception:
        return None


def _snap_to_manhattan(corners: list[list[float]]) -> list[list[float]]:
    xs = [c[0] for c in corners]
    zs = [c[1] for c in corners]
    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)
    return [
        [min_x, min_z],
        [max_x, min_z],
        [max_x, max_z],
        [min_x, max_z],
    ]


def _axis_bbox_corners(xz: np.ndarray) -> list[list[float]]:
    xs, zs = xz[:, 0], xz[:, 1]
    return [
        [float(xs.min()), float(zs.min())],
        [float(xs.max()), float(zs.min())],
        [float(xs.max()), float(zs.max())],
        [float(xs.min()), float(zs.max())],
    ]


def _walls_with_openings(
    corners: list[list[float]],
    room_id: str,
    tier: InputTier,
    xz: np.ndarray,
    floor_y: float,
    scale_sigma_rel: float,
) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    walls: list[dict] = []
    sigma_len = max(SIGMA[tier].length_m, 0.02 + scale_sigma_rel * 0.5)

    for i in range(4):
        a = corners[i]
        b = corners[(i + 1) % 4]
        length = float(np.hypot(b[0] - a[0], b[1] - a[1]))
        length = max(length, 0.1)
        openings = _detect_openings_on_wall(a, b, xz, floor_y, room_id, i, tier, sigma_len)
        walls.append(
            {
                "id": f"{room_id}-W{i + 1}",
                "length_m": with_interval(
                    length, sigma_len, notes="stray_wall", tier=tier, kind="wall"
                ),
                "polyline_m": [a, b],
                "openings": openings,
            }
        )
    if not any(w["openings"] for w in walls):
        warnings.append("no door/window gaps detected in depth (may be normal for empty room)")
    return walls, warnings


def _detect_openings_on_wall(
    a: list[float],
    b: list[float],
    xz: np.ndarray,
    floor_y: float,
    room_id: str,
    wall_idx: int,
    tier: InputTier,
    sigma_len: float,
) -> list[dict]:
    ab = np.array(b, float) - np.array(a, float)
    length = float(np.linalg.norm(ab))
    if length < 0.5:
        return []
    u = ab / length
    # Points near this wall segment in 2D
    ap = np.array(a, float)
    rel = xz - ap
    t = rel @ u
    perp = np.linalg.norm(rel - np.outer(t, u), axis=1)
    on_wall = (t >= 0.05) & (t <= length - 0.05) & (perp < 0.35)
    if not np.any(on_wall):
        return []

    bin_w = 0.08
    bins = max(1, int(length / bin_w))
    counts = np.zeros(bins, dtype=int)
    t_on = t[on_wall]
    for tv in t_on:
        bi = min(bins - 1, int(tv / length * bins))
        counts[bi] += 1

    thresh = max(3, int(np.percentile(counts, 25)))
    openings: list[dict] = []
    gap_start: int | None = None
    for bi in range(bins):
        if counts[bi] <= thresh:
            if gap_start is None:
                gap_start = bi
        else:
            if gap_start is not None:
                _maybe_add_opening(gap_start, bi, bins, length, ap, u, room_id, wall_idx, tier, sigma_len, openings)
                gap_start = None
    if gap_start is not None:
        _maybe_add_opening(gap_start, bins, bins, length, ap, u, room_id, wall_idx, tier, sigma_len, openings)
    return openings


def _maybe_add_opening(
    g0: int,
    g1: int,
    bins: int,
    length: float,
    ap: np.ndarray,
    u: np.ndarray,
    room_id: str,
    wall_idx: int,
    tier: InputTier,
    sigma_len: float,
    out: list[dict],
) -> None:
    width = (g1 - g0) / bins * length
    if width < 0.65:
        return
    center_t = (g0 + g1) / 2 / bins * length
    center = ap + u * center_t
    sig_w = max(SIGMA[tier].opening_m, width * 0.08)
    out.append(
        {
            "id": f"{room_id}-O{wall_idx + 1}{g0}",
            "kind": "door" if width >= 0.7 else "opening",
            "width_m": with_interval(width, sig_w, notes="stray_gap", tier=tier, kind="opening"),
            "height_m": m(2.05, tier, "height"),
            "wall_id": f"{room_id}-W{wall_idx + 1}",
            "anchor_m": [float(center[0]), float(center[1])],
        }
    )


def _fallback_bbox(
    pts: np.ndarray,
    room_id: str,
    name: str,
    tier: InputTier,
    ceiling_h: float,
    scale_sigma_rel: float,
    warnings: list[str],
) -> tuple[dict[str, Any], list[str]]:
    corners = _axis_bbox_corners(pts[:, [0, 2]])
    walls, _ = _walls_with_openings(corners, room_id, tier, pts[:, [0, 2]], float(np.percentile(pts[:, 1], 4)), scale_sigma_rel)
    xs = [c[0] for c in corners]
    zs = [c[1] for c in corners]
    area_val = max((max(xs) - min(xs)) * (max(zs) - min(zs)), 0.5)
    return (
        {
            "room_id": room_id,
            "name": name,
            "floor_area_m2": area_m2(area_val, tier),
            "ceiling_height_m": with_interval(ceiling_h, SIGMA[tier].height_m * 2, notes="fallback"),
            "walls": walls,
            "pose_world": {"translation_m": [float(np.mean(xs)), 0.0, float(np.mean(zs))], "rotation_quat": [0, 0, 0, 1]},
            "_orphan_openings": [],
        },
        warnings,
    )
