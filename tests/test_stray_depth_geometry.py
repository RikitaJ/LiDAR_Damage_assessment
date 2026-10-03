import json
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.config import RunConfig
from pipeline.run import run_capture


def _write_mini_stray_capture(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "camera_matrix.csv").write_text(
        "500.0, 0.0, 16.0\n0.0, 500.0, 16.0\n0.0, 0.0, 1.0\n",
        encoding="utf-8",
    )
    depth_dir = root / "depth"
    conf_dir = root / "confidence"
    depth_dir.mkdir()
    conf_dir.mkdir()
    depth = np.zeros((48, 48), dtype=np.uint16)
    depth[6:42, 6:42] = 2800
    depth[20:28, 6:42] = 0
    conf = np.full((48, 48), 2, dtype=np.uint8)
    for i in range(4):
        Image.fromarray(depth).save(depth_dir / f"{i:06d}.png")
        Image.fromarray(conf).save(conf_dir / f"{i:06d}.png")
    (root / "odometry.csv").write_text(
        "timestamp,frame,x,y,z,qx,qy,qz,qw\n"
        + "\n".join(f"{1+i}.0,{i},0,0,0,0,0,0,1" for i in range(4))
        + "\n",
        encoding="utf-8",
    )


def test_stray_depth_produces_intervals_and_walls(tmp_path):
    cap = tmp_path / "mini_stray"
    _write_mini_stray_capture(cap)
    out = run_capture(cap, cap / "out", RunConfig())
    plan = json.loads(out.read_text(encoding="utf-8"))
    room = plan["rooms"][0]
    wall = room["walls"][0]
    assert "lo" in wall["length_m"] and "hi" in wall["length_m"]
    assert wall["length_m"]["hi"] >= wall["length_m"]["value_m"]
    assert room["ceiling_height_m"]["value_m"] >= 2.0


def test_fetch_data_skips_todo_url():
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "fetch_data.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "skip" in proc.stdout.lower() or "c00a170fe1" in proc.stdout
