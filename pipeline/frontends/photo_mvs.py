"""Sparse multi-view cues from 2–8 stills (OpenCV SfM-lite, brief §5.4 offline path)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pipeline.frontends.photo_exif import exif_summary, intrinsics_matrix


@dataclass
class PhotoMvsResult:
    n_views: int
    n_triangulated: int
    span_m: float | None
    scale_sigma_rel: float
    warnings: list[str]


def run_photo_mvs(photo_paths: list[Path]) -> PhotoMvsResult:
    warnings: list[str] = []
    paths = [p for p in photo_paths if p.is_file()]
    if len(paths) < 2:
        return PhotoMvsResult(
            n_views=len(paths),
            n_triangulated=0,
            span_m=None,
            scale_sigma_rel=0.28,
            warnings=["photo_mvs: need ≥2 views for multi-view scale cue"],
        )

    try:
        import cv2
    except ImportError:
        warnings.append("photo_mvs: opencv unavailable")
        return PhotoMvsResult(len(paths), 0, None, 0.26, warnings)

    meta, _ = exif_summary(paths)
    k = intrinsics_matrix(meta, default_focal_px=800.0)
    orb = cv2.ORB_create(800)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    best_pts: np.ndarray | None = None
    best_inliers = 0

    subset = paths[: min(len(paths), 8)]
    for i in range(len(subset) - 1):
        pts3d, ninl = _pair_triangulate(cv2, orb, bf, subset[i], subset[i + 1], k)
        if ninl > best_inliers:
            best_inliers = ninl
            best_pts = pts3d

    if best_pts is None or best_pts.shape[0] < 8:
        warnings.append("photo_mvs: sparse reconstruction failed; wide scale σ")
        return PhotoMvsResult(len(paths), 0, None, 0.24, warnings)

    span = float(
        max(
            np.ptp(best_pts[:, 0]),
            np.ptp(best_pts[:, 1]),
            np.ptp(best_pts[:, 2]),
            0.01,
        )
    )
    rel = 0.12 + max(0, 40 - best_inliers) * 0.004
    rel = min(rel, 0.32)
    warnings.append(f"photo_mvs: {best_pts.shape[0]} sparse points, inliers≈{best_inliers}")
    return PhotoMvsResult(len(paths), int(best_pts.shape[0]), span, rel, warnings)


def _pair_triangulate(cv2, orb, bf, path_a: Path, path_b: Path, k: np.ndarray):
    im_a = _read_gray(cv2, path_a)
    im_b = _read_gray(cv2, path_b)
    if im_a is None or im_b is None:
        return None, 0

    kp1, des1 = orb.detectAndCompute(im_a, None)
    kp2, des2 = orb.detectAndCompute(im_b, None)
    if des1 is None or des2 is None or len(kp1) < 12 or len(kp2) < 12:
        return None, 0

    matches = bf.match(des1, des2)
    if len(matches) < 12:
        return None, 0
    matches = sorted(matches, key=lambda m: m.distance)[:200]
    pts1 = np.float32([kp1[m.queryIdx].pt for m in matches])
    pts2 = np.float32([kp2[m.trainIdx].pt for m in matches])

    e, mask = cv2.findEssentialMat(pts1, pts2, k, method=cv2.RANSAC, prob=0.999, threshold=1.5)
    if e is None or mask is None:
        return None, 0
    _, r, t, mask_pose = cv2.recoverPose(e, pts1, pts2, k, mask=mask)
    inliers = int(mask_pose.sum()) if mask_pose is not None else 0
    if inliers < 8:
        return None, inliers

    p1 = cv2.undistortPoints(pts1.reshape(-1, 1, 2), k, None)
    p2 = cv2.undistortPoints(pts2.reshape(-1, 1, 2), k, None)
    proj1 = np.hstack([np.eye(3), np.zeros((3, 1))])
    proj2 = np.hstack([r, t])
    homog = cv2.triangulatePoints(k @ proj1, k @ proj2, p1, p2)
    homog /= np.maximum(homog[3:4, :], 1e-9)
    pts3d = homog[:3, :].T
    valid = np.isfinite(pts3d).all(axis=1)
    pts3d = pts3d[valid]
    if pts3d.shape[0] < 8:
        return None, inliers
    return pts3d, inliers


def _read_gray(cv2, path: Path):
    try:
        data = path.read_bytes()
        if len(data) < 32:
            return None
        arr = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    except OSError:
        return None
