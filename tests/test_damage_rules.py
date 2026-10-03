from pathlib import Path

from pipeline.config import InputTier
from pipeline.damage.rules_v0 import build_scope_line_items, infer_damage_regions


def test_damage_rules_from_qa():
    regions, _ = infer_damage_regions(
        [],
        ["R39: low LiDAR confidence ratio; possible glass"],
        Path("."),
        InputTier.LIDAR,
    )
    assert regions
    scope = build_scope_line_items(["warn"], regions, InputTier.LIDAR)
    assert scope[0]["item"] == "verify_flagged_regions"
