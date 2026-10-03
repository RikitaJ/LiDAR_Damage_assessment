from pathlib import Path

from pipeline.config import InputTier
from pipeline.damage.phase5 import run_damage_pipeline


def test_damage_pipeline_empty_capture_emits_contract():
    """Without RGB stills, pipeline still returns surfaces + optional QA flags."""
    rooms = [
        {
            "room_id": "R1",
            "name": "room",
            "pose_world": {"translation_m": [0.0, 0.0, 0.0]},
            "ceiling_height_m": {"value_m": 2.5, "lo": 2.3, "hi": 2.7},
            "floor_area_m2": {"value_m": 10.0, "lo": 9.0, "hi": 11.0},
            "walls": [
                {
                    "id": "R1-W1",
                    "length_m": {"value_m": 4.0, "lo": 3.8, "hi": 4.2},
                    "polyline_m": [[0.0, 0.0], [4.0, 0.0]],
                    "openings": [],
                }
            ],
        }
    ]
    surfaces, regions, concealed, scope, warnings, limitations = run_damage_pipeline(
        rooms,
        ["R39: low LiDAR confidence ratio; possible glass"],
        Path("."),
        InputTier.LIDAR,
    )
    assert surfaces
    assert isinstance(regions, list)
    assert isinstance(scope, list)
    assert any("damage:" in w or "R39" in w for w in warnings) or concealed
    assert limitations
    assert any("SAM" in line or "damage_v3" in line for line in limitations)
    assert any("R39" in line or "mirror" in line for line in limitations)
