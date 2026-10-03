"""Load and fuse Stray depth + confidence into a world-frame point cloud."""

from __future__ import annotations

import numpy as np

from pipeline.geometry.voxel import voxel_downsample
from pipeline.schema.capture_frames import CaptureFrame, CaptureFrames

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore


def collect_world_points(
    cf: CaptureFrames,
    *,
    max_frames: int = 60,
    stride_px: int = 3,
) -> tuple[np.ndarray | None, list[str]]:
    warnings: list[str] = []
    if Image is None:
        warnings.append("Pillow not installed; cannot read depth PNGs")
        return None, warnings

    with_depth = [fr for fr in cf.frames if fr.depth_path and fr.depth_path.is_file()]
    if not with_depth:
        return None, warnings

    step = max(1, len(with_depth) // max_frames)
    picked = with_depth[::step][:max_frames]

    chunks: list[np.ndarray] = []
    for fr in picked:
        pts = _frame_world_points(fr, stride_px, warnings)
        if pts is not None and len(pts) >= 20:
            chunks.append(pts)

    if not chunks:
        warnings.append("depth present but no valid 3D points after filtering")
        return None, warnings

    pts = np.vstack(chunks)
    pts = voxel_downsample(pts)
    if len(pts) > 250_000:
        idx = np.linspace(0, len(pts) - 1, 250_000, dtype=int)
        pts = pts[idx]
    return pts, warnings


def _frame_world_points(fr: CaptureFrame, stride: int, warnings: list[str]) -> np.ndarray | None:
    assert fr.depth_path is not None
    try:
        depth_mm = np.array(Image.open(fr.depth_path))
    except OSError:
        warnings.append(f"unreadable depth: {fr.depth_path.name}")
        return None

    if depth_mm.ndim > 2:
        depth_mm = depth_mm[..., 0]
    depth_m = depth_mm.astype(np.float32) / 1000.0

    mask = (depth_m > 0.15) & (depth_m < 8.0)
    if fr.confidence_path and fr.confidence_path.is_file():
        try:
            conf = np.array(Image.open(fr.confidence_path))
            if conf.ndim > 2:
                conf = conf[..., 0]
            mask &= conf == 2
        except OSError:
            warnings.append(f"unreadable confidence: {fr.confidence_path.name}")

    h, w = depth_m.shape
    K = _intrinsics_for_depth(fr.K, w, h)
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]

    vs = np.arange(0, h, stride)
    us = np.arange(0, w, stride)
    uu, vv = np.meshgrid(us, vs)
    z = depth_m[vv, uu]
    m = mask[vv, uu]
    if not np.any(m):
        return None

    uu, vv, z = uu[m], vv[m], z[m]
    x = (uu - cx) * z / fx
    y = (vv - cy) * z / fy
    cam = np.column_stack([x, y, z, np.ones(len(z))])
    return (fr.T_world_cam @ cam.T).T[:, :3]


def _intrinsics_for_depth(K_rgb: np.ndarray, depth_w: int, depth_h: int) -> np.ndarray:
    """Scale full-resolution intrinsics (Stray odometry fx/cx) to depth PNG size."""
    rgb_w = max(float(K_rgb[0, 2]) * 2.0, float(depth_w))
    rgb_h = max(float(K_rgb[1, 2]) * 2.0, float(depth_h))
    sx, sy = depth_w / rgb_w, depth_h / rgb_h
    K = K_rgb.copy()
    K[0, 0] *= sx
    K[0, 2] *= sx
    K[1, 1] *= sy
    K[1, 2] *= sy
    return K
