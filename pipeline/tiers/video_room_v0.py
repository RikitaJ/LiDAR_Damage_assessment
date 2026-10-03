"""Video CaptureFrames → single-room plan (reuses motion footprint + video-tier σ)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.config import InputTier
from pipeline.frontends.stray_lidar import load_stray_capture
from pipeline.frontends.video import find_video_file, load_video_capture
from pipeline.geometry.stray_poses import apply_loop_closure_to_poses
from pipeline.geometry.hard_surfaces import filter_points_and_warn
from pipeline.geometry.stray_points import collect_world_points
from pipeline.geometry.stray_room import room_from_point_cloud
from pipeline.geometry.video_scale import align_video_room_to_odometry
from pipeline.tiers.stray_room_v0 import _room_from_trajectory


def parse_video_room(
    lidar_dir: Path,
    room_id: str,
    name: str,
    *,
    drift_correction: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    """`lidar_dir` = capture root containing the video file (and optional odometry.csv)."""
    lidar_dir = lidar_dir.resolve()
    if (lidar_dir / "odometry.csv").is_file() and find_video_file(lidar_dir) is not None:
        return _parse_video_from_odometry(lidar_dir, room_id, name, drift_correction)

    cf = load_video_capture(lidar_dir, capture_id=room_id)
    warnings = list(cf.warnings)

    # Optional Azure enrichment (env keys only — Quanta testing RG via .env)
    from pipeline.integrations.azure_optional import enrich_video_warnings

    warnings.extend(enrich_video_warnings(lidar_dir))

    pts, pt_warn = collect_world_points(cf)
    warnings.extend(pt_warn)
    if pts is not None:
        pts, surf_warn = filter_points_and_warn(pts, cf)
        warnings.extend(surf_warn)
        if len(pts) >= 120:
            room, extra = room_from_point_cloud(
                pts, room_id, name, scale_sigma_rel=cf.scale_sigma_rel
            )
            return _tag_video_tier(room), warnings + extra

    room, extra = _room_from_trajectory(cf, room_id, name, warnings, path_buffer=True)
    extra.extend(align_video_room_to_odometry(room, lidar_dir))
    return _tag_video_tier(room), extra


def _parse_video_from_odometry(
    root: Path,
    room_id: str,
    name: str,
    drift_correction: bool,
) -> tuple[dict[str, Any], list[str]]:
    cf = load_stray_capture(root, capture_id=room_id)
    warnings = list(cf.warnings)
    pose_w, _ = apply_loop_closure_to_poses(cf, enabled=drift_correction)
    warnings.extend(pose_w)

    from pipeline.integrations.azure_optional import enrich_video_warnings

    warnings.extend(enrich_video_warnings(root))
    room, extra = _room_from_trajectory(cf, room_id, name, warnings, path_buffer=True)
    extra.insert(0, "video tier: metric path from co-located odometry.csv + rgb.mp4")
    return _tag_video_tier(room), warnings + extra


def _tag_video_tier(room: dict[str, Any]) -> dict[str, Any]:
    """Ensure confidence notes mention video tier (σ already from InputTier in helpers)."""
    tier_note = InputTier.VIDEO.value
    for wall in room.get("walls", []):
        conf = wall.get("length_m", {}).get("confidence", {})
        conf["notes"] = f"{tier_note}; " + conf.get("notes", "")
    return room
