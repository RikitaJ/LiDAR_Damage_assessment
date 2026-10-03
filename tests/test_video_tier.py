import json
from pathlib import Path

from pipeline.config import InputTier, RunConfig
from pipeline.run import run_capture

from tests.fixtures.capture_factory import write_mini_stray_capture, write_mini_video_capture


def test_video_tier_on_mp4_folder(tmp_path: Path):
    cap = tmp_path / "video_cap"
    write_mini_video_capture(cap)
    out = tmp_path / "out"
    plan = run_capture(cap, out, RunConfig(tier=InputTier.VIDEO))
    data = json.loads(plan.read_text(encoding="utf-8"))
    assert data["input_tier"] == "video"
    assert data["rooms"]
    assert (out / "floorplan.png").is_file()


def test_video_tier_odometry_metric_path(tmp_path: Path):
    cap = tmp_path / "stray_video"
    write_mini_stray_capture(cap, n_frames=12)
    write_mini_video_capture(cap, name="rgb.mp4")
    out = tmp_path / "out"
    plan = run_capture(cap, out, RunConfig(tier=InputTier.VIDEO))
    data = json.loads(plan.read_text(encoding="utf-8"))
    assert "video_odometry_metric" in data["pipeline_meta"]["models_used"]
