"""Capture → plan.json + floorplan.png (LiDAR / Stray / video)."""

from __future__ import annotations

import time
from pathlib import Path

from pipeline.config import SCHEMA_PATH, InputTier, RunConfig
from pipeline.damage.rules_v0 import build_scope_line_items, infer_damage_regions
from pipeline.export.output import render_plan, write_plan
from pipeline.io.session import load_session
from pipeline.io.validate import sanitize_room
from pipeline.stitch.stitch import stitch
from pipeline.geometry.overlap import pairwise_overlap_m2
from pipeline.frontends.video import find_video_file
from pipeline.io.tier_detect import CaptureKind, detect_capture_kind
from pipeline.tiers.lidar import parse_room
from pipeline.tiers.stray_room_v0 import parse_stray_room
from pipeline.tiers.photo_room_v0 import parse_photo_room
from pipeline.tiers.video_room_v0 import parse_video_room


def _has_roomplan_json(lidar_dir: Path) -> bool:
    for name in ("room.json", "captured_room.json"):
        if (lidar_dir / name).is_file():
            return True
    skip = {"manifest.json", "ground_truth.json", "plan.json", "package.json"}
    for p in sorted(lidar_dir.glob("*.json")):
        if p.name in skip:
            continue
        head = p.read_text(encoding="utf-8")[:800]
        if '"walls"' in head and '"transform"' in head:
            return True
    return False


def _parse_room_paths(rp, tier: InputTier, config: RunConfig) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    if tier == InputTier.PHOTOS:
        return parse_photo_room(rp.lidar_dir, rp.room_id, rp.name)
    if tier == InputTier.VIDEO:
        return parse_video_room(
            rp.lidar_dir, rp.room_id, rp.name, drift_correction=config.drift_correction
        )
    if _has_roomplan_json(rp.lidar_dir):
        return parse_room(rp.lidar_dir, rp.room_id, rp.name), warnings
    if (rp.lidar_dir / "odometry.csv").is_file():
        room, w = parse_stray_room(
            rp.lidar_dir,
            rp.room_id,
            rp.name,
            stray_segment=rp.stray_segment,
            stray_segment_count=rp.stray_segment_count,
            drift_correction=config.drift_correction,
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
        r, w = _parse_room_paths(rp, tier, config)
        qa_warnings.extend(w)
        qa_warnings.extend(sanitize_room(r))
        orphans = r.pop("_orphan_openings", [])
        if orphans:
            qa_warnings.append(f"{r['room_id']}: orphan openings {orphans}")
        rooms_raw.append(r)

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

    damage_regions, dmg_warn = infer_damage_regions(
        rooms, qa_warnings, capture_dir.resolve(), tier
    )
    qa_warnings.extend(dmg_warn)
    scope_items = build_scope_line_items(qa_warnings, damage_regions, tier)

    payload = {
        "schema_version": "1.0.0",
        "capture_id": session.capture_id,
        "input_tier": tier.value,
        "device": {"model": session.device_model, "has_lidar": session.has_lidar},
        "rooms": rooms,
        "stitched_plan": stitched,
        "damage_regions": damage_regions,
        "concealed_damage_flags": _concealed_flags_from_qa(qa_warnings),
        "scope_line_items": scope_items,
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
            "description": "Video: odometry metric path when rgb+odometry co-located; else optical-flow + scale.",
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


def _concealed_flags_from_qa(qa_warnings: list[str]) -> list[dict]:
    flags: list[dict] = []
    for w in qa_warnings:
        low = w.lower()
        if "r39" in low or "glass" in low or "mirror" in low or "sparse depth" in low:
            flags.append({"severity": "review", "reason": w, "source": "qa_heuristic_v0"})
    return flags


def _models_used(session, tier: InputTier) -> list[str]:
    if tier == InputTier.PHOTOS:
        from pipeline.integrations.azure_optional import _env, _load_dotenv_once

        _load_dotenv_once()
        if _env("AZURE_OPENAI_API_KEY"):
            return ["photo_v0_prior", "azure_openai_vlm_optional", "shared_stitch"]
        return ["photo_v0_prior", "shared_stitch"]
    if tier == InputTier.VIDEO:
        root = session.rooms[0].lidar_dir if session.rooms else None
        if root and (root / "odometry.csv").is_file() and find_video_file(root):
            return ["video_odometry_metric", "path_buffer_footprint", "shared_stitch"]
        return ["video_keyframes_v0", "optical_flow_poses", "odometry_scale_optional", "shared_stitch"]
    root = session.rooms[0].lidar_dir if session.rooms else None
    if root and (root / "odometry.csv").is_file():
        return ["stray_scanner_v0", "trajectory_or_depth_geometry"]
    return ["roomplan_json", "door_pose_graph"]
