#!/usr/bin/env python3
"""Phase 1–2 sign-off: LiDAR fixture gates + Stray mini capture + drift ablation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.benchmark.ablation import drift_ablation
from pipeline.benchmark.gates import score
from pipeline.config import RunConfig
from pipeline.run import run_capture, run_lidar

from eval.report import score_capture
from tests.fixtures.capture_factory import copy_lidar_two_room, ground_truth_json, write_mini_stray_capture

def main() -> int:
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="phase12_") as td:
        td_path = Path(td)
        cap = copy_lidar_two_room(td_path / "lidar_two_room_fixture")
        out = cap / "out"
        run_lidar(cap, out, RunConfig(drift_correction=True))
        gate = score(out / "plan.json", ground_truth_json(), "lidar")
        eval_rep = score_capture(cap, out / "plan.json", tier="lidar")
        rows.append(
            {
                "check": "lidar_two_room_fixture",
                "status": "ok" if eval_rep.get("ready") and all(gate.passed.values()) else "fail",
                "gates_passed": gate.passed,
                "footprint_m2": json.loads((out / "plan.json").read_text())["stitched_plan"][
                    "footprint_area_m2"
                ]["value_m"],
            }
        )

        stray = td_path / "mini_stray"
        write_mini_stray_capture(stray, n_frames=14)
        stray_out = stray / "out"
        run_capture(stray, stray_out, RunConfig(drift_correction=True))
        stray_plan = json.loads((stray_out / "plan.json").read_text(encoding="utf-8"))
        rows.append(
            {
                "check": "stray_mini_capture",
                "status": "ok" if stray_plan["rooms"] and (stray_out / "floorplan.png").is_file() else "fail",
                "models": stray_plan["pipeline_meta"].get("models_used", []),
            }
        )

        ab = drift_ablation(cap, cap / "phase12_ablation")
        rows.append({"check": "drift_ablation", "status": "ok", "delta_m2": ab["delta_m2"]})

    report = {"phase": "1-2", "runs": rows}
    out_path = ROOT / "docs" / "PHASE12_SIGNOFF_REPORT.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    failed = [r for r in rows if r.get("status") != "ok"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
