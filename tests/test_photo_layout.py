import json
import shutil
from pathlib import Path

from pipeline.config import InputTier, RunConfig
from pipeline.run import run_capture
from pipeline.measure.intervals import interval_notes, with_interval
from pipeline.stitch.photo_layout import infer_photo_adjacency, rotate_room_local
from pipeline.tiers.photo_room_v0 import _widen_intervals_for_scale_sigma

from tests.fixtures.capture_factory import LIDAR_TWO_ROOM


def test_rotate_preserves_floor_area():
    room = {
        "walls": [
            {
                "id": "w0",
                "length_m": {"value_m": 4.0},
                "polyline_m": [[0, 0], [4, 0]],
                "openings": [],
            },
            {
                "id": "w1",
                "length_m": {"value_m": 3.0},
                "polyline_m": [[4, 0], [4, 3]],
                "openings": [],
            },
        ]
    }
    before = 12.0
    rotate_room_local(room, 1)
    xs = [p[0] for w in room["walls"] for p in w["polyline_m"]]
    zs = [p[1] for w in room["walls"] for p in w["polyline_m"]]
    area = (max(xs) - min(xs)) * (max(zs) - min(zs))
    assert abs(area - before) < 0.01


def test_infer_adjacency_without_manifest_edges(tmp_path: Path):
    cap = tmp_path / "photo_cap"
    shutil.copytree(LIDAR_TWO_ROOM, cap)
    manifest = json.loads((cap / "manifest.json").read_text(encoding="utf-8"))
    manifest["tier"] = "photos"
    manifest["adjacency"] = []
    (cap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for rid in ("living_room", "hallway"):
        photos = cap / "rooms" / rid / "photos"
        photos.mkdir(exist_ok=True)
        (photos / "a.jpg").write_bytes(b"\xff\xd8\xff")
    plan = run_capture(cap, cap / "out", RunConfig(tier=InputTier.PHOTOS))
    data = json.loads(plan.read_text(encoding="utf-8"))
    assert len(data["rooms"]) == 2
    assert data["stitched_plan"]["adjacency"]


def test_widen_preserves_vlm_provenance():
    fa = with_interval(12.0, 1.0, notes="photo_vlm", tier=InputTier.PHOTOS, kind="footprint")
    room = {"floor_area_m2": fa, "walls": [], "ceiling_height_m": with_interval(2.5, 0.1, notes="photo_vlm", tier=InputTier.PHOTOS, kind="height")}
    _widen_intervals_for_scale_sigma(room, InputTier.PHOTOS, 0.18)
    assert "photo_vlm" in interval_notes(room["floor_area_m2"])


def test_infer_photo_adjacency_unit():
    rooms = [
        {
            "room_id": "a",
            "walls": [
                {
                    "id": "w",
                    "openings": [
                        {
                            "id": "d1",
                            "kind": "door",
                            "width_m": {"value_m": 0.9},
                        }
                    ],
                }
            ],
        },
        {
            "room_id": "b",
            "walls": [
                {
                    "id": "w",
                    "openings": [
                        {
                            "id": "d2",
                            "kind": "door",
                            "width_m": {"value_m": 0.92},
                        }
                    ],
                }
            ],
        },
    ]
    edges = infer_photo_adjacency(rooms)
    assert len(edges) == 1
