"""Central 90% intervals on measurements (ASSESSMENT_BRIEF A7)."""

from __future__ import annotations

INTERVAL_Z = 1.645


def with_interval(value: float, sigma: float, *, notes: str = "") -> dict:
    half = INTERVAL_Z * max(float(sigma), 1e-6)
    v = float(value)
    return {
        "value_m": v,
        "value": v,
        "lo": v - half,
        "hi": v + half,
        "confidence": {
            "sigma_m": float(sigma),
            "tier_floor_m": float(sigma),
            "notes": notes,
        },
    }
