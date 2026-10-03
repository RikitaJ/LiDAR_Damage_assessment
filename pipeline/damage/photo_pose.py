"""Weak photo-tier pose hints from EXIF (horizontal spread + vertical placement)."""

from __future__ import annotations

import math
from pathlib import Path

from pipeline.config import InputTier
from pipeline.frontends.photo_exif import exif_summary


def enrich_hit_for_photo_tier(
    image_path: Path,
    hit: dict,
    room: dict,
    tier: InputTier,
) -> dict:
    if tier != InputTier.PHOTOS or hit.get("surface_type") == "ceiling":
        return hit
    meta, _ = exif_summary([image_path])
    row = _matching_row(meta, image_path.name)
    if not row:
        return hit

    width = float(row.get("width") or 1920)
    focal_px = _focal_px(row, width)
    if focal_px <= 0:
        return hit

    out = dict(hit)
    fov_h = 2.0 * math.atan(width / (2.0 * focal_px))
    # Assume ~2.5 m standoff; map image horizontal fraction to wall span along picked wall.
    standoff = 2.5
    visible_m = 2.0 * standoff * math.tan(fov_h / 2.0)
    wl = _max_wall_len(room)
    span_frac = min(visible_m / max(wl, 1.0), 0.85)

    u0, u1 = out.get("u0_frac"), out.get("u1_frac")
    if u0 is not None and u1 is not None:
        uc = (float(u0) + float(u1)) / 2.0
        half = (float(u1) - float(u0)) / 2.0
        half = min(half * (0.42 / max(focal_px / width, 0.25)), span_frac * 0.35)
        out["u0_frac"] = max(0.0, uc - half)
        out["u1_frac"] = min(1.0, uc + half)
    else:
        uc = float(out.get("u_center_frac", 0.4))
        half_img = min(0.12 * (900.0 / focal_px), span_frac * 0.22)
        out["u0_frac"] = max(0.0, uc - half_img)
        out["u1_frac"] = min(1.0, uc + half_img)

    v_center = out.get("v_center_frac")
    if v_center is None and u0 is not None:
        v_center = out.get("v0_frac")
    if v_center is not None:
        try:
            v = max(0.05, min(0.95, float(v_center)))
            ceil_m = float(room.get("ceiling_height_m", {}).get("value_m", 2.5))
            out["bottom_above_floor_m"] = max(0.08, min(ceil_m * 0.92, (1.0 - v) * ceil_m * 0.88))
        except (TypeError, ValueError):
            pass

    out["source"] = str(out.get("source", "")) + "+photo_exif"
    return out


def _matching_row(meta: dict, filename: str) -> dict | None:
    for row in meta.get("samples") or []:
        if row.get("file") == filename:
            return row
    samples = meta.get("samples") or []
    return samples[0] if samples else None


def _focal_px(row: dict, width: float) -> float:
    fl35 = row.get("FocalLengthIn35mmFilm")
    if fl35:
        return width * float(fl35) / 36.0
    fl = row.get("FocalLength")
    if fl:
        try:
            return float(fl) * 50.0
        except (TypeError, ValueError):
            pass
    return width * 0.48


def _max_wall_len(room: dict) -> float:
    best = 3.0
    for w in room.get("walls") or []:
        try:
            best = max(best, float(w.get("length_m", {}).get("value_m", 3.0)))
        except (TypeError, ValueError):
            continue
    return best
