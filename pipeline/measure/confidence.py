from __future__ import annotations

from pipeline.config import InputTier, SIGMA


def m(value: float, tier: InputTier, kind: str = "length") -> dict:
    s = SIGMA[tier]
    sigma = {"opening": s.opening_m, "height": s.height_m}.get(kind, s.length_m)
    return {
        "value_m": float(value),
        "confidence": {"sigma_m": sigma, "tier_floor_m": sigma, "notes": f"{tier.value} tier"},
    }


def area_m2(value: float, tier: InputTier) -> dict:
    sigma = value * SIGMA[tier].footprint_rel
    return {
        "value_m": float(value),
        "confidence": {"sigma_m": sigma, "tier_floor_m": sigma, "notes": "footprint"},
    }
