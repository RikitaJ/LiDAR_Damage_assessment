"""Optional doorway feature check between adjacent room folders (brief §5.6)."""

from __future__ import annotations

from pathlib import Path

from pipeline.io.session import Session
from pipeline.frontends.photo_pick import pick_spaced_photos
from pipeline.tiers.photo_room_v0 import PHOTO_EXT


def verify_photo_adjacency(
    session: Session,
    edges: list[tuple[str, str, str]],
    *,
    min_inliers: int = 12,
) -> list[str]:
    if session.tier.value != "photos" or not edges:
        return []

    try:
        import cv2
    except ImportError:
        return ["photo: doorway verify skipped (opencv missing)"]

    by_id = {rp.room_id: rp.lidar_dir for rp in session.rooms}
    warnings: list[str] = []
    orb = cv2.ORB_create(600)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    for a, b, _oid in edges:
        pa = _photo_files(by_id.get(a))
        pb = _photo_files(by_id.get(b))
        if not pa or not pb:
            continue
        best = 0
        for ia in pick_spaced_photos(pa, 3):
            for ib in pick_spaced_photos(pb, 3):
                best = max(best, _match_inliers(cv2, orb, bf, ia, ib))
        if best < min_inliers:
            warnings.append(
                f"photo: weak doorway feature match {a}↔{b} ({best} inliers); check adjacency"
            )
    return warnings


def _photo_files(room_dir: Path | None) -> list[Path]:
    if room_dir is None or not room_dir.is_dir():
        return []
    photos = room_dir / "photos"
    root = photos if photos.is_dir() else room_dir
    return sorted(
        p for p in root.iterdir() if p.is_file() and p.suffix.lower() in PHOTO_EXT
    )


def _match_inliers(cv2, orb, bf, path_a: Path, path_b: Path) -> int:
    im_a = _gray(cv2, path_a)
    im_b = _gray(cv2, path_b)
    if im_a is None or im_b is None:
        return 0
    kp1, d1 = orb.detectAndCompute(im_a, None)
    kp2, d2 = orb.detectAndCompute(im_b, None)
    if d1 is None or d2 is None:
        return 0
    matches = bf.match(d1, d2)
    if len(matches) < 8:
        return len(matches)
    import numpy as np

    matches = sorted(matches, key=lambda m: m.distance)[:120]
    pts1 = np.float32([kp1[m.queryIdx].pt for m in matches])
    pts2 = np.float32([kp2[m.trainIdx].pt for m in matches])
    _, mask = cv2.findFundamentalMat(pts1, pts2, cv2.FM_RANSAC, 3.0, 0.99)
    if mask is None:
        return 0
    return int(mask.ravel().sum())


def _gray(cv2, path: Path):
    try:
        import numpy as np

        arr = np.frombuffer(path.read_bytes()[:2_000_000], dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    except OSError:
        return None
