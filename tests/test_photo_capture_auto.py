import json
from pathlib import Path

from pipeline.config import InputTier, RunConfig
from pipeline.geometry.photo_rect import manhattan_room_from_wall_lengths
from pipeline.io.session import load_session
from pipeline.io.tier_detect import detect_tier
from pipeline.run import run_capture
from pipeline.stitch.photo_layout import infer_photo_adjacency


def test_auto_discover_photo_folders_without_manifest(tmp_path: Path):
    cap = tmp_path / "auto_photos"
    for rid in ("hallway", "bedroom"):
        photos = cap / "rooms" / rid / "photos"
        photos.mkdir(parents=True)
        (photos / "shot.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x01" * 120 + b"\xff\xd9")

    assert detect_tier(cap, None) == InputTier.PHOTOS
    session = load_session(cap, tier_hint=InputTier.PHOTOS)
    assert session.tier == InputTier.PHOTOS
    assert len(session.rooms) == 2

    plan = run_capture(cap, cap / "out", RunConfig(tier=InputTier.PHOTOS))
    data = json.loads(plan.read_text(encoding="utf-8"))
    assert data["input_tier"] == "photos"
    assert len(data["rooms"]) == 2


def test_manhattan_l_shape_room():
    room = manhattan_room_from_wall_lengths(
        "L1",
        "L Room",
        [4.0, 2.0, 2.0, 2.0, 2.0, 4.0],
        tier=InputTier.PHOTOS,
        ceiling_m=2.6,
    )
    assert len(room["walls"]) == 6
    assert room["floor_area_m2"]["value_m"] > 10.0


def test_hub_infers_two_edges():
    rooms = [
        {
            "room_id": "hall",
            "walls": [
                {
                    "id": "w",
                    "openings": [
                        {"id": "h1", "kind": "door", "width_m": {"value_m": 0.9}, "height_m": {"value_m": 2.05}},
                        {"id": "h2", "kind": "door", "width_m": {"value_m": 0.80}, "height_m": {"value_m": 2.05}},
                    ],
                }
            ],
        },
        {
            "room_id": "living",
            "walls": [
                {
                    "id": "w",
                    "openings": [{"id": "l1", "kind": "door", "width_m": {"value_m": 0.91}, "height_m": {"value_m": 2.05}}],
                }
            ],
        },
        {
            "room_id": "bed",
            "walls": [
                {
                    "id": "w",
                    "openings": [{"id": "b1", "kind": "door", "width_m": {"value_m": 0.81}, "height_m": {"value_m": 2.05}}],
                }
            ],
        },
    ]
    edges = infer_photo_adjacency(rooms)
    assert len(edges) >= 2
    hubs = {a for a, b, _ in edges} | {b for a, b, _ in edges}
    assert "hall" in hubs
