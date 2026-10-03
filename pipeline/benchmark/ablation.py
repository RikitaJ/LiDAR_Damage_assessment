"""Drift / loop-closure ablation: footprint with loop on vs off."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.config import InputTier, RunConfig
from pipeline.run import run_capture, run_lidar


def drift_ablation(capture_dir: Path, work_dir: Path) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    on_dir = work_dir / "loop_on"
    off_dir = work_dir / "loop_off"
    run_lidar(capture_dir, on_dir, RunConfig(loop_closure=True, drift_correction=True))
    run_lidar(capture_dir, off_dir, RunConfig(loop_closure=False, drift_correction=False))

    on_fp = _footprint(on_dir / "plan.json")
    off_fp = _footprint(off_dir / "plan.json")
    delta = abs(on_fp - off_fp)
    rel = delta / max(on_fp, 1e-6)
    return {
        "footprint_loop_on_m2": on_fp,
        "footprint_loop_off_m2": off_fp,
        "delta_m2": delta,
        "relative_delta": rel,
        "paths": {"on": str(on_dir / "plan.json"), "off": str(off_dir / "plan.json")},
    }


def video_drift_ablation(capture_dir: Path, work_dir: Path) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    on_dir = work_dir / "loop_on"
    off_dir = work_dir / "loop_off"
    run_capture(
        capture_dir,
        on_dir,
        RunConfig(tier=InputTier.VIDEO, loop_closure=True, drift_correction=True),
    )
    run_capture(
        capture_dir,
        off_dir,
        RunConfig(tier=InputTier.VIDEO, loop_closure=False, drift_correction=False),
    )
    on_fp = _footprint(on_dir / "plan.json")
    off_fp = _footprint(off_dir / "plan.json")
    delta = abs(on_fp - off_fp)
    return {
        "footprint_loop_on_m2": on_fp,
        "footprint_loop_off_m2": off_fp,
        "delta_m2": delta,
        "relative_delta": delta / max(on_fp, 1e-6),
        "paths": {"on": str(on_dir / "plan.json"), "off": str(off_dir / "plan.json")},
    }


def _footprint(plan_path: Path) -> float:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    return float(plan["stitched_plan"]["footprint_area_m2"]["value_m"])
