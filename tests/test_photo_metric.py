from pipeline.geometry.photo_metric import (
    apply_metric_to_estimate,
    merge_vlm_estimates,
    prior_metric_scale,
    refine_rectangle_lengths,
    reject_implausible_estimate,
)


def test_prior_scale_from_door_height():
    est = {"floor_area_m2": 12.0, "wall_lengths_m": [4, 3, 4, 3], "door_height_m": 1.8}
    s, spread, _w = prior_metric_scale(est)
    assert s > 1.05
    assert spread >= 0.0


def test_apply_metric_scales_area():
    est = {"floor_area_m2": 10.0, "wall_lengths_m": [4, 2.5, 4, 2.5]}
    out = apply_metric_to_estimate(est, 1.1)
    assert abs(out["floor_area_m2"] - 12.1) < 0.01
    assert abs(out["wall_lengths_m"][0] - 4.4) < 0.01


def test_merge_vlm_medians():
    a = {"floor_area_m2": 10.0, "ceiling_height_m": 2.5, "wall_lengths_m": [4, 3, 4, 3]}
    b = {"floor_area_m2": 14.0, "ceiling_height_m": 2.7, "wall_lengths_m": [5, 3, 5, 3]}
    m = merge_vlm_estimates([a, b])
    assert m is not None
    assert m["floor_area_m2"] == 12.0
    assert m["wall_lengths_m"][0] == 4.5


def test_refine_rectangle_area():
    lens = refine_rectangle_lengths([4.2, 2.8, 3.8, 3.0], target_area_m2=12.0)
    assert abs(lens[0] - lens[2]) < 0.01
    assert abs(lens[1] - lens[3]) < 0.01
    assert abs(lens[0] * lens[1] - 12.0) < 0.5


def test_reject_huge_room():
    ok, _ = reject_implausible_estimate(
        {"floor_area_m2": 200.0, "wall_lengths_m": [20, 10, 20, 10]}
    )
    assert not ok
