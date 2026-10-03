"""Voxel downsample for fused point clouds."""

from __future__ import annotations

import numpy as np

VOXEL_M = 0.018


def voxel_downsample(pts: np.ndarray, voxel_m: float = VOXEL_M) -> np.ndarray:
    if len(pts) <= 80_000:
        return pts
    keys = np.floor(pts / voxel_m).astype(np.int64)
    _, idx = np.unique(keys, axis=0, return_index=True)
    return pts[np.sort(idx)]
