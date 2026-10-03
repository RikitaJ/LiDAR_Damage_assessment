"""Damage pipeline edge-case sanitization (brief rule 5 — warn, never crash)."""

from __future__ import annotations

import math

from pipeline.config import InputTier, SIGMA
from pipeline.measure.intervals import with_interval

_ALLOWED_CLASSES = frozenset({"water_stain", "crack", "mold"})


def valid_hit(hit: dict) -> bool:
    if not isinstance(hit, dict):
        return False
    if hit.get("class") not in _ALLOWED_CLASSES:
        return False
    try:
        float(hit.get("u_center_frac", 0.5))
        float(hit.get("area_m2", 0.1))
        float(hit.get("score", 0.4))
    except (TypeError, ValueError):
        return False
    return True


def filter_hits(hits: list[dict]) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    out: list[dict] = []
    for i, hit in enumerate(hits):
        if valid_hit(hit):
            out.append(hit)
        else:
            warnings.append(f"damage: dropped invalid cached hit #{i + 1}")
    return out, warnings


def sanitize_damage_regions(regions: list[dict], tier: InputTier) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    clean: list[dict] = []
    for reg in regions:
        fixed, w = _sanitize_one(reg, tier)
        warnings.extend(w)
        if fixed:
            clean.append(fixed)
    return clean, warnings


def apply_r39_surface_review(regions: list[dict], qa_warnings: list[str]) -> list[str]:
    """Down-rank damage confidence when mirror/glass QA is active (R39)."""
    extra: list[str] = []
    if not _r39_active(qa_warnings):
        return extra
    extra.append("damage: R39 mirror/glass — damage regions marked for manual review")
    for reg in regions:
        reg["surface_review"] = "r39_mirror_glass"
        reg["score"] = min(float(reg.get("score", 0.5)), 0.32)
        for key in ("area_m2", "width_m", "height_m", "bottom_above_floor_m"):
            field = reg.get(key)
            if isinstance(field, dict):
                conf = dict(field.get("confidence") or {})
                sig = float(conf.get("sigma_m", 0.08)) * 1.5
                v = float(field.get("value_m", field.get("value", 0)))
                half = 1.645 * max(sig, 1e-6)
                notes = str(conf.get("notes") or "")
                if "r39_widen" not in notes:
                    notes = (notes + "; r39_widen").strip("; ")
                reg[key] = {
                    **field,
                    "lo": v - half,
                    "hi": v + half,
                    "confidence": {**conf, "sigma_m": sig, "tier_floor_m": sig, "notes": notes},
                }
    return extra


def _r39_active(qa_warnings: list[str]) -> bool:
    for w in qa_warnings:
        low = w.lower()
        if "r39" in low or "mirror" in low or "glass" in low:
            return True
    return False


def _sanitize_one(reg: dict, tier: InputTier) -> tuple[dict | None, list[str]]:
    warnings: list[str] = []
    cls = reg.get("class")
    if cls not in _ALLOWED_CLASSES:
        warnings.append(f"damage: dropped region {reg.get('id')} unknown class {cls!r}")
        return None, warnings
    sid = str(reg.get("surface_id") or "").strip()
    if not sid:
        warnings.append(f"damage: dropped region {reg.get('id')} missing surface_id")
        return None, warnings
    poly = reg.get("polygon_surface")
    if not isinstance(poly, list) or len(poly) < 3:
        warnings.append(f"damage: dropped region {reg.get('id')} invalid polygon")
        return None, warnings
    fixed_poly: list[list[float]] = []
    for pt in poly:
        try:
            fixed_poly.append([float(pt[0]), float(pt[1])])
        except (TypeError, ValueError, IndexError):
            warnings.append(f"damage: dropped region {reg.get('id')} bad polygon point")
            return None, warnings
    out = dict(reg)
    out["polygon_surface"] = fixed_poly
    out["class"] = cls
    out["surface_id"] = sid
    for key, kind in (
        ("area_m2", "footprint"),
        ("width_m", "wall"),
        ("height_m", "height"),
        ("bottom_above_floor_m", "height"),
    ):
        out[key] = _ensure_interval(out.get(key), tier=tier, kind=kind, notes=str(out.get("source", "damage")))
    try:
        sc = float(out.get("score", 0.4))
        if math.isnan(sc) or math.isinf(sc):
            sc = 0.4
        out["score"] = max(0.0, min(sc, 1.0))
    except (TypeError, ValueError):
        out["score"] = 0.4
    return out, warnings


def _ensure_interval(field, *, tier: InputTier, kind: str, notes: str) -> dict:
    if isinstance(field, dict) and "value_m" in field:
        try:
            v = float(field["value_m"])
            if math.isnan(v) or math.isinf(v) or v <= 0:
                raise ValueError("bad value")
            return field
        except (TypeError, ValueError):
            pass
    try:
        v = float(field) if field is not None else 0.05
    except (TypeError, ValueError):
        v = 0.05
    v = max(v, 0.01)
    sig = max(v * 0.35, SIGMA[tier].footprint_rel)
    return with_interval(v, sig, notes=notes, tier=tier, kind=kind)
