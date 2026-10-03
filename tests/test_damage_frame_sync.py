from pathlib import Path

from pipeline.config import InputTier
from pipeline.damage.frame_lookup import DamageViewContext, _rank_images, frame_for_image
from pipeline.schema.capture_frames import CaptureFrame


def test_image_time_rank_maps_to_frames():
    import numpy as np

    frames = [
        CaptureFrame(i, float(i), None, np.eye(3), np.eye(4)) for i in range(5)
    ]
    ctx = DamageViewContext(tier=InputTier.LIDAR, frames=frames, image_time_rank={"a": 0.0, "b": 1.0})
    assert frame_for_image(ctx, Path("a")) is frames[0]
    assert frame_for_image(ctx, Path("b")) is frames[-1]


def test_rank_images_empty_when_one_path():
    assert _rank_images([Path("only.jpg")]) == {}
