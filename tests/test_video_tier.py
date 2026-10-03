import json
from pathlib import Path

import pytest

from pipeline.config import InputTier, RunConfig
from pipeline.run import run_capture

ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "single_room sample data_given" / "c00a170fe1"


@pytest.mark.skipif(not COMPANY.is_dir(), reason="company sample not present")
def test_video_tier_on_mp4_folder():
    out = COMPANY / "out_video_tier"
    plan = run_capture(COMPANY, out, RunConfig(tier=InputTier.VIDEO))
    data = json.loads(plan.read_text(encoding="utf-8"))
    assert data["input_tier"] == "video"
    assert data["rooms"]
    assert (out / "floorplan.png").is_file()
