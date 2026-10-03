"""Capture → plan.json + floorplan.png (LiDAR / Stray / video)."""

from __future__ import annotations

import time
from pathlib import Path

from pipeline.config import SCHEMA_PATH, InputTier, RunConfig
from pipeline.damage.phase5 import run_damage_pipeline
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


def _parse_room_paths(
    rp,
    tier: InputTier,
    config: RunConfig,
    *,
    allow_photo_mvs_rescale: bool = True,
) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    if tier == InputTier.PHOTOS:
        return parse_photo_room(
            rp.lidar_dir,
            rp.room_id,
            rp.name,
            allow_mvs_rescale=allow_photo_mvs_rescale,
        )
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
    allow_photo_mvs = tier != InputTier.PHOTOS or len(session.rooms) == 1
    for rp in session.rooms:
        r, w = _parse_room_paths(
            rp, tier, config, allow_photo_mvs_rescale=allow_photo_mvs
        )
        qa_warnings.extend(w)
        qa_warnings.extend(sanitize_room(r))
        orphans = r.pop("_orphan_openings", [])
        if orphans:
            qa_warnings.append(f"{r['room_id']}: orphan openings {orphans}")
        rooms_raw.append(r)

    apply_drift = config.drift_correction
    adjacency_for_stitch = session.adjacency
    if tier == InputTier.PHOTOS and not adjacency_for_stitch and len(rooms_raw) > 1:
        from pipeline.stitch.photo_door_verify import filter_inferred_photo_edges
        from pipeline.stitch.photo_layout import infer_photo_adjacency

        inferred = infer_photo_adjacency(rooms_raw)
        inferred, orb_filter_w = filter_inferred_photo_edges(session, inferred)
        qa_warnings.extend(orb_filter_w)
        adjacency_for_stitch = inferred

    rooms, stitched = stitch(
        rooms_raw,
        tier,
        adjacency_for_stitch,
        config.loop_closure and apply_drift,
        drift_correction=apply_drift,
    )
    layout_note = stitched.pop("_layout_warning", None)
    if layout_note:
        qa_warnings.append(layout_note)
    if tier == InputTier.PHOTOS and stitched.get("adjacency"):
        from pipeline.stitch.photo_door_verify import verify_photo_adjacency

        qa_warnings.extend(
            verify_photo_adjacency(
                session,
                [(e["room_a"], e["room_b"], e.get("via_opening_id", "")) for e in stitched["adjacency"]],
            )
        )
    overlap = pairwise_overlap_m2(rooms)
    if overlap > 0.05:
        qa_warnings.append(f"stitched room overlap {overlap:.3f} m²")

    surfaces, damage_regions, concealed_flags, scope_items, dmg_warn, damage_limits = run_damage_pipeline(
        rooms,
        qa_warnings,
        capture_dir.resolve(),
        tier,
        adjacency=adjacency_for_stitch,
    )
    qa_warnings.extend(dmg_warn)

    png = out_dir / "floorplan.png"
    stitched["render_path"] = render_plan(stitched, rooms, png, damage_regions=damage_regions)

    payload = {
        "schema_version": "1.0.0",
        "capture_id": session.capture_id,
        "input_tier": tier.value,
        "device": {"model": session.device_model, "has_lidar": session.has_lidar},
        "rooms": rooms,
        "surfaces": surfaces,
        "stitched_plan": stitched,
        "damage_regions": damage_regions,
        "concealed_damage_flags": concealed_flags,
        "scope_line_items": scope_items,
        "drift_handling": _drift_block(session, tier, config.loop_closure),
        "pipeline_meta": {
            "command": "housefloor run --capture <capture_dir>",
            "capture_dir": str(capture_dir.name),
            "duration_s": round(time.time() - t0, 2),
            "models_used": _models_used(session, tier, rooms_raw),
            "qa_warnings": qa_warnings,
            "overlap_m2": round(overlap, 4),
            "limitations": damage_limits,
        },
    }

    out_json = out_dir / "plan.json"
    write_plan(payload, SCHEMA_PATH, out_json)
    return out_json


def _drift_block(session, tier: InputTier, loop_closure: bool) -> dict:
    if tier == InputTier.PHOTOS:
        return {
            "method": "photo_layout_solver",
            "loop_closure_enabled": False,
            "description": "Per-room folders: door pairing + 90° rotations + overlap penalty (brief §5.6).",
            "pose_graph_notes": "No global poses; manifest adjacency or inferred door-width pairing.",
        }
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


def _photo_used_vlm(rooms: list[dict] | None) -> bool:
    if not rooms:
        return False
    for room in rooms:
        notes = str(room.get("floor_area_m2", {}).get("confidence", {}).get("notes", ""))
        if "photo_vlm" in notes:
            return True
    return False


def _video_used_depth_fusion(rooms: list[dict] | None) -> bool:
    if not rooms:
        return False
    for room in rooms:
        notes = str(room.get("floor_area_m2", {}).get("confidence", {}).get("notes", ""))
        if "stray_floor_occupancy" in notes or "stray_depth_planes" in notes:
            return True
    return False


def _models_used(session, tier: InputTier, rooms: list[dict] | None = None) -> list[str]:
    if tier == InputTier.PHOTOS:
        from pipeline.integrations.azure_optional import _env, _load_dotenv_once

        _load_dotenv_once()
        used_vlm = _photo_used_vlm(rooms)
        if used_vlm:
            return ["photo_vlm_layout", "photo_door_stitch", "shared_stitch"]
        if _env("AZURE_OPENAI_API_KEY"):
            return ["photo_v0_prior", "azure_openai_vlm_optional", "shared_stitch"]
        return ["photo_v0_prior", "photo_door_stitch", "shared_stitch"]
    if tier == InputTier.VIDEO:
        root = session.rooms[0].lidar_dir if session.rooms else None
        if root and (root / "odometry.csv").is_file() and find_video_file(root):
            if _video_used_depth_fusion(rooms):
                return ["video_odometry_metric", "depth_fusion_footprint", "shared_stitch"]
            return ["video_odometry_metric", "path_buffer_footprint", "shared_stitch"]
        if _video_used_depth_fusion(rooms):
            return ["video_keyframes_v0", "optical_flow_poses", "depth_fusion_footprint", "shared_stitch"]
        return ["video_keyframes_v0", "optical_flow_poses", "odometry_scale_optional", "shared_stitch"]
    root = session.rooms[0].lidar_dir if session.rooms else None
    if root and (root / "odometry.csv").is_file():
        return ["stray_scanner_v0", "trajectory_or_depth_geometry"]
    return ["roomplan_json", "door_pose_graph"]
