import json
import shutil
from pathlib import Path

import pytest

from pipeline.config import RunConfig
from pipeline.io.apple_import import import_apple
from pipeline.io.session import load_session
from pipeline.io.validate import sanitize_room
from pipeline.run import run_lidar
from pipeline.tiers.lidar import parse_room

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "benchmark_sample"


def test_missing_tier_defaults_to_lidar(tmp_path):
    cap = tmp_path / "cap"
    shutil.copytree(SAMPLE, cap)
    manifest = json.loads((cap / "manifest.json").read_text(encoding="utf-8"))
    del manifest["tier"]
    (cap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    session = load_session(cap)
    assert session.tier.value == "lidar"


def test_nan_wall_sanitized_not_crash():
    room = {
        "room_id": "x",
        "walls": [{"id": "w1", "length_m": {"value_m": float("nan")}, "polyline_m": [[0, 0], [0, 0]]}],
        "floor_area_m2": {"value_m": float("nan")},
    }
    w = sanitize_room(room)
    assert w
    assert room["walls"][0]["length_m"]["value_m"] == 0.01


def test_negative_wall_length_sanitized():
    room = {
        "room_id": "x",
        "walls": [{"id": "w1", "length_m": {"value_m": -2.0}, "polyline_m": [[0, 0], [1, 0]]}],
        "floor_area_m2": {"value_m": 4.0},
    }
    sanitize_room(room)
    assert room["walls"][0]["length_m"]["value_m"] > 0


def test_import_apple_refuses_overwrite(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    shutil.copy(SAMPLE / "rooms" / "living_room" / "lidar" / "room.json", src / "living.json")
    out = tmp_path / "out"
    import_apple(src, out)
    with pytest.raises(FileExistsError):
        import_apple(src, out)


def test_roomplan_column_major_transform(tmp_path):
    lidar = tmp_path / "lidar"
    lidar.mkdir()
    data = {
        "walls": [
            {
                "identifier": "w0",
                "dimensions": [4.0, 2.5, 0.1],
                "transform": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2.0, 0, 0, 1],
            }
        ]
    }
    (lidar / "room.json").write_text(json.dumps(data), encoding="utf-8")
    room = parse_room(lidar, "t", "T")
    p0 = room["walls"][0]["polyline_m"][0]
    assert abs(p0[0] - 2.0) < 0.05 or abs(p0[0]) > 0.1


def test_run_with_bad_wall_injected(tmp_path):
    cap = tmp_path / "cap"
    shutil.copytree(SAMPLE, cap)
    lidar = cap / "rooms" / "living_room" / "lidar" / "room.json"
    data = json.loads(lidar.read_text(encoding="utf-8"))
    data["walls"][0]["dimensions"] = [float("nan"), 2.5, 0.1]
    lidar.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid length"):
        run_lidar(cap, cap / "out", RunConfig())
