from pathlib import Path

from pipeline.config import InputTier
from pipeline.damage.cache import read_image_hits, write_image_hits
from pipeline.damage.concealed import evaluate_concealed_flags
from pipeline.damage.project import (
    annotate_opening_geometry,
    merge_regions_on_surface,
    pick_wall_id,
    room_for_image,
)
from pipeline.measure.intervals import with_interval


def test_damage_cache_roundtrip(tmp_path: Path):
    img = tmp_path / "room.jpg"
    img.write_bytes(b"fake-image-bytes-for-cache")
    hits = [{"class": "water_stain", "u_center_frac": 0.5, "area_m2": 0.1, "score": 0.5, "source": "test"}]
    write_image_hits(img, hits)
    assert read_image_hits(img) == hits


def test_room_for_image_maps_per_room_folder(tmp_path: Path):
    cap = tmp_path / "cap"
    photos = cap / "rooms" / "bed" / "photos"
    photos.mkdir(parents=True)
    img = photos / "a.jpg"
    img.write_text("x")
    rooms = [{"room_id": "bed", "walls": []}, {"room_id": "hall", "walls": []}]
    assert room_for_image(cap, img, rooms)["room_id"] == "bed"


def test_pick_wall_prefers_door_for_stain():
    room = {
        "walls": [
            {"id": "W1", "length_m": {"value_m": 3.0}, "openings": []},
            {
                "id": "W2",
                "length_m": {"value_m": 4.0},
                "openings": [{"kind": "door", "width_m": {"value_m": 0.9}}],
            },
        ]
    }
    assert pick_wall_id(room, cls="water_stain") == "W2"


def test_merge_overlapping_uv_regions():
    tier = InputTier.LIDAR
    a = {
        "surface_id": "R1-W1",
        "class": "water_stain",
        "polygon_surface": [[0.2, 0.1], [0.5, 0.1], [0.5, 0.4], [0.2, 0.4]],
        "score": 0.5,
        "source": "hsv_stain_heuristic_v1",
    }
    b = {
        "surface_id": "R1-W1",
        "class": "water_stain",
        "polygon_surface": [[0.35, 0.12], [0.6, 0.12], [0.6, 0.38], [0.35, 0.38]],
        "score": 0.55,
        "source": "hsv_stain_heuristic_v1",
    }
    merged = merge_regions_on_surface([a, b], tier)
    assert len(merged) == 1
    assert "merge_v2" in merged[0]["source"]


def test_cd05_fires_when_crack_near_door_corner():
    tier = InputTier.LIDAR
    room = {
        "room_id": "R1",
        "name": "room",
        "walls": [
            {
                "id": "R1-W1",
                "length_m": {"value_m": 4.0},
                "polyline_m": [[0.0, 0.0], [4.0, 0.0]],
                "openings": [
                    {
                        "id": "D1",
                        "kind": "door",
                        "width_m": {"value_m": 0.9},
                        "anchor_m": [2.0, 0.0],
                    }
                ],
            }
        ],
    }
    crack = {
        "id": "D1",
        "surface_id": "R1-W1",
        "class": "crack",
        "polygon_surface": [[1.55, 0.5], [1.9, 0.5], [1.9, 1.2], [1.55, 1.2]],
        "area_m2": with_interval(0.08, 0.03, notes="t", tier=tier, kind="footprint"),
        "bottom_above_floor_m": with_interval(0.5, 0.05, notes="t", tier=tier, kind="height"),
    }
    annotate_opening_geometry([crack], [room])
    assert crack.get("diagonal_from_opening") is True
    surfaces = [{"id": "R1-W1", "type": "wall", "room_id": "R1"}]
    flags = evaluate_concealed_flags([crack], surfaces, [room])
    assert any(f["rule_id"] == "CD-05" for f in flags)
