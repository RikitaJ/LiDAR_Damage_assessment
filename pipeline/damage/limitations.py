"""Explicit Phase 5 capability limits (brief §5.8 vs v1) for JSON + reports."""

from __future__ import annotations

from pathlib import Path

from pipeline.config import InputTier
from pipeline.damage.detect import count_rgb_samples

# Static gaps vs target architecture (always disclosed on every run).
STATIC_LIMITATIONS: tuple[str, ...] = (
    "damage_v7: fast SAM-family refine (HSV crop + optional MobileSAM); optional Azure Vision / damage VLM",
    "damage_v7: mask bbox → wall UV via camera rays (EXIF/ordinal pose sync + unix odometry match; else EXIF standoff)",
    "damage_v2: multi-frame merge is 2D UV IoU on surface, not mask fusion in 3D",
    "damage_v2: CD-03 (wet-room adjacency) fires only when room names or manifest adjacency imply bath/kitchen",
    "damage_v2: per-image cues cached under .cache/damage/ (detector version pinned)",
)

_HEURISTIC_SOURCES = frozenset(
    {
        "hsv_stain_heuristic_v1",
        "hsv_stain_heuristic_v2",
        "hough_crack_heuristic_v1",
        "hough_crack_heuristic_v2",
        "azure_vision_optional",
    }
)


def collect_damage_limitations(
    *,
    tier: InputTier,
    capture_root: Path,
    rooms: list[dict],
    damage_regions: list[dict],
    scope_items: list[dict],
    qa_warnings: list[str],
) -> list[str]:
    out = list(STATIC_LIMITATIONS)
    rgb_n = count_rgb_samples(capture_root, rooms)
    if rgb_n == 0:
        out.append("damage_v2: no RGB stills in capture — damage_regions[] empty; scope from damage disabled")
    elif rgb_n < 2:
        out.append(f"damage_v2: only {rgb_n} RGB sample(s); limited multi-view merge")

    if damage_regions and all(r.get("source") in _HEURISTIC_SOURCES for r in damage_regions):
        out.append("damage_v2: all damage regions are provisional hints — extents widened, not field quantities")
    if any(r.get("class") == "crack" and not r.get("diagonal_from_opening") for r in damage_regions):
        out.append("damage_v2: crack present without opening-corner geometry — CD-05 may not fire")

    if scope_items and damage_regions:
        if all(_is_heuristic_source(r.get("source", "")) for r in damage_regions):
            out.append("damage_v2: scope quantities are rule-derived from provisional damage, not verified repair takeoff")

    if tier == InputTier.PHOTOS:
        out.append("damage_v7: photo tier uses VLM door-wall hint + EXIF standoff (no per-still pose file)")
    if any("mirror" in w.lower() or "glass" in w.lower() or "r39" in w.lower() for w in qa_warnings):
        out.append("damage_v2: mirror/glass QA active — do not trust damage extent on affected surfaces (R39)")

    return out


def _is_heuristic_source(source: str) -> bool:
    if "merge_v2" in source or "mobile_sam_v1" in source or "camera_proj_v1" in source:
        return False
    if "sam_fast_hsv_v1" in source and "azure_damage" in source:
        return False
    base = source.split("+")[0]
    if "azure_damage_vlm" in source:
        return False
    return base in _HEURISTIC_SOURCES or source.startswith("azure_vision")


def widen_heuristic_regions(regions: list[dict], *, factor: float = 1.75) -> None:
    for r in regions:
        src = str(r.get("source", ""))
        if "merge_v2" in src:
            continue
        if not _is_heuristic_source(src):
            continue
        widen = 1.35 if float(r.get("score", 0)) >= 0.68 and "vision_fused" in src else factor
        for key in ("area_m2", "width_m", "height_m", "bottom_above_floor_m"):
            field = r.get(key)
            if isinstance(field, dict):
                r[key] = _widen_field(field, factor=widen)


def _widen_field(field: dict, *, factor: float) -> dict:
    conf = dict(field.get("confidence") or {})
    sig = float(conf.get("sigma_m", 0.08)) * factor
    v = float(field.get("value_m", field.get("value", 0.0)))
    half = 1.645 * max(sig, 1e-6)
    notes = str(conf.get("notes") or "")
    if "heuristic_widen" not in notes:
        notes = (notes + "; heuristic_widen").strip("; ")
    return {
        **field,
        "value_m": v,
        "value": v,
        "lo": v - half,
        "hi": v + half,
        "confidence": {**conf, "sigma_m": sig, "tier_floor_m": sig, "notes": notes},
    }
