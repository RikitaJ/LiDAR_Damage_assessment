"""Canonical intermediate between tier front-ends and geometry (ASSESSMENT_BRIEF §5.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import InputTier


@dataclass
class CaptureFrame:
    index: int
    timestamp_s: float
    image_path: Path | None
    K: np.ndarray
    T_world_cam: np.ndarray
    depth_path: Path | None = None
    confidence_path: Path | None = None


@dataclass
class CaptureFrames:
    tier: InputTier
    capture_id: str
    device: str
    gravity_aligned: bool
    scale_sigma_rel: float
    frames: list[CaptureFrame] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rgb_video_path: Path | None = None

    def to_meta(self) -> dict[str, Any]:
        return {
            "tier": self.tier.value,
            "capture_id": self.capture_id,
            "device": self.device,
            "gravity_aligned": self.gravity_aligned,
            "scale_sigma_rel": self.scale_sigma_rel,
            "frame_count": len(self.frames),
            "warnings": list(self.warnings),
        }
