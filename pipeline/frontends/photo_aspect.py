"""Room aspect ratio hint from dominant orthogonal lines (offline)."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def median_aspect_long_over_short(photo_paths: list[Path], *, max_images: int = 4) -> tuple[float | None, list[str]]:
    warnings: list[str] = []
    try:
        import cv2
    except ImportError:
        return None, warnings

    ratios: list[float] = []
    for path in photo_paths[:max_images]:
        r = _aspect_from_image(cv2, path)
        if r is not None:
            ratios.append(r)

    if not ratios:
        return None, warnings
    med = float(np.median(ratios))
    med = max(1.0, min(med, 3.5))
    warnings.append(f"photo_aspect: median line aspect hint {med:.2f}:1")
    return med, warnings


def _aspect_from_image(cv2, path: Path) -> float | None:
    try:
        buf = np.frombuffer(path.read_bytes()[:2_500_000], dtype=np.uint8)
        gray = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    except OSError:
        return None
    if gray is None or gray.size == 0:
        return None
    h, w = gray.shape[:2]
    scale = 480.0 / max(h, w)
    if scale < 1.0:
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)))

    edges = cv2.Canny(gray, 60, 180)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60, minLineLength=40, maxLineGap=12)
    if lines is None:
        return None

    horiz, vert = 0.0, 0.0
    for seg in lines:
        x1, y1, x2, y2 = seg[0]
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        length = float((dx * dx + dy * dy) ** 0.5)
        if length < 20:
            continue
        if dx > dy * 1.8:
            horiz += length
        elif dy > dx * 1.8:
            vert += length

    if horiz < 1 or vert < 1:
        return None
    return max(horiz, vert) / min(horiz, vert)
