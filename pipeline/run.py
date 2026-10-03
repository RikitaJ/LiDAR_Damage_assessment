"""Capture → plan.json + floorplan.png (LiDAR / Stray / video)."""

from __future__ import annotations

import time
from pathlib import Path

from pipeline.config import SCHEMA_PATH, InputTier, RunConfig
from pipeline.export.output import render_plan, write_plan
from pipeline.io.session import load_session
from pipeline.io.validate import sanitize_room
from pipeline.stitch.stitch import stitch
from pipeline.stitch.stray_drift import apply_stray_loop_to_rooms
from pipeline.stitch.video_drift import apply_video_loop_to_rooms
from pipeline.geometry.overlap import pairwise_overlap_m2
from pipeline.io.tier_detect import CaptureKind, detect_capture_kind
from pipeline.tiers.lidar import parse_room
from pipeline.tiers.stray_room_v0 import parse_stray_room
from pipeline.tiers.video_room_v0 import parse_video_room


def _has_roomplan_json(lidar_dir: Path) -> bool:
    for name in ("room.json", "captured_room.json"):
        if (lidar_dir / name).is_file():
            return True
    return bool(list(lidar_dir.glob("*.json")))


def _parse_room_paths(rp, tier: InputTier) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    if tier == InputTier.VIDEO:
        return parse_video_room(rp.lidar_dir, rp.room_id, rp.name)
    if _has_roomplan_json(rp.lidar_dir):
        return parse_room(rp.lidar_dir, rp.room_id, rp.name), warnings
    if (rp.lidar_dir / "odometry.csv").is_file():
        room, w = parse_stray_room(
            rp.lidar_dir,
            rp.room_id,
            rp.name,
            stray_segment=rp.stray_segment,
            stray_segment_count=rp.stray_segment_count,
        )
        return room, w
    raise FileNotFoundError(f"No RoomPlan JSON, Stray odometry, or video under {rp.lidar_dir}")


def run_capture(capture_dir: Path, out_dir: Path, config: RunConfig) -> Path:
    if detect_capture_kind(capture_dir) == CaptureKind.UNKNOWN:
        try:
            load_session(capture_dir, tier_hint=config.tier)
        except FileNotFoundError as e:
            raise SystemExit(str(e)) from e
    return _run_pipeline(capture_dir, out_dir, config)


def run_lidar(capture_dir: Path, out_dir: Path, config: RunConfig) -> Path:
    if config.tier != InputTier.LIDAR:
        config = RunConfig(
            tier=InputTier.LIDAR,
            loop_closure=config.loop_closure,
            drift_correction=config.drift_correction,
        )
    return _run_pipeline(capture_dir, out_dir, config)


def _run_pipeline(capture_dir: Path, out_dir: Path, config: RunConfig) -> Path:
    t0 = time.time()
    tier = config.tier
    session = load_session(capture_dir, tier_hint=tier)
    if session.tier != tier:
        raise ValueError(f"Session tier {session.tier.value} != requested {tier.value}")

    rooms_raw: list[dict] = []
    qa_warnings: list[str] = []
    for rp in session.rooms:
        r, w = _parse_room_paths(rp, tier)
        qa_warnings.extend(w)
        qa_warnings.extend(sanitize_room(r))
        orphans = r.pop("_orphan_openings", [])
        if orphans:
            qa_warnings.append(f"{r['room_id']}: orphan openings {orphans}")
        rooms_raw.append(r)

    root = session.rooms[0].lidar_dir if session.rooms else capture_dir
    if tier == InputTier.LIDAR and (root / "odometry.csv").is_file():
        qa_warnings.extend(apply_stray_loop_to_rooms(rooms_raw, root, config.drift_correction))
    elif tier == InputTier.VIDEO:
        qa_warnings.extend(apply_video_loop_to_rooms(rooms_raw, root, config.drift_correction))

    apply_drift = config.drift_correction
    rooms, stitched = stitch(
        rooms_raw,
        tier,
        session.adjacency,
        config.loop_closure and apply_drift,
        drift_correction=apply_drift,
    )
    overlap = pairwise_overlap_m2(rooms)
    if overlap > 0.05:
        qa_warnings.append(f"stitched room overlap {overlap:.3f} m²")

    png = out_dir / "floorplan.png"
    stitched["render_path"] = render_plan(stitched, rooms, png)

    payload = {
        "schema_version": "1.0.0",
        "capture_id": session.capture_id,
        "input_tier": tier.value,
        "device": {"model": session.device_model, "has_lidar": session.has_lidar},
        "rooms": rooms,
        "stitched_plan": stitched,
        "damage_regions": [],
        "concealed_damage_flags": [],
        "scope_line_items": [],
        "drift_handling": _drift_block(session, tier, config.loop_closure),
        "pipeline_meta": {
            "command": "housefloor run --capture <capture_dir>",
            "capture_dir": str(capture_dir.name),
            "duration_s": round(time.time() - t0, 2),
            "models_used": _models_used(session, tier),
            "qa_warnings": qa_warnings,
            "overlap_m2": round(overlap, 4),
        },
    }

    out_json = out_dir / "plan.json"
    write_plan(payload, SCHEMA_PATH, out_json)
    return out_json


def _drift_block(session, tier: InputTier, loop_closure: bool) -> dict:
    if tier == InputTier.VIDEO:
        return {
            "method": "video_flow_loop",
            "loop_closure_enabled": loop_closure,
            "description": "Video v0: optical-flow path + optional loop nudge; no metric SLAM yet.",
            "pose_graph_notes": "Use --drift on|off for loop closure on estimated path.",
        }
    stray = session.rooms and (session.rooms[0].lidar_dir / "odometry.csv").is_file()
    if stray:
        return {
            "method": "stray_loop_closure+door_graph",
            "loop_closure_enabled": loop_closure,
            "description": "Stray: odometry loop nudge; multi-room door graph with overlap-only separation.",
            "pose_graph_notes": "Drift on applies loop shift + stitch correction.",
        }
    return {
        "method": "door_aligned_pose_graph",
        "loop_closure_enabled": loop_closure,
        "description": "Rooms aligned at door midpoints; soft closure nudge on revisits.",
        "pose_graph_notes": "RoomPlan JSON wall frames.",
    }


def _models_used(session, tier: InputTier) -> list[str]:
    if tier == InputTier.VIDEO:
        return ["video_keyframes_v0", "optical_flow_poses", "shared_stitch"]
    root = session.rooms[0].lidar_dir if session.rooms else None
    if root and (root / "odometry.csv").is_file():
        return ["stray_scanner_v0", "trajectory_or_depth_geometry"]
    return ["roomplan_json", "door_pose_graph"]
