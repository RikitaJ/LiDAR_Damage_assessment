import json
import shutil
from pathlib import Path

from pipeline.config import InputTier, RunConfig
from pipeline.run import run_capture

from tests.fixtures.capture_factory import LIDAR_TWO_ROOM


def test_photo_two_room_stitched_footprint(tmp_path: Path):
    cap = tmp_path / "photo_cap"
    shutil.copytree(LIDAR_TWO_ROOM, cap)
    manifest = json.loads((cap / "manifest.json").read_text(encoding="utf-8"))
    manifest["tier"] = "photos"
    (cap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for rid in ("living_room", "hallway"):
        photos = cap / "rooms" / rid / "photos"
        photos.mkdir(exist_ok=True)
        (photos / "a.jpg").write_bytes(b"\xff\xd8\xff")
    plan = run_capture(cap, cap / "out", RunConfig(tier=InputTier.PHOTOS))
    data = json.loads(plan.read_text(encoding="utf-8"))
    assert len(data["rooms"]) == 2
    fp = data["stitched_plan"]["footprint_area_m2"]["value_m"]
    assert fp > 8.0
    assert data["pipeline_meta"]["overlap_m2"] <= 0.2
