import json
import shutil
from pathlib import Path

from eval.gt_template import build_gt_template, write_gt_template

from tests.fixtures.capture_factory import LIDAR_TWO_ROOM


def test_gt_template_from_manifest(tmp_path: Path):
    cap = tmp_path / "cap"
    shutil.copytree(LIDAR_TWO_ROOM, cap)
    tpl = build_gt_template(cap)
    assert tpl["_meta"]["status"] == "TODO"
    assert "living_room" in tpl["wall_lengths_cm"]
    assert tpl["footprint_area_m2"] == "TODO"


def test_write_gt_template(tmp_path: Path, monkeypatch):
    cap = tmp_path / "cap"
    shutil.copytree(LIDAR_TWO_ROOM, cap)
    gt_dir = tmp_path / "gt_store"
    gt_dir.mkdir()
    monkeypatch.setattr("eval.gt_loader.GT_DIR", gt_dir)
    path = write_gt_template(cap)
    assert path.parent == gt_dir
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["wall_lengths_cm"]["hallway"]
