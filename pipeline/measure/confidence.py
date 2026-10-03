from __future__ import annotations

from pipeline.config import InputTier, SIGMA
from pipeline.measure.intervals import with_interval


def m(value: float, tier: InputTier, kind: str = "length") -> dict:
    s = SIGMA[tier]
    sigma = {"opening": s.opening_m, "height": s.height_m}.get(kind, s.length_m)
    return with_interval(float(value), sigma, notes=f"{tier.value} tier")


def area_m2(value: float, tier: InputTier) -> dict:
    sigma = float(value) * SIGMA[tier].footprint_rel
    return with_interval(float(value), sigma, notes="footprint")
