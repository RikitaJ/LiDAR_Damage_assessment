import json
from pathlib import Path

from pipeline.benchmark.ablation import drift_ablation
from pipeline.benchmark.gates import score
from pipeline.config import RunConfig
from pipeline.run import run_lidar

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "benchmark_sample"


def test_score_after_run():
    run_lidar(SAMPLE, SAMPLE / "out_gates", RunConfig())
    report = score(SAMPLE / "out_gates" / "plan.json", SAMPLE / "ground_truth.json", "lidar")
    assert "opening_pass_rate" in report.metrics
    assert report.metrics["opening_pass_rate"] >= 0.85


def test_ablation_produces_two_plans():
    result = drift_ablation(SAMPLE, SAMPLE / "out_ablation_test")
    assert "footprint_loop_on_m2" in result
    assert Path(result["paths"]["on"]).exists()
    assert Path(result["paths"]["off"]).exists()


def test_qa_warnings_in_plan():
    run_lidar(SAMPLE, SAMPLE / "out_qa", RunConfig())
    plan = json.loads((SAMPLE / "out_qa" / "plan.json").read_text(encoding="utf-8"))
    assert "qa_warnings" in plan["pipeline_meta"]
    assert "overlap_m2" in plan["pipeline_meta"]
