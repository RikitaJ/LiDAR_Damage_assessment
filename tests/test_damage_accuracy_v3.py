from pipeline.config import InputTier
from pipeline.damage.project import hit_to_region, wall_index_from_image_x
from pipeline.damage.refine import refine_region_confidence
from pipeline.measure.intervals import with_interval


def test_wall_index_from_image_x():
    assert wall_index_from_image_x(0.1, 4) == 0
    assert wall_index_from_image_x(0.9, 4) == 3


def test_hit_bbox_uv_width():
    room = {
        "room_id": "R1",
        "ceiling_height_m": {"value_m": 2.5},
        "floor_area_m2": {"value_m": 12},
        "walls": [
            {
                "id": "R1-W1",
                "length_m": {"value_m": 4.0},
                "polyline_m": [[0, 0], [4, 0]],
                "openings": [],
            }
        ],
    }
    hit = {
        "class": "water_stain",
        "surface_type": "wall",
        "u_center_frac": 0.5,
        "u0_frac": 0.2,
        "u1_frac": 0.45,
        "area_m2": 0.15,
        "bottom_above_floor_m": 0.2,
        "score": 0.6,
        "source": "hsv_stain_heuristic_v2",
    }
    reg = hit_to_region(hit, room, InputTier.LIDAR, "D1")
    assert reg
    poly = reg["polygon_surface"]
    assert poly[1][0] - poly[0][0] > 0.5


def test_ceiling_stain_surface_id():
    room = {
        "room_id": "R1",
        "ceiling_height_m": {"value_m": 2.5},
        "floor_area_m2": {"value_m": 12},
        "walls": [{"id": "W1", "length_m": {"value_m": 4}, "polyline_m": [[0, 0], [4, 0]], "openings": []}],
    }
    hit = {
        "class": "water_stain",
        "surface_type": "ceiling",
        "u_center_frac": 0.5,
        "u0_frac": 0.3,
        "u1_frac": 0.5,
        "area_m2": 0.1,
        "bottom_above_floor_m": 2.0,
        "score": 0.55,
        "source": "hsv_stain_heuristic_v2",
    }
    reg = hit_to_region(hit, room, InputTier.LIDAR, "D1")
    assert reg["surface_id"] == "R1-ceiling"


def test_refine_high_score_vlm():
    tier = InputTier.LIDAR
    reg = {
        "id": "D1",
        "score": 0.8,
        "source": "azure_damage_vlm_v1",
        "area_m2": with_interval(0.1, 0.05, notes="t", tier=tier, kind="footprint"),
    }
    lo_before = reg["area_m2"]["lo"]
    refine_region_confidence([reg], tier)
    assert reg["area_m2"]["lo"] >= lo_before - 0.001 or reg["area_m2"]["hi"] - reg["area_m2"]["lo"] < 0.15
