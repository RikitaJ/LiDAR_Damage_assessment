"""Load global calibration multipliers (brief § eval — pipeline never reads GT)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pipeline.config import InputTier

ROOT = Path(__file__).resolve().parents[2]
CAL_PATH = ROOT / "configs" / "calibration.json"


@lru_cache(maxsize=1)
def _data() -> dict:
    if not CAL_PATH.is_file():
        return {"multipliers": {}}
    return json.loads(CAL_PATH.read_text(encoding="utf-8"))


def sigma_multiplier(tier: InputTier, kind: str) -> float:
    mults = _data().get("multipliers", {}).get(tier.value, {})
    k = float(mults.get(kind, 1.0))
    return max(k, 0.5)


def calibrated_sigma(tier: InputTier, kind: str, sigma: float) -> float:
    return float(sigma) * sigma_multiplier(tier, kind)
