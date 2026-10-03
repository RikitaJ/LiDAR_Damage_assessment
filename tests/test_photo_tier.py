import json
import shutil
from pathlib import Path

from pipeline.config import InputTier, RunConfig
from pipeline.run import run_capture

from tests.fixtures.capture_factory import LIDAR_TWO_ROOM


def test_photo_tier_manifest(tmp_path: Path):
    cap = tmp_path / "photo_cap"
    shutil.copytree(LIDAR_TWO_ROOM, cap)
    manifest = json.loads((cap / "manifest.json").read_text(encoding="utf-8"))
    manifest["tier"] = "photos"
    (cap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    photos = cap / "rooms" / "living_room" / "photos"
    photos.mkdir(exist_ok=True)
    (photos / "a.jpg").write_bytes(b"\xff\xd8\xff")

    out = run_capture(cap, cap / "out", RunConfig(tier=InputTier.PHOTOS))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["input_tier"] == "photos"
    assert data["rooms"]
