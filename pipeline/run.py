"""Phase 1: LiDAR capture → plan.json + floorplan.png."""

from __future__ import annotations

import time
from pathlib import Path

from pipeline.config import SCHEMA_PATH, InputTier, RunConfig
from pipeline.export.output import render_plan, write_plan
from pipeline.io.session import load_session
from pipeline.stitch.stitch import stitch
from pipeline.geometry.overlap import pairwise_overlap_m2
from pipeline.tiers.lidar import parse_room


def run_lidar(capture_dir: Path, out_dir: Path, config: RunConfig) -> Path:
    if config.tier != InputTier.LIDAR:
        raise NotImplementedError(
            f"Phase 1 supports tier=lidar only. ({config.tier.value} comes in a later phase.)"
        )

    t0 = time.time()
    session = load_session(capture_dir)
    if session.tier != InputTier.LIDAR:
        raise ValueError(
            f"Phase 1 only supports manifest tier 'lidar' (got '{session.tier.value}')."
        )
    rooms_raw = [parse_room(rp.lidar_dir, rp.room_id, rp.name) for rp in session.rooms]
    qa_warnings: list[str] = []
    for r in rooms_raw:
        orphans = r.pop("_orphan_openings", [])
        if orphans:
            qa_warnings.append(f"{r['room_id']}: orphan openings {orphans}")

    rooms, stitched = stitch(rooms_raw, InputTier.LIDAR, session.adjacency, config.loop_closure)
    overlap = pairwise_overlap_m2(rooms)
    if overlap > 0.05:
        qa_warnings.append(f"stitched room overlap {overlap:.3f} m²")

    png = out_dir / "floorplan.png"
    stitched["render_path"] = render_plan(stitched, rooms, png)

    payload = {
        "schema_version": "1.0.0",
        "capture_id": session.capture_id,
        "input_tier": "lidar",
        "device": {"model": session.device_model, "has_lidar": session.has_lidar},
        "rooms": rooms,
        "stitched_plan": stitched,
        "damage_regions": [],
        "concealed_damage_flags": [],
        "scope_line_items": [],
        "drift_handling": {
            "method": "door_aligned_pose_graph",
            "loop_closure_enabled": config.loop_closure,
            "description": "Rooms aligned at door midpoints; soft closure nudge on revisits.",
            "pose_graph_notes": "LiDAR uses Apple wall frames; no SLAM drift on single-room parse.",
        },
        "pipeline_meta": {
            "command": f"housefloor run --capture {capture_dir}",
            "duration_s": round(time.time() - t0, 2),
            "models_used": ["roomplan_json", "door_pose_graph"],
            "qa_warnings": qa_warnings,
            "overlap_m2": round(overlap, 4),
        },
    }

    out_json = out_dir / "plan.json"
    write_plan(payload, SCHEMA_PATH, out_json)
    return out_json
