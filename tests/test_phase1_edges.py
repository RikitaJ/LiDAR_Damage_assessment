import json
import shutil
from pathlib import Path

import pytest

from pipeline.config import RunConfig
from pipeline.io.apple_import import import_apple
from pipeline.io.session import load_session
from pipeline.run import run_lidar
from pipeline.stitch.stitch import stitch
from pipeline.tiers.lidar import parse_room

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "benchmark_sample"


def test_single_room_no_adjacency(tmp_path):
    cap = tmp_path / "one_room"
    shutil.copytree(SAMPLE / "rooms" / "living_room", cap / "rooms" / "living_room")
    (cap / "manifest.json").write_text(
        json.dumps(
            {
                "capture_id": "one",
                "tier": "lidar",
                "device": {"model": "iPhone 15 Pro", "has_lidar": True},
                "rooms": [{"room_id": "living_room", "name": "Living Room"}],
            }
        ),
        encoding="utf-8",
    )
    out = run_lidar(cap, cap / "out", RunConfig())
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert len(plan["rooms"]) == 1
    assert plan["stitched_plan"]["adjacency"] == []


def test_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_session(tmp_path)


def test_manifest_adjacency_unknown_room_ignored(tmp_path):
    cap = tmp_path / "cap"
    shutil.copytree(SAMPLE, cap)
    manifest = json.loads((cap / "manifest.json").read_text(encoding="utf-8"))
    manifest["adjacency"] = [{"room_a": "living_room", "room_b": "ghost", "via_opening_id": "x"}]
    (cap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    session = load_session(cap)
    assert session.adjacency == []
    out = run_lidar(cap, cap / "out", RunConfig())
    assert out.exists()


def test_empty_rooms_manifest(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"tier": "lidar", "rooms": []}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="non-empty"):
        load_session(tmp_path)


def test_wrong_tier_rejected(tmp_path):
    cap = tmp_path / "bad_tier"
    shutil.copytree(SAMPLE, cap)
    manifest = json.loads((cap / "manifest.json").read_text(encoding="utf-8"))
    manifest["tier"] = "photos"
    (cap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Session tier photos"):
        run_lidar(cap, cap / "out", RunConfig())


def test_no_walls_in_json(tmp_path):
    lidar = tmp_path / "lidar"
    lidar.mkdir()
    (lidar / "room.json").write_text(json.dumps({"walls": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="no walls"):
        parse_room(lidar, "x", "X")


def test_bad_transform(tmp_path):
    lidar = tmp_path / "lidar"
    lidar.mkdir()
    (lidar / "room.json").write_text(
        json.dumps({"walls": [{"identifier": "w0", "dimensions": [3, 2.5, 0.1], "transform": [1, 0]}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="16 numbers"):
        parse_room(lidar, "x", "X")


def test_stitch_three_rooms_chain(tmp_path):
    rooms = [
        _fake_room("a", "d_a", offset_x=0.0),
        _fake_room("b", "d_b", offset_x=20.0),
        _fake_room("c", "d_c", offset_x=40.0),
    ]
    edges = [("b", "a", "d_b"), ("c", "b", "d_c")]
    from pipeline.config import InputTier

    out, _ = stitch(rooms, InputTier.LIDAR, edges, loop_closure=False)
    xs = [r["pose_world"]["translation_m"][0] for r in out]
    assert len(set(round(x, 3) for x in xs)) >= 2


def test_import_apple_then_run(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    shutil.copy(SAMPLE / "rooms" / "living_room" / "lidar" / "room.json", src / "living_room.json")
    cap = tmp_path / "cap"
    import_apple(src, cap)
    out = run_lidar(cap, cap / "out", RunConfig())
    assert out.exists()


def test_loop_closure_off_runs():
    out = run_lidar(SAMPLE, SAMPLE / "out_no_lc", RunConfig(loop_closure=False))
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["drift_handling"]["loop_closure_enabled"] is False


def _fake_room(rid: str, door_id: str, offset_x: float) -> dict:
    x0, x1 = offset_x, offset_x + 3.0
    return {
        "room_id": rid,
        "name": rid,
        "floor_area_m2": {"value_m": 9.0},
        "pose_world": {"translation_m": [0, 0, 0], "rotation_quat": [0, 0, 0, 1]},
        "walls": [
            {
                "id": "w0",
                "length_m": {"value_m": 3.0},
                "polyline_m": [[x0, 0.0], [x1, 0.0]],
                "openings": [
                    {
                        "id": door_id,
                        "kind": "door",
                        "width_m": {"value_m": 0.9},
                        "height_m": {"value_m": 2.0},
                        "wall_id": "w0",
                    }
                ],
            }
        ],
    }
