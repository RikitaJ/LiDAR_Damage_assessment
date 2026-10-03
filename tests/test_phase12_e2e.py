import json
from pathlib import Path

from eval.report import score_capture
from pipeline.benchmark.gates import score
from pipeline.config import RunConfig
from pipeline.run import run_lidar

from tests.fixtures.capture_factory import copy_lidar_two_room, ground_truth_json


def test_eval_scores_fixture_by_manifest_capture_id(tmp_path: Path):
    cap = copy_lidar_two_room(tmp_path / "any_folder_name")
    run_lidar(cap, cap / "out", RunConfig(drift_correction=True))
    rep = score_capture(cap, cap / "out" / "plan.json", tier="lidar")
    assert rep["capture_id"] == "lidar_two_room_fixture"
    assert rep["ready"] is True
    gates = rep["gates"]["passed"]
    assert gates["walls_tier"]
    assert gates["stitch_no_overlap"]
    assert gates["footprint_tier"]


def test_lidar_fixture_footprint_near_gt(tmp_path: Path):
    cap = copy_lidar_two_room(tmp_path / "lidar_two_room_fixture")
    run_lidar(cap, cap / "out", RunConfig())
    report = score(cap / "out" / "plan.json", ground_truth_json(), "lidar")
    fp_err = report.metrics.get("footprint_error_pct")
    assert fp_err is not None and fp_err <= 0.02
