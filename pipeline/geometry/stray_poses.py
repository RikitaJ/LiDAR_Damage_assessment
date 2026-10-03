"""Stray odometry loop-closure: distribute start/end gap correction across poses."""

from __future__ import annotations

import numpy as np

from pipeline.schema.capture_frames import CaptureFrames

# Global constant (brief §4): max fraction of loop gap applied along the path.
LOOP_CORRECTION_SCALE = 0.55


def apply_loop_closure_to_poses(
    cf: CaptureFrames,
    *,
    enabled: bool,
) -> tuple[list[str], float]:
    """
    Adjust T_world_cam translations so drift accumulates less at the end of the scan.
    Returns warnings and the 2D loop gap (m) before correction.
    """
    if not enabled or len(cf.frames) < 5:
        return [], 0.0

    xs = np.array([float(fr.T_world_cam[0, 3]) for fr in cf.frames], dtype=float)
    zs = np.array([float(fr.T_world_cam[2, 3]) for fr in cf.frames], dtype=float)
    start = np.array([xs[0], zs[0]])
    end = np.array([xs[-1], zs[-1]])
    delta = end - start
    gap = float(np.linalg.norm(delta))
    if gap < 0.04:
        return [], gap

    span = max(float(xs.max() - xs.min()), float(zs.max() - zs.min()), 1.0)
    scale = min(LOOP_CORRECTION_SCALE, gap / span)
    n = len(cf.frames)
    for i, fr in enumerate(cf.frames):
        t = i / max(n - 1, 1)
        shift = -delta * scale * t
        fr.T_world_cam[0, 3] += float(shift[0])
        fr.T_world_cam[2, 3] += float(shift[1])

    return [f"stray pose loop-closure gap {gap:.3f} m (correction scale={scale:.3f})"], gap
