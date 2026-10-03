import json
from pathlib import Path

from pipeline.benchmark.ablation import drift_ablation
from pipeline.config import RunConfig
from pipeline.run import run_capture

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "benchmark_sample"
COMPANY = ROOT / "single_room sample data_given" / "c00a170fe1"


def test_drift_ablation_delta_on_benchmark_sample():
    out = SAMPLE / "out_ablation_test"
    result = drift_ablation(SAMPLE, out)
    assert result["delta_m2"] >= 0.0


def test_render_png_exists_with_drift_flags(tmp_path):
    plan = run_capture(SAMPLE, tmp_path / "out", RunConfig(drift_correction=True))
    data = json.loads(plan.read_text(encoding="utf-8"))
    assert (tmp_path / "out" / "floorplan.png").stat().st_size > 5000
    assert "drift_correction_applied" in data["stitched_plan"]


def test_stray_drift_on_off_diff_if_company_present():
    if not COMPANY.is_dir():
        return
    on = COMPANY / "out_drift_on"
    off = COMPANY / "out_drift_off"
    p_on = run_capture(COMPANY, on, RunConfig(drift_correction=True))
    p_off = run_capture(COMPANY, off, RunConfig(drift_correction=False))
    a = json.loads(p_on.read_text(encoding="utf-8"))["stitched_plan"]["footprint_area_m2"]["value_m"]
    b = json.loads(p_off.read_text(encoding="utf-8"))["stitched_plan"]["footprint_area_m2"]["value_m"]
    assert a != b or json.loads(p_on.read_text())["pipeline_meta"]["qa_warnings"]
