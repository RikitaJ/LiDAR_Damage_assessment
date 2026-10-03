from pipeline.config import InputTier
from pipeline.geometry.floor_polygon import stitched_footprint_area_m2
from pipeline.stitch.stitch import stitch


def _fake_room(rid: str, x0: float, x1: float, z0: float, z1: float) -> dict:
    return {
        "room_id": rid,
        "name": rid,
        "floor_area_m2": {"value_m": (x1 - x0) * (z1 - z0)},
        "pose_world": {"translation_m": [0.0, 0.0, 0.0], "rotation_quat": [0, 0, 0, 1]},
        "walls": [
            {
                "id": "w0",
                "length_m": {"value_m": x1 - x0},
                "polyline_m": [[x0, z0], [x1, z0]],
                "openings": [],
            },
            {
                "id": "w1",
                "length_m": {"value_m": z1 - z0},
                "polyline_m": [[x1, z0], [x1, z1]],
                "openings": [],
            },
        ],
    }


def test_stitched_footprint_unions_two_rooms():
    a = _fake_room("a", 0, 4, 0, 3)
    b = _fake_room("b", 4, 6, 0, 2)
    rooms, stitched = stitch(
        [a, b],
        InputTier.LIDAR,
        [("a", "b", "")],
        loop_closure=False,
    )
    fp = stitched["footprint_area_m2"]["value_m"]
    assert fp >= 16.0
    assert stitched_footprint_area_m2(rooms) == fp
