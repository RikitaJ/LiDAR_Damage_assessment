import numpy as np

from pipeline.damage.segment import SEGMENT_TAG_FAST, segment_hits_on_image


def test_fast_hsv_segment_tightens_bbox():
    import cv2

    bgr = np.zeros((200, 300, 3), np.uint8)
    cv2.rectangle(bgr, (90, 110), (210, 170), (25, 120, 200), -1)
    hit = {
        "class": "water_stain",
        "surface_type": "wall",
        "u0_frac": 0.1,
        "u1_frac": 0.9,
        "u_center_frac": 0.5,
        "area_m2": 0.1,
        "score": 0.5,
        "source": "hsv_stain_heuristic_v2",
    }
    out = segment_hits_on_image(bgr, [hit])[0]
    assert SEGMENT_TAG_FAST in out.get("source", "")
    assert out["u1_frac"] - out["u0_frac"] < 0.75


def test_segment_skips_empty_hits():
    bgr = np.zeros((64, 64, 3), np.uint8)
    assert segment_hits_on_image(bgr, []) == []
