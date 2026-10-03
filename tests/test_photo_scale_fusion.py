from pipeline.config import InputTier
from pipeline.frontends.photo_mvs import PhotoMvsResult
from pipeline.geometry.photo_metric import prior_metric_scale
from pipeline.geometry.photo_rect import rectangle_room_from_wall_lengths
from pipeline.geometry.photo_scale import (
    apply_horizontal_scale_to_room,
    fuse_mvs_with_vlm_scale,
    mvs_horizontal_scale,
)
from pipeline.frontends.photo_exif import focal_sanity_warnings
from pipeline.stitch.photo_layout import infer_photo_adjacency


def test_mvs_scale_applies_when_span_agrees():
    mvs = PhotoMvsResult(n_views=4, n_triangulated=20, span_m=2.0, scale_sigma_rel=0.14, warnings=[])
    factor, w = mvs_horizontal_scale(2.7, mvs)
    assert factor is not None
    assert abs(factor - 1.35) < 0.02
    assert not w


def test_mvs_scale_rejected_when_span_outlier():
    mvs = PhotoMvsResult(n_views=4, n_triangulated=20, span_m=0.5, scale_sigma_rel=0.14, warnings=[])
    factor, w = mvs_horizontal_scale(4.0, mvs)
    assert factor is None
    assert w


def test_apply_horizontal_scale_doubles_area():
    room = rectangle_room_from_wall_lengths(
        "R1",
        "R",
        [2.0, 3.0, 2.0, 3.0],
        tier=InputTier.PHOTOS,
        area_m2=6.0,
    )
    before = float(room["floor_area_m2"]["value_m"])
    apply_horizontal_scale_to_room(room, 1.1, InputTier.PHOTOS, notes="test")
    after = float(room["floor_area_m2"]["value_m"])
    assert abs(after / before - 1.21) < 0.05


def test_fuse_mvs_vlm_median():
    fused, w = fuse_mvs_with_vlm_scale(1.2)
    assert 1.0 <= fused <= 1.12
    assert w


def test_camera_height_prior_scale():
    est = {"floor_area_m2": 12.0, "wall_lengths_m": [4, 3, 4, 3], "camera_height_m": 1.6}
    s, _, _w = prior_metric_scale(est)
    assert s < 1.0


def test_door_height_blocks_mismatch_pairing():
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
                            "height_m": {"value_m": 2.05},
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
                            "width_m": {"value_m": 0.9},
                            "height_m": {"value_m": 2.55},
                        }
                    ],
                }
            ],
        },
    ]
    assert infer_photo_adjacency(rooms) == []


def test_exif_focal_warning_when_missing():
    meta = {"samples": [{"file": "a.jpg", "width": 1000, "height": 800}]}
    w = focal_sanity_warnings(meta)
    assert any("focal length" in x for x in w)
