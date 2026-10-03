from pathlib import Path

import numpy as np

from pipeline.config import InputTier
from pipeline.damage.frame_lookup import DamageViewContext
from pipeline.damage.project_camera import PROJ_TAG, project_hits_on_image
from pipeline.measure.intervals import with_interval
from pipeline.schema.capture_frames import CaptureFrame


def _room() -> dict:
    tier = InputTier.LIDAR
    return {
        "room_id": "R1",
        "pose_world": {"translation_m": [0.0, 0.0, 0.0]},
        "ceiling_height_m": with_interval(2.5, 0.1, notes="t", tier=tier, kind="height"),
        "walls": [
            {
                "id": "R1-W1",
                "length_m": with_interval(4.0, 0.1, notes="t", tier=tier, kind="wall"),
                "polyline_m": [[0.0, 0.0], [4.0, 0.0]],
                "openings": [],
            }
        ],
    }


def test_calibrated_projection_sets_frac():
    K = np.array([[600, 0, 320], [0, 600, 240], [0, 0, 1]], dtype=float)
    T = np.eye(4)
    T[:3, 3] = [2.0, 1.45, 2.5]
    T[:3, 2] = [0.0, 0.0, -1.0]
    T[:3, 0] = [1.0, 0.0, 0.0]
    T[:3, 1] = [0.0, 1.0, 0.0]
    frame = CaptureFrame(0, 0.0, None, K, T)
    ctx = DamageViewContext(tier=InputTier.LIDAR, frames=[frame])
    hit = {
        "class": "water_stain",
        "surface_type": "wall",
        "u0_frac": 0.35,
        "u1_frac": 0.55,
        "v0_frac": 0.4,
        "v1_frac": 0.7,
        "source": "hsv_stain_heuristic_v2",
    }
    out, w = project_hits_on_image(
        [hit],
        room=_room(),
        tier=InputTier.LIDAR,
        image_path=Path("housefloor_damage_vid_0.jpg"),
        view_ctx=ctx,
        img_w=640,
        img_h=480,
    )
    assert PROJ_TAG in out[0].get("source", "")
    assert out[0]["u1_frac"] > out[0]["u0_frac"]


def test_photo_tier_exif_plane_projects():
    ctx = DamageViewContext(tier=InputTier.PHOTOS)
    hit = {
        "class": "water_stain",
        "surface_type": "wall",
        "u0_frac": 0.3,
        "u1_frac": 0.5,
        "v0_frac": 0.45,
        "v1_frac": 0.75,
        "source": "test",
    }
    out, _ = project_hits_on_image(
        [hit],
        room=_room(),
        tier=InputTier.PHOTOS,
        image_path=Path("still.jpg"),
        view_ctx=ctx,
        img_w=640,
        img_h=480,
    )
    assert "exif_wall_plane_v1" in out[0].get("source", "")
