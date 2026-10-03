"""Offline RGB damage cues: mask geometry + wall/ceiling placement hints."""

from __future__ import annotations


def stain_hits(bgr, h: int, w_img: int) -> list[dict]:
    import cv2

    hits: list[dict] = []
    low = _stain_from_roi(bgr, h, w_img, y0_frac=0.32, y1_frac=1.0, surface="wall")
    if low:
        hits.append(low)
    high = _stain_from_roi(bgr, h, w_img, y0_frac=0.0, y1_frac=0.38, surface="ceiling")
    if high:
        hits.append(high)
    return hits


def crack_hit(bgr, h: int, w_img: int) -> dict | None:
    import cv2
    import numpy as np

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 180)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=60, minLineLength=int(h * 0.12), maxLineGap=12
    )
    if lines is None:
        return None
    best = None
    best_len = 0.0
    for line in lines[:40]:
        x1, y1, x2, y2 = line[0]
        length = float(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
        if length < best_len:
            continue
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        if dx < 8 or dy < 8:
            continue
        if abs(dx - dy) / max(dx, dy) < 0.25:
            best_len = length
            best = (x1, y1, x2, y2)
    if best is None:
        return None
    x1, y1, x2, y2 = best
    cx = (x1 + x2) / 2.0 / max(w_img, 1)
    cy = (y1 + y2) / 2.0 / max(h, 1)
    u0_frac = min(x1, x2) / max(w_img, 1)
    u1_frac = max(x1, x2) / max(w_img, 1)
    return {
        "class": "crack",
        "surface_type": "wall",
        "u_center_frac": cx,
        "u0_frac": max(0.0, u0_frac),
        "u1_frac": min(1.0, u1_frac),
        "bottom_above_floor_m": 0.35 + cy * 1.1,
        "area_m2": 0.05 + best_len / max(h, 1) * 0.1,
        "score": 0.54,
        "source": "hough_crack_heuristic_v2",
        "diagonal_from_opening": True,
    }


def _stain_from_roi(
    bgr,
    h: int,
    w_img: int,
    *,
    y0_frac: float,
    y1_frac: float,
    surface: str,
) -> dict | None:
    import cv2

    y0 = int(h * y0_frac)
    y1 = max(y0 + 8, int(h * y1_frac))
    roi = bgr[y0:y1, :]
    if roi.size == 0:
        return None
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (5, 40, 40), (25, 255, 200))
    mask = cv2.medianBlur(mask, 7)
    if int(mask.sum()) < 6000:
        return None
    ys, xs = mask.nonzero()
    if len(xs) == 0:
        return None
    x0, x1 = int(xs.min()), int(xs.max())
    y_max = int(ys.max()) + y0
    y_min = int(ys.min()) + y0
    cx = float(xs.mean()) / max(w_img, 1)
    u0_frac = x0 / max(w_img, 1)
    u1_frac = x1 / max(w_img, 1)
    wall_frac = max((x1 - x0) / max(w_img, 1), 0.05)
    area_m2 = 0.06 + wall_frac * 0.35 + (mask.sum() / 1.5e6)
    if surface == "ceiling":
        bottom_m = 2.0
        score = 0.5
        cls = "water_stain"
    else:
        bottom_m = 0.05 + (y_max / max(h, 1)) * 0.42
        score = 0.52
        cls = "water_stain"
    return {
        "class": cls,
        "surface_type": surface,
        "u_center_frac": cx,
        "u0_frac": u0_frac,
        "u1_frac": u1_frac,
        "bottom_above_floor_m": bottom_m,
        "area_m2": area_m2,
        "score": score,
        "source": "hsv_stain_heuristic_v2",
    }
