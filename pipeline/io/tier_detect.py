from __future__ import annotations

from enum import Enum
from pathlib import Path

from pipeline.config import InputTier


class CaptureKind(str, Enum):
    ROOMPLAN_MANIFEST = "roomplan_manifest"
    STRAY_SCANNER = "stray_scanner"
    VIDEO_ONLY = "video_only"
    UNKNOWN = "unknown"


def stray_scanner_root(capture_dir: Path) -> Path | None:
    """Return directory containing Stray Scanner files, or None."""
    capture_dir = capture_dir.resolve()
    if (capture_dir / "odometry.csv").is_file():
        return capture_dir
    for child in sorted(capture_dir.iterdir()):
        if child.is_dir() and (child / "odometry.csv").is_file():
            return child
    return None


def detect_capture_kind(capture_dir: Path) -> CaptureKind:
    capture_dir = capture_dir.resolve()
    if (capture_dir / "manifest.json").is_file():
        return CaptureKind.ROOMPLAN_MANIFEST
    if stray_scanner_root(capture_dir) is not None:
        return CaptureKind.STRAY_SCANNER
    from pipeline.frontends.video import find_video_file

    if find_video_file(capture_dir) is not None:
        return CaptureKind.VIDEO_ONLY
    return CaptureKind.UNKNOWN


def detect_tier(capture_dir: Path, override: InputTier | None = None) -> InputTier:
    if override is not None:
        return override
    kind = detect_capture_kind(capture_dir)
    if kind == CaptureKind.VIDEO_ONLY:
        return InputTier.VIDEO
    if kind == CaptureKind.STRAY_SCANNER:
        return InputTier.LIDAR
    if kind == CaptureKind.ROOMPLAN_MANIFEST:
        return InputTier.LIDAR
    return InputTier.LIDAR
