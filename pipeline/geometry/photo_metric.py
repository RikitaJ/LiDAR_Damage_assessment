"""Metric rescale + geometry consistency for photo tier (brief §5.4)."""

from __future__ import annotations

import statistics
from typing import Any

from pipeline.geometry.photo_priors import CEILING_PRIOR_M, DOOR_HEIGHT_PRIOR_M

DOOR_REF_M = (DOOR_HEIGHT_PRIOR_M[0] + DOOR_HEIGHT_PRIOR_M[1]) / 2.0
CEILING_REF_M = (CEILING_PRIOR_M[0] + CEILING_PRIOR_M[1]) / 2.0
MAX_ROOM_DIM_M = 18.0
MIN_ROOM_DIM_M = 2.0
MAX_FLOOR_AREA_M2 = 85.0


def merge_vlm_estimates(estimates: list[dict]) -> dict | None:
    """Robust median merge of several VLM JSON payloads."""
    good = [e for e in estimates if _valid_core(e)]
    if not good:
        return None
    if len(good) == 1:
        return good[0]

    areas = [_f(e["floor_area_m2"]) for e in good]
    ceils = [_f(e.get("ceiling_height_m") or CEILING_REF_M) for e in good]
    lens_lists = [_lengths(e) for e in good]
    n = min(len(x) for x in lens_lists)
    merged_lens = [
        statistics.median([lst[i] for lst in lens_lists if len(lst) > i]) for i in range(n)
    ]

    out: dict[str, Any] = {
        "floor_area_m2": statistics.median(areas),
        "ceiling_height_m": statistics.median(ceils),
        "wall_lengths_m": merged_lens,
    }
    openings = [e.get("openings") for e in good if isinstance(e.get("openings"), list)]
    if openings:
        out["openings"] = max(openings, key=len)
    for key in ("door_height_m", "main_door_image_height_fraction", "door_on_wall", "door_width_m"):
        vals = [e.get(key) for e in good if e.get(key) is not None]
        if vals:
            try:
                out[key] = statistics.median([float(v) for v in vals])
            except (TypeError, ValueError):
                pass
    return out


def prior_metric_scale(est: dict) -> tuple[float, float, list[str]]:
    """
    Uniform scale for horizontal dimensions from door/ceiling cues.
    Returns (scale, cue_spread_rel, warnings).
    """
    warnings: list[str] = []
    scales: list[float] = []

    dh = _optional_float(est.get("door_height_m"))
    if dh and 1.45 <= dh <= 2.35:
        scales.append(DOOR_REF_M / dh)

    frac = _optional_float(est.get("main_door_image_height_fraction"))
    ceil = _optional_float(est.get("ceiling_height_m"))
    if frac and ceil and 0.06 <= frac <= 0.65 and 1.9 <= ceil <= 3.6:
        implied_door = ceil * frac
        if 1.35 <= implied_door <= 2.45:
            scales.append(DOOR_REF_M / implied_door)

    if not scales:
        return 1.0, 0.0, warnings

    spread = (max(scales) - min(scales)) / max(statistics.mean(scales), 1e-6)
    s = statistics.median(scales)
    s = max(0.72, min(1.38, s))
    if abs(s - 1.0) >= 0.04:
        warnings.append(f"photo: prior metric scale ×{s:.3f} from door/ceiling cues")
    if spread > 0.12:
        warnings.append("photo: scale cues disagree; intervals widened")
    return s, spread, warnings


def apply_metric_to_estimate(est: dict, scale: float) -> dict:
    out = dict(est)
    if scale == 1.0:
        return out
    try:
        out["floor_area_m2"] = float(est["floor_area_m2"]) * scale * scale
    except (TypeError, ValueError, KeyError):
        pass
    lens = _lengths(est)
    if lens:
        out["wall_lengths_m"] = [float(x) * scale for x in lens]
    for op in out.get("openings") or []:
        if isinstance(op, dict) and op.get("width_m") is not None:
            try:
                op["width_m"] = float(op["width_m"]) * scale
            except (TypeError, ValueError):
                pass
    dw = out.get("door_width_m")
    if dw is not None:
        try:
            out["door_width_m"] = float(dw) * scale
        except (TypeError, ValueError):
            pass
    return out


def refine_rectangle_lengths(
    lengths_m: list[float],
    *,
    target_area_m2: float | None,
) -> list[float]:
    """Opposite walls equal + optional area fit (Manhattan rectangle)."""
    if len(lengths_m) < 4:
        return lengths_m
    a, b, c, d = (max(float(x), MIN_ROOM_DIM_M) for x in lengths_m[:4])
    a = c = (a + c) / 2.0
    b = d = (b + d) / 2.0
    if target_area_m2 and target_area_m2 > 4.0:
        cur = a * b
        if cur > 1.0:
            k = (target_area_m2 / cur) ** 0.5
            a *= k
            b *= k
            c, d = a, b
    a = _clamp_dim(a)
    b = _clamp_dim(b)
    return [a, b, c, d]


def apply_aspect_ratio_hint(
    lengths_m: list[float],
    aspect_long_over_short: float | None,
) -> tuple[list[float], list[str]]:
    """Adjust rectangle sides toward vanishing-point aspect (long/short ≥ 1)."""
    warnings: list[str] = []
    if not aspect_long_over_short or len(lengths_m) < 4 or aspect_long_over_short <= 0:
        return lengths_m, warnings
    r = max(aspect_long_over_short, 1.0)
    a, b, c, d = refine_rectangle_lengths(lengths_m, target_area_m2=None)
    cur = max(a, b) / max(min(a, b), 0.1)
    if abs(cur - r) / r < 0.12:
        return [a, b, c, d], warnings
    geo_mean = (a * b) ** 0.5
    if r >= 1.0:
        long_side = geo_mean * (r**0.5)
        short_side = geo_mean / (r**0.5)
    else:
        long_side, short_side = b, a
    long_side = _clamp_dim(long_side)
    short_side = _clamp_dim(short_side)
    warnings.append(f"photo: aspect hint adjusted sides toward {r:.2f}:1")
    return [long_side, short_side, long_side, short_side], warnings


def reject_implausible_estimate(est: dict) -> tuple[bool, str]:
    if not _valid_core(est):
        return False, "missing core fields"
    area = _f(est["floor_area_m2"])
    lens = _lengths(est)
    if area > MAX_FLOOR_AREA_M2:
        return False, f"floor area {area:.1f} m² implausible"
    if max(lens, default=0) > MAX_ROOM_DIM_M:
        return False, "wall length implausible"
    if min(lens, default=0) < MIN_ROOM_DIM_M - 0.5:
        return False, "wall length too small"
    ceil = _optional_float(est.get("ceiling_height_m"))
    if ceil and (ceil < 1.6 or ceil > 4.5):
        return False, "ceiling height implausible"
    return True, ""


def _valid_core(est: dict) -> bool:
    try:
        area = float(est["floor_area_m2"])
        lens = est.get("wall_lengths_m") or []
        return area > 2.0 and isinstance(lens, list) and len(lens) >= 4
    except (KeyError, TypeError, ValueError):
        return False


def _lengths(est: dict) -> list[float]:
    raw = est.get("wall_lengths_m") or []
    out: list[float] = []
    for x in raw:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            continue
    return out


def _f(val: Any) -> float:
    return float(val)


def _optional_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _clamp_dim(x: float) -> float:
    return max(MIN_ROOM_DIM_M, min(x, MAX_ROOM_DIM_M))
