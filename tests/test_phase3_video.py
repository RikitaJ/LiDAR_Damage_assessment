"""Phase 3 integration checks (offline video path)."""

from pathlib import Path

import pytest

from pipeline.config import InputTier, RunConfig
from pipeline.run import run_capture

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = [
    ROOT / "single_room" / "c00a170fe1",
    ROOT / "single_scan_floor_only" / "1a8384c3f6",
    ROOT / "single_scan_with_ceiling" / "c7d28f72c6",
]


@pytest.mark.parametrize("cap", SAMPLES, ids=[p.name for p in SAMPLES])
def test_phase3_video_runs_on_company_mp4(cap: Path, tmp_path: Path):
    if not (cap / "rgb.mp4").is_file():
        pytest.skip("sample mp4 not present")
    out = tmp_path / "out"
    plan = run_capture(cap, out, RunConfig(tier=InputTier.VIDEO, drift_correction=True))
    import json

    data = json.loads(plan.read_text(encoding="utf-8"))
    assert data["input_tier"] == "video"
    assert data["stitched_plan"]["footprint_area_m2"]["value_m"] > 1.0
    assert (out / "floorplan.png").is_file()
