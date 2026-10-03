"""Fit calibration multipliers from benchmark fixture (Tester — not GT from captures)."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from pipeline.benchmark.gates import score
from pipeline.config import RunConfig
from pipeline.run import run_lidar

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "lidar_two_room"
GT = FIXTURE / "ground_truth.json"
CAL_OUT = ROOT / "configs" / "calibration.json"


def fit_from_fixture() -> dict:
    if not FIXTURE.is_dir() or not GT.is_file():
        raise FileNotFoundError("missing tests/fixtures/lidar_two_room or ground_truth.json")

    with tempfile.TemporaryDirectory() as td:
        cap = Path(td) / "cap"
        out = Path(td) / "out"
        shutil.copytree(FIXTURE, cap)
        run_lidar(cap, out, RunConfig())
        report = score(out / "plan.json", GT, "lidar")

    fp_err = report.details.get("footprint", {}).get("error_pct")
    wall_rate = report.metrics.get("wall_pass_rate") or 0.0
    k_fp = 1.0 if fp_err is None else min(2.0, max(1.0, 1.0 + float(fp_err)))
    k_wall = min(2.0, max(1.0, 1.0 + (1.0 - float(wall_rate)) * 0.5))

    data = json.loads(CAL_OUT.read_text(encoding="utf-8")) if CAL_OUT.is_file() else {"version": 1, "multipliers": {}}
    data.setdefault("multipliers", {})
    data["multipliers"]["lidar"] = {
        "footprint": round(k_fp, 3),
        "wall": round(k_wall, 3),
        "height": data["multipliers"].get("lidar", {}).get("height", 1.05),
        "opening": data["multipliers"].get("lidar", {}).get("opening", 1.1),
    }
    data["notes"] = "Last fit from tests/fixtures/lidar_two_room via eval.calibrate"
    data["fixture_metrics"] = {
        "footprint_error_pct": fp_err,
        "wall_pass_rate": wall_rate,
    }
    return data


def fit_and_write() -> Path:
    data = fit_from_fixture()
    CAL_OUT.parent.mkdir(parents=True, exist_ok=True)
    CAL_OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return CAL_OUT


def main() -> int:
    fit_and_write()
    print(CAL_OUT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
