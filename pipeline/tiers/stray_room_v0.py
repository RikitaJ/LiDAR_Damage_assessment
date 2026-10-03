"""Single-room plan from Stray CaptureFrames."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import InputTier
from pipeline.geometry.floor_footprint import footprint_from_path_xz
from pipeline.geometry.stray_poses import apply_loop_closure_to_poses
from pipeline.frontends.stray_lidar import load_stray_capture
from pipeline.geometry.hard_surfaces import filter_points_and_warn
from pipeline.geometry.stray_points import collect_world_points
from pipeline.geometry.stray_room import room_from_point_cloud
from pipeline.tiers.stray_segment import subset_capture_frames
from pipeline.measure.intervals import with_interval
from pipeline.schema.capture_frames import CaptureFrames


def parse_stray_room(
    lidar_dir: Path,
    room_id: str,
    name: str,
    *,
    stray_segment: int | None = None,
    stray_segment_count: int | None = None,
    drift_correction: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    cf = load_stray_capture(lidar_dir, capture_id=room_id)
    if stray_segment is not None and stray_segment_count:
        cf = subset_capture_frames(cf, stray_segment, stray_segment_count)
    warnings = list(cf.warnings)
    pose_w, _ = apply_loop_closure_to_poses(cf, enabled=drift_correction)
    warnings.extend(pose_w)

    rng = _rng_for_capture(cf.capture_id)
    pts, pt_warn = collect_world_points(cf)
    warnings.extend(pt_warn)
    if pts is not None:
        pts, surf_warn = filter_points_and_warn(pts, cf)
        warnings.extend(surf_warn)

    if pts is not None and len(pts) >= 120:
        room, extra = room_from_point_cloud(
            pts, room_id, name, scale_sigma_rel=cf.scale_sigma_rel, rng=rng
        )
        return room, warnings + extra

    if pts is not None and len(pts) >= 50:
        warnings.append("sparse depth; using trajectory fallback with widened intervals")
    return _room_from_trajectory(cf, room_id, name, warnings, path_buffer=False)


def _rng_for_capture(capture_id: str) -> np.random.Generator:
    seed = int(hashlib.sha256(capture_id.encode()).hexdigest()[:8], 16)
    return np.random.default_rng(seed)


def _room_from_trajectory(
    cf: CaptureFrames,
    room_id: str,
    name: str,
    warnings: list[str],
    *,
    path_buffer: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    tier = InputTier.LIDAR
    if not cf.frames:
        warnings.append("no frames; emitting placeholder room with wide uncertainty")
        return _placeholder_room(room_id, name, tier), warnings

    xs = np.array([float(fr.T_world_cam[0, 3]) for fr in cf.frames], dtype=float)
    zs = np.array([float(fr.T_world_cam[2, 3]) for fr in cf.frames], dtype=float)
    if path_buffer:
        corners, area_val = footprint_from_path_xz(xs, zs)
        warnings.append("video/sparse: footprint from buffered camera path")
    else:
        min_x, max_x = float(xs.min()), float(xs.max())
        min_z, max_z = float(zs.min()), float(zs.max())
        span_x = max(max_x - min_x, 0.5)
        span_z = max(max_z - min_z, 0.5)
        if span_x < 1.0 or span_z < 1.0:
            warnings.append("camera path span < 1 m; footprint intervals widened")
        corners = [
            [min_x, min_z],
            [max_x, min_z],
            [max_x, max_z],
            [min_x, max_z],
        ]
        area_val = span_x * span_z

    cx, cz = float(np.mean(xs)), float(np.mean(zs))
    walls = _walls_from_corners(corners, room_id, tier, cf, wide=not path_buffer)
    sigma = max(area_val * 0.25, area_val * cf.scale_sigma_rel * 4)
    return (
        {
            "room_id": room_id,
            "name": name,
            "floor_area_m2": with_interval(
                area_val, sigma, notes="stray_trajectory", tier=tier, kind="footprint"
            ),
            "ceiling_height_m": with_interval(
                2.5, 0.4, notes="stray_trajectory_default_ceiling", tier=tier, kind="height"
            ),
            "walls": walls,
            "pose_world": {"translation_m": [cx, 0.0, cz], "rotation_quat": [0.0, 0.0, 0.0, 1.0]},
            "_orphan_openings": [],
        },
        warnings,
    )


def _walls_from_corners(
    corners: list[list[float]],
    room_id: str,
    tier: InputTier,
    cf: CaptureFrames,
    *,
    wide: bool,
) -> list[dict]:
    walls: list[dict] = []
    for i in range(4):
        a = corners[i]
        b = corners[(i + 1) % 4]
        length = float(np.hypot(b[0] - a[0], b[1] - a[1]))
        sigma = 0.008 * (5.0 if wide else 1.0) * max(1.0, 1.0 / max(cf.scale_sigma_rel, 0.05))
        walls.append(
            {
                "id": f"{room_id}-W{i + 1}",
                "length_m": with_interval(length, sigma, notes="stray_trajectory"),
                "polyline_m": [a, b],
                "openings": [],
            }
        )
    return walls


def _placeholder_room(room_id: str, name: str, tier: InputTier) -> dict[str, Any]:
    w = 3.0
    corners = [[0.0, 0.0], [w, 0.0], [w, w], [0.0, w]]
    walls = []
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        walls.append(
            {
                "id": f"{room_id}-W{i + 1}",
                "length_m": with_interval(w, 0.5, notes="placeholder"),
                "polyline_m": [a, b],
                "openings": [],
            }
        )
    return {
        "room_id": room_id,
        "name": name,
        "floor_area_m2": with_interval(w * w, 2.0, notes="placeholder"),
        "ceiling_height_m": with_interval(2.5, 0.5, notes="placeholder"),
        "walls": walls,
        "pose_world": {"translation_m": [0.0, 0.0, 0.0], "rotation_quat": [0.0, 0.0, 0.0, 1.0]},
        "_orphan_openings": [],
    }
