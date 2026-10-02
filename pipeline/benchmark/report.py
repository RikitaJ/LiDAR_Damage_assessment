"""Write benchmark/reports/REPORT.md for a capture session."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.benchmark.ablation import drift_ablation
from pipeline.benchmark.gates import score
from pipeline.config import RunConfig
from pipeline.run import run_lidar


def write_benchmark_report(capture_dir: Path, reports_dir: Path | None = None) -> Path:
    capture_dir = capture_dir.resolve()
    reports_dir = reports_dir or (capture_dir / "benchmark_report")
    reports_dir.mkdir(parents=True, exist_ok=True)

    import time

    t0 = time.time()
    out_dir = capture_dir / "out"
    run_lidar(capture_dir, out_dir, RunConfig())
    run_s = round(time.time() - t0, 2)

    gt = capture_dir / "ground_truth.json"
    repeat = capture_dir / "repeat" / "plan.json"
    gate = score(out_dir / "plan.json", gt, "lidar", repeat if repeat.is_file() else None)

    ablation = drift_ablation(capture_dir, reports_dir / "ablation")

    lines = [
        "# Benchmark report (LiDAR)",
        "",
        f"- capture: `{capture_dir.name}`",
        f"- run_time_s: {run_s}",
        "",
        "## Gates",
        "",
        f"```json\n{json.dumps(gate.to_dict(), indent=2)}\n```",
        "",
        "## Drift ablation",
        "",
        f"```json\n{json.dumps(ablation, indent=2)}\n```",
        "",
    ]
    path = reports_dir / "REPORT.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    (reports_dir / "gate_report.json").write_text(json.dumps(gate.to_dict(), indent=2), encoding="utf-8")
    return path
