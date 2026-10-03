"""Video estimated path loop closure (same idea as Stray loop nudge)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.frontends.video import load_video_capture


def apply_video_loop_to_rooms(rooms: list[dict], capture_dir: Path, enabled: bool) -> list[str]:
    if not enabled or not rooms:
        return []
    cf = load_video_capture(capture_dir)
    if len(cf.frames) < 5:
        return []
    xs = [float(fr.T_world_cam[0, 3]) for fr in cf.frames]
    zs = [float(fr.T_world_cam[2, 3]) for fr in cf.frames]
    start = np.array([xs[0], zs[0]], dtype=float)
    end = np.array([xs[-1], zs[-1]], dtype=float)
    delta = end - start
    gap = float(np.linalg.norm(delta))
    if gap < 0.04:
        return []
    scale = min(0.3, gap / max(max(xs) - min(xs), max(zs) - min(zs), 0.5))
    shift = -delta * scale
    for r in rooms:
        for w in r.get("walls", []):
            for p in w.get("polyline_m", []):
                p[0] += float(shift[0])
                p[1] += float(shift[1])
        tx, _, tz = r["pose_world"]["translation_m"]
        r["pose_world"]["translation_m"] = [tx + float(shift[0]), 0.0, tz + float(shift[1])]
    return [f"video loop-closure shift {gap:.3f} m (scale={scale:.3f})"]
