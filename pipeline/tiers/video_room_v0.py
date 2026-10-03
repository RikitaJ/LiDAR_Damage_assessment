"""Video CaptureFrames → single-room plan (reuses motion footprint + video-tier σ)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.config import InputTier
from pipeline.frontends.video import load_video_capture
from pipeline.geometry.hard_surfaces import filter_points_and_warn
from pipeline.geometry.stray_points import collect_world_points
from pipeline.geometry.stray_room import room_from_point_cloud
from pipeline.tiers.stray_room_v0 import _room_from_trajectory


def parse_video_room(lidar_dir: Path, room_id: str, name: str) -> tuple[dict[str, Any], list[str]]:
    """`lidar_dir` = capture root containing the video file."""
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

    room, extra = _room_from_trajectory(cf, room_id, name, warnings)
    return _tag_video_tier(room), extra


def _tag_video_tier(room: dict[str, Any]) -> dict[str, Any]:
    """Ensure confidence notes mention video tier (σ already from InputTier in helpers)."""
    tier_note = InputTier.VIDEO.value
    for wall in room.get("walls", []):
        conf = wall.get("length_m", {}).get("confidence", {})
        conf["notes"] = f"{tier_note}; " + conf.get("notes", "")
    return room
