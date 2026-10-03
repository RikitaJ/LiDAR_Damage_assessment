"""Central 90% intervals on measurements (ASSESSMENT_BRIEF A7)."""

from __future__ import annotations

from pipeline.config import InputTier
from pipeline.measure.calibration import calibrated_sigma

INTERVAL_Z = 1.645
_DEFAULT_TIER = InputTier.LIDAR


def with_interval(
    value: float,
    sigma: float,
    *,
    notes: str = "",
    tier: InputTier | None = None,
    kind: str = "wall",
) -> dict:
    t = tier or _DEFAULT_TIER
    sig = calibrated_sigma(t, kind, float(sigma))
    half = INTERVAL_Z * max(sig, 1e-6)
    v = float(value)
    return {
        "value_m": v,
        "value": v,
        "lo": v - half,
        "hi": v + half,
        "confidence": {
            "sigma_m": sig,
            "tier_floor_m": sig,
            "notes": notes,
        },
    }
