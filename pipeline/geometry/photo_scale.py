"""Combine photo scale cues: still count, MVS, priors (brief §5.4)."""

from __future__ import annotations

from pipeline.frontends.photo_mvs import PhotoMvsResult
from pipeline.geometry.photo_priors import CEILING_PRIOR_M, photo_scale_sigma_rel, prior_warnings


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


def combined_scale_sigma_rel(
    n_photos: int,
    *,
    vlm_used: bool,
    ceiling_m: float,
    mvs: PhotoMvsResult,
    room_span_m: float,
    metric_cue_spread: float = 0.0,
) -> tuple[float, list[str]]:
    warnings = list(mvs.warnings)
    sigmas = [photo_scale_sigma_rel(n_photos, vlm_used=vlm_used)]

    if mvs.n_triangulated >= 12 and mvs.span_m and mvs.span_m > 0.05:
        ratio = room_span_m / mvs.span_m
        if ratio < 0.35 or ratio > 3.5:
            warnings.append(
                "photo: sparse MVS span disagrees with room prior; intervals widened"
            )
            sigmas.append(0.22)
        else:
            sigmas.append(mvs.scale_sigma_rel)

    if ceiling_m < CEILING_PRIOR_M[0] - 0.25 or ceiling_m > CEILING_PRIOR_M[1] + 0.35:
        sigmas.append(0.2)
    if metric_cue_spread > 0.12:
        sigmas.append(0.16 + metric_cue_spread * 0.5)
    warnings.extend(prior_warnings(ceiling_m))
    return min(0.38, max(sigmas)), warnings
