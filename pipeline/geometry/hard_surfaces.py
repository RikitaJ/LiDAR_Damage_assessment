"""R39: mirrors, glass, glossy floor, low depth — filter points and emit warnings."""

from __future__ import annotations

import numpy as np

from pipeline.schema.capture_frames import CaptureFrames


def filter_points_and_warn(
    pts: np.ndarray,
    cf: CaptureFrames,
) -> tuple[np.ndarray, list[str]]:
    warnings: list[str] = []
    if len(pts) == 0:
        return pts, warnings

    frame_stats = _per_frame_valid_depth_ratio(cf)
    if frame_stats:
        low_frac = sum(1 for r in frame_stats if r < 0.12) / len(frame_stats)
        if low_frac > 0.35:
            warnings.append(
                "R39: many frames with sparse depth (glass, wet floor, or low light); intervals widened"
            )
        conf2_frac = _confidence_two_ratio(cf)
        if conf2_frac is not None and conf2_frac < 0.35:
            warnings.append("R39: low LiDAR confidence ratio; possible glass or see-through surfaces")

    cleaned = _remove_far_outliers(pts)
    removed = len(pts) - len(cleaned)
    if removed > len(pts) * 0.05:
        warnings.append(f"R39: removed {removed} outlier points (possible mirror duplicates behind walls)")

    return cleaned, warnings


def _per_frame_valid_depth_ratio(cf: CaptureFrames) -> list[float]:
    ratios: list[float] = []
    for fr in cf.frames:
        if not fr.depth_path or not fr.depth_path.is_file():
            continue
        try:
            from PIL import Image

            depth = np.array(Image.open(fr.depth_path))
            if depth.ndim > 2:
                depth = depth[..., 0]
            valid = (depth.astype(np.float32) > 150) & (depth < 8000)
            ratios.append(float(valid.mean()))
        except OSError:
            continue
    return ratios


def _confidence_two_ratio(cf: CaptureFrames) -> float | None:
    counts = [0, 0]
    for fr in cf.frames:
        if not fr.confidence_path or not fr.confidence_path.is_file():
            continue
        try:
            from PIL import Image

            conf = np.array(Image.open(fr.confidence_path))
            if conf.ndim > 2:
                conf = conf[..., 0]
            counts[0] += conf.size
            counts[1] += int((conf == 2).sum())
        except OSError:
            continue
    if counts[0] == 0:
        return None
    return counts[1] / counts[0]


def _remove_far_outliers(pts: np.ndarray) -> np.ndarray:
    xz = pts[:, [0, 2]]
    y = pts[:, 1]
    cx, cz = float(np.median(xz[:, 0])), float(np.median(xz[:, 1]))
    cy = float(np.median(y))
    d = np.linalg.norm(xz - np.array([cx, cz]), axis=1)
    span = float(np.percentile(d, 92)) + 0.01
    keep = (d <= span + 0.6) & (np.abs(y - cy) < 3.5)
    return pts[keep] if np.any(keep) else pts
