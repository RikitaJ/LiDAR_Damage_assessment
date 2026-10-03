import json
import shutil
from pathlib import Path

from pipeline.config import RunConfig
from pipeline.run import run_capture

from tests.fixtures.capture_factory import write_mini_stray_capture

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "examples" / "stray_multi_manifest.json"


def test_stray_multi_room_manifest_segments(tmp_path: Path):
    cap = tmp_path / "multi"
    write_mini_stray_capture(cap, n_frames=8)
    shutil.copy(MANIFEST, cap / "manifest.json")
    out = run_capture(cap, tmp_path / "out", RunConfig(drift_correction=False))
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert len(plan["rooms"]) == 2
    ids = {r["room_id"] for r in plan["rooms"]}
    assert ids == {"room_a", "room_b"}
