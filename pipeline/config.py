from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "floorplan_output.schema.json"


class InputTier(str, Enum):
    LIDAR = "lidar"
    VIDEO = "video"
    PHOTOS = "photos"


@dataclass(frozen=True)
class TierSigma:
    length_m: float
    opening_m: float
    height_m: float
    footprint_rel: float


SIGMA = {
    InputTier.LIDAR: TierSigma(0.008, 0.015, 0.012, 0.01),
    InputTier.VIDEO: TierSigma(0.025, 0.03, 0.025, 0.03),
    InputTier.PHOTOS: TierSigma(0.06, 0.08, 0.05, 0.08),
}


@dataclass
class RunConfig:
    tier: InputTier = InputTier.LIDAR
    loop_closure: bool = True
    drift_correction: bool = True
