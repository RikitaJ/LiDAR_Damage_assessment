import json
import shutil
from pathlib import Path

from pipeline.benchmark.gates import score, score_repeatability
from pipeline.config import RunConfig
from pipeline.run import run_lidar

from tests.fixtures.capture_factory import copy_lidar_two_room, ground_truth_json


def test_all_lidar_gates_on_sample(tmp_path: Path):
    cap = copy_lidar_two_room(tmp_path / "cap")
    run_lidar(cap, tmp_path / "out", RunConfig())
    report = score(tmp_path / "out" / "plan.json", ground_truth_json(), "lidar")
    p = report.passed
    assert p["opening_85pct_2cm"]
    assert p["ceiling_1p5cm"]
    assert p["walls_tier"]
    assert p["stitch_no_overlap"]
    assert p["calibration_sane"]


def test_ceiling_repeat_gate(tmp_path: Path):
    cap = copy_lidar_two_room(tmp_path / "cap")
    run_lidar(cap, tmp_path / "a", RunConfig())
    shutil.copytree(tmp_path / "a", tmp_path / "b")
    report = score(
        tmp_path / "a" / "plan.json",
        ground_truth_json(),
        "lidar",
        tmp_path / "b" / "plan.json",
    )
    assert report.passed["ceiling_repeat_spread_1cm"]


def test_bias_analysis(tmp_path: Path):
    cap = copy_lidar_two_room(tmp_path / "cap")
    run_lidar(cap, tmp_path / "out", RunConfig())
    plan = tmp_path / "out" / "plan.json"
    report = score_repeatability(plan, plan)
    assert report.details["bias_analysis"]["kind"] == "repeatable"
