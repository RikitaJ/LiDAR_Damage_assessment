from pathlib import Path

from pipeline.config import RunConfig
from pipeline.io.tier_detect import CaptureKind, detect_capture_kind
from pipeline.run import run_capture

ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "single_room sample data_given" / "c00a170fe1"


def test_detect_stray_sample():
    assert detect_capture_kind(COMPANY) == CaptureKind.STRAY_SCANNER


def test_run_company_stray_sample_without_manifest():
    if not COMPANY.is_dir():
        return
    out = COMPANY / "out_stray_test"
    plan = run_capture(COMPANY, out, RunConfig())
    assert plan.is_file()
    text = plan.read_text(encoding="utf-8")
    assert "qa_warnings" in text
    assert (out / "floorplan.png").exists()
