import json
from pathlib import Path

from pipeline.benchmark.ablation import drift_ablation
from pipeline.benchmark.gates import score
from pipeline.config import RunConfig
from pipeline.run import run_lidar

from tests.fixtures.capture_factory import copy_lidar_two_room, ground_truth_json


def test_score_after_run(tmp_path: Path):
    cap = copy_lidar_two_room(tmp_path / "cap")
    run_lidar(cap, tmp_path / "out", RunConfig())
    report = score(tmp_path / "out" / "plan.json", ground_truth_json(), "lidar")
    assert "opening_pass_rate" in report.metrics
    assert report.metrics["opening_pass_rate"] >= 0.85


def test_ablation_produces_two_plans(tmp_path: Path):
    cap = copy_lidar_two_room(tmp_path / "cap")
    result = drift_ablation(cap, tmp_path / "ablation")
    assert "footprint_loop_on_m2" in result
    assert Path(result["paths"]["on"]).exists()
    assert Path(result["paths"]["off"]).exists()


def test_qa_warnings_in_plan(tmp_path: Path):
    cap = copy_lidar_two_room(tmp_path / "cap")
    run_lidar(cap, tmp_path / "out", RunConfig())
    plan = json.loads((tmp_path / "out" / "plan.json").read_text(encoding="utf-8"))
    assert "qa_warnings" in plan["pipeline_meta"]
    assert "overlap_m2" in plan["pipeline_meta"]
