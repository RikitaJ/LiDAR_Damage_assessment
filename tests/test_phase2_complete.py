import json
import shutil
from pathlib import Path

from pipeline.benchmark.gates import score, score_repeatability
from pipeline.config import RunConfig
from pipeline.run import run_lidar

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "benchmark_sample"


def test_all_lidar_gates_on_sample():
    run_lidar(SAMPLE, SAMPLE / "out_p2", RunConfig())
    report = score(SAMPLE / "out_p2" / "plan.json", SAMPLE / "ground_truth.json", "lidar")
    p = report.passed
    assert p["opening_85pct_2cm"]
    assert p["ceiling_1p5cm"]
    assert p["walls_tier"]
    assert p["stitch_no_overlap"]
    assert p["calibration_sane"]


def test_ceiling_repeat_gate(tmp_path):
    run_lidar(SAMPLE, tmp_path / "a", RunConfig())
    shutil.copytree(tmp_path / "a", tmp_path / "b")
    report = score(
        tmp_path / "a" / "plan.json",
        SAMPLE / "ground_truth.json",
        "lidar",
        tmp_path / "b" / "plan.json",
    )
    assert report.passed["ceiling_repeat_spread_1cm"]


def test_bias_analysis():
    a = SAMPLE / "out_p2" / "plan.json"
    if not a.exists():
        run_lidar(SAMPLE, SAMPLE / "out_p2", RunConfig())
    report = score_repeatability(a, a)
    assert report.details["bias_analysis"]["kind"] == "repeatable"
