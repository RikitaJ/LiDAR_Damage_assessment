from pathlib import Path

from pipeline.config import RunConfig
from pipeline.io.tier_detect import CaptureKind, detect_capture_kind
from pipeline.run import run_capture

from tests.fixtures.capture_factory import write_mini_stray_capture


def test_detect_stray_fixture(tmp_path: Path):
    cap = tmp_path / "stray"
    write_mini_stray_capture(cap)
    assert detect_capture_kind(cap) == CaptureKind.STRAY_SCANNER


def test_run_mini_stray_without_manifest(tmp_path: Path):
    cap = tmp_path / "stray"
    write_mini_stray_capture(cap)
    out = tmp_path / "out"
    plan = run_capture(cap, out, RunConfig())
    assert plan.is_file()
    text = plan.read_text(encoding="utf-8")
    assert "qa_warnings" in text
    assert (out / "floorplan.png").exists()
