import json
from pathlib import Path

from pipeline.io.adjacency_infer import infer_adjacency
from pipeline.io.apple_import import import_apple
from pipeline.tiers.lidar import parse_room

from tests.fixtures.capture_factory import LIDAR_TWO_ROOM


def test_l_shape_polygon_area():
    from pipeline.geometry.wall_graph import polygon_area_from_walls

    walls = [
        {"polyline_m": [[0, 0], [4, 0]]},
        {"polyline_m": [[4, 0], [4, 3]]},
        {"polyline_m": [[4, 3], [2, 3]]},
        {"polyline_m": [[2, 3], [2, 1]]},
        {"polyline_m": [[2, 1], [0, 1]]},
        {"polyline_m": [[0, 1], [0, 0]]},
    ]
    area = polygon_area_from_walls(walls)
    assert 7.5 <= area <= 8.5


def test_import_infers_adjacency(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    for name in ("living_room", "hallway"):
        raw = LIDAR_TWO_ROOM / "rooms" / name / "lidar" / "room.json"
        (src / f"{name}.json").write_text(raw.read_text(encoding="utf-8"), encoding="utf-8")
    cap = tmp_path / "cap"
    import_apple(src, cap)
    manifest = json.loads((cap / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest.get("adjacency", [])) >= 1

