import json
from pathlib import Path

import subprocess
import sys

from pipeline.config import RunConfig
from pipeline.run import run_capture

from tests.fixtures.capture_factory import write_mini_stray_capture


def test_stray_depth_produces_intervals_and_walls(tmp_path: Path):
    cap = tmp_path / "mini_stray"
    write_mini_stray_capture(cap)
    out = run_capture(cap, cap / "out", RunConfig())
    plan = json.loads(out.read_text(encoding="utf-8"))
    room = plan["rooms"][0]
    wall = room["walls"][0]
    assert "lo" in wall["length_m"] and "hi" in wall["length_m"]
    assert wall["length_m"]["hi"] >= wall["length_m"]["value_m"]
    assert room["ceiling_height_m"]["value_m"] >= 2.0


def test_fetch_data_skips_todo_url(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("capture_id,url,sha256\nexample,TODO,TODO\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "fetch_data.py"), "--manifest", str(manifest), "--dest", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "skip" in proc.stdout.lower()
