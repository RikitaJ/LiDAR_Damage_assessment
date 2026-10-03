import json
from pathlib import Path

from pipeline.benchmark.ablation import drift_ablation
from pipeline.config import RunConfig
from pipeline.run import run_capture

from tests.fixtures.capture_factory import copy_lidar_two_room, write_mini_stray_capture


def test_drift_ablation_delta_on_lidar_fixture(tmp_path: Path):
    cap = copy_lidar_two_room(tmp_path / "cap")
    result = drift_ablation(cap, tmp_path / "ablation")
    assert result["delta_m2"] >= 0.0


def test_render_png_exists_with_drift_flags(tmp_path: Path):
    cap = copy_lidar_two_room(tmp_path / "cap")
    plan = run_capture(cap, tmp_path / "out", RunConfig(drift_correction=True))
    data = json.loads(plan.read_text(encoding="utf-8"))
    assert (tmp_path / "out" / "floorplan.png").stat().st_size > 5000
    assert "drift_correction_applied" in data["stitched_plan"]


def test_stray_drift_on_off_runs(tmp_path: Path):
    cap = tmp_path / "stray"
    write_mini_stray_capture(cap, n_frames=12)
    p_on = run_capture(cap, tmp_path / "on", RunConfig(drift_correction=True))
    p_off = run_capture(cap, tmp_path / "off", RunConfig(drift_correction=False))
    assert p_on.is_file() and p_off.is_file()
