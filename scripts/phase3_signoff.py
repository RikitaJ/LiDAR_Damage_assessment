#!/usr/bin/env python3
"""Run Phase 3 video tier on local Stray samples and write a sign-off report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.benchmark.ablation import video_drift_ablation
from pipeline.config import InputTier, RunConfig
from pipeline.run import run_capture

SAMPLES = [
    ROOT / "single_room" / "c00a170fe1",
    ROOT / "single_scan_floor_only" / "1a8384c3f6",
    ROOT / "single_scan_with_ceiling" / "c7d28f72c6",
]


def main() -> int:
    rows: list[dict] = []
    for cap in SAMPLES:
        if not (cap / "rgb.mp4").is_file():
            rows.append({"capture": cap.name, "status": "skip", "reason": "no rgb.mp4"})
            continue
        out = cap / "out_phase3_signoff"
        plan_path = run_capture(cap, out, RunConfig(tier=InputTier.VIDEO, drift_correction=True))
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        fp = data["stitched_plan"]["footprint_area_m2"]["value_m"]
        def _rel(p: Path) -> str:
            try:
                return str(p.resolve().relative_to(ROOT))
            except ValueError:
                return str(p)

        rows.append(
            {
                "capture": cap.name,
                "status": "ok",
                "footprint_m2": fp,
                "models": data["pipeline_meta"].get("models_used", []),
                "plan": _rel(plan_path),
                "png": _rel(out / "floorplan.png"),
            }
        )

    ablation = None
    first = SAMPLES[0]
    if (first / "rgb.mp4").is_file():
        ablation = video_drift_ablation(first, first / "out_phase3_ablation")

    report = {
        "phase": 3,
        "tier": "video",
        "scope": "v0 offline (odometry metric path when co-located with rgb.mp4)",
        "runs": rows,
        "video_drift_ablation_c00": ablation,
    }
    out_path = ROOT / "docs" / "PHASE3_SIGNOFF_REPORT.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    failed = [r for r in rows if r.get("status") != "ok"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
