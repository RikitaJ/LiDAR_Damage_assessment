"""Combine photo scale cues: still count, MVS rescale, priors (brief §5.4)."""

from __future__ import annotations

import statistics

from pipeline.config import InputTier, SIGMA
from pipeline.frontends.photo_mvs import PhotoMvsResult
from pipeline.geometry.photo_priors import CEILING_PRIOR_M, photo_scale_sigma_rel, prior_warnings
from pipeline.measure.intervals import interval_notes, with_interval

MVS_RATIO_MIN = 0.38
MVS_RATIO_MAX = 3.2
MVS_MIN_TRIANGULATED = 12
MVS_APPLY_CLAMP = (0.72, 1.38)
MVS_VLM_FUSE_CLAMP = (0.82, 1.22)


def room_wall_span_m(room: dict) -> float:
    xs: list[float] = []
    zs: list[float] = []
    for w in room.get("walls", []):
        for p in w.get("polyline_m") or []:
            xs.append(float(p[0]))
            zs.append(float(p[1]))
    if not xs:
        return 3.5
    return max(max(xs) - min(xs), max(zs) - min(zs), 2.0)


def mvs_horizontal_scale(room_span_m: float, mvs: PhotoMvsResult) -> tuple[float | None, list[str]]:
    """Scale factor to multiply horizontal room dims so span aligns with sparse MVS."""
    warnings: list[str] = []
    if mvs.n_triangulated < MVS_MIN_TRIANGULATED or not mvs.span_m or mvs.span_m <= 0.05:
        return None, warnings
    factor = room_span_m / mvs.span_m
    if factor < MVS_RATIO_MIN or factor > MVS_RATIO_MAX:
        warnings.append("photo: sparse MVS span disagrees with room layout; scale not applied")
        return None, warnings
    clamped = max(MVS_APPLY_CLAMP[0], min(MVS_APPLY_CLAMP[1], factor))
    if abs(clamped - factor) > 0.02:
        warnings.append("photo: MVS scale clamped for stability")
    return clamped, warnings


def fuse_mvs_with_vlm_scale(mvs_scale: float) -> tuple[float, list[str]]:
    """When VLM layout exists, nudge toward MVS with median(1, mvs) — do not override fully."""
    warnings: list[str] = []
    fused = statistics.median([1.0, mvs_scale])
    fused = max(MVS_VLM_FUSE_CLAMP[0], min(MVS_VLM_FUSE_CLAMP[1], fused))
    if abs(fused - 1.0) >= 0.03:
        warnings.append(f"photo: MVS+VLM fused horizontal scale ×{fused:.3f}")
    if abs(mvs_scale - 1.0) >= 0.12 and abs(fused - 1.0) < 0.05:
        warnings.append("photo: MVS disagrees with VLM; kept VLM-dominant fuse")
    return fused, warnings


def apply_horizontal_scale_to_room(
    room: dict,
    scale: float,
    tier: InputTier,
    *,
    notes: str,
) -> None:
    if abs(scale - 1.0) < 0.02:
        return
    cx, cz = _room_centroid(room)
    for wall in room.get("walls", []):
        pl = wall.get("polyline_m") or []
        if len(pl) >= 2:
            wall["polyline_m"] = [
                [_scale_coord(float(p[0]), cx, scale), _scale_coord(float(p[1]), cz, scale)]
                for p in pl
            ]
        lm = wall.get("length_m") or {}
        v = float(lm.get("value_m", 0)) * scale
        wall["length_m"] = with_interval(
            v,
            max(float(lm.get("confidence", {}).get("sigma_m", SIGMA[tier].length_m)), v * 0.08),
            notes=f"{interval_notes(lm, notes)};{notes}",
            tier=tier,
            kind="wall",
        )
        for op in wall.get("openings") or []:
            wm = op.get("width_m") or {}
            try:
                wv = float(wm.get("value_m", 0.9)) * scale
                op["width_m"] = with_interval(
                    wv,
                    max(wv * 0.1, SIGMA[tier].opening_m),
                    notes=interval_notes(wm, notes),
                    tier=tier,
                    kind="opening",
                )
            except (TypeError, ValueError):
                continue
            if "anchor_m" in op:
                a = op["anchor_m"]
                op["anchor_m"] = [
                    _scale_coord(float(a[0]), cx, scale),
                    _scale_coord(float(a[1]), cz, scale),
                ]

    fa = room.get("floor_area_m2") or {}
    av = float(fa.get("value_m", 0)) * scale * scale
    room["floor_area_m2"] = with_interval(
        av,
        max(av * 0.12, SIGMA[tier].footprint_rel * av),
        notes=f"{interval_notes(fa, notes)};{notes}",
        tier=tier,
        kind="footprint",
    )


def combined_scale_sigma_rel(
    n_photos: int,
    *,
    vlm_used: bool,
    ceiling_m: float,
    mvs: PhotoMvsResult,
    room_span_m: float,
    metric_cue_spread: float = 0.0,
    mvs_scale_applied: bool = False,
    mvs_vlm_fused: bool = False,
) -> tuple[float, list[str]]:
    warnings = list(mvs.warnings)
    sigmas = [photo_scale_sigma_rel(n_photos, vlm_used=vlm_used)]

    if mvs.n_triangulated >= MVS_MIN_TRIANGULATED and mvs.span_m and mvs.span_m > 0.05:
        ratio = room_span_m / mvs.span_m
        if ratio < MVS_RATIO_MIN or ratio > MVS_RATIO_MAX:
            warnings.append(
                "photo: sparse MVS span disagrees with room prior; intervals widened"
            )
            sigmas.append(0.22)
        else:
            sigmas.append(mvs.scale_sigma_rel)
            if mvs_scale_applied:
                sigmas.append(max(mvs.scale_sigma_rel * 0.65, 0.08))
            if mvs_vlm_fused:
                sigmas.append(0.1)

    if ceiling_m < CEILING_PRIOR_M[0] - 0.25 or ceiling_m > CEILING_PRIOR_M[1] + 0.35:
        sigmas.append(0.2)
    if metric_cue_spread > 0.12:
        sigmas.append(0.16 + metric_cue_spread * 0.5)
    warnings.extend(prior_warnings(ceiling_m))
    return min(0.38, max(sigmas)), warnings


def _room_centroid(room: dict) -> tuple[float, float]:
    xs: list[float] = []
    zs: list[float] = []
    for w in room.get("walls", []):
        for p in w.get("polyline_m") or []:
            xs.append(float(p[0]))
            zs.append(float(p[1]))
    if not xs:
        return 0.0, 0.0
    return (min(xs) + max(xs)) / 2.0, (min(zs) + max(zs)) / 2.0


def _scale_coord(v: float, center: float, scale: float) -> float:
    return center + (v - center) * scale
