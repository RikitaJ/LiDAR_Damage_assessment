"""Pose/intrinsics lookup for damage projection (only when capture has poses)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from pipeline.config import InputTier
from pipeline.frontends.photo_exif import image_timestamp_s
from pipeline.schema.capture_frames import CaptureFrame


@dataclass
class DamageViewContext:
    tier: InputTier
    frames: list[CaptureFrame] = field(default_factory=list)
    image_time_rank: dict[str, float] = field(default_factory=dict)


def build_view_context(capture_root: Path, tier: InputTier, *, rgb_paths: list[Path] | None = None) -> DamageViewContext:
    root = capture_root.resolve()
    ranks = _rank_images(rgb_paths or [])
    if tier == InputTier.PHOTOS:
        return DamageViewContext(tier=tier, image_time_rank=ranks)
    if tier == InputTier.VIDEO:
        from pipeline.frontends.video import find_video_file, load_video_capture

        if find_video_file(root) is None:
            return DamageViewContext(tier=tier, image_time_rank=ranks)
        cf = load_video_capture(root)
        return DamageViewContext(tier=tier, frames=list(cf.frames), image_time_rank=ranks)
    if tier == InputTier.LIDAR and (root / "odometry.csv").is_file():
        from pipeline.frontends.stray_lidar import load_stray_capture

        cf = load_stray_capture(root)
        return DamageViewContext(tier=tier, frames=list(cf.frames), image_time_rank=ranks)
    return DamageViewContext(tier=tier, image_time_rank=ranks)


def frame_for_image(ctx: DamageViewContext, image_path: Path | str) -> CaptureFrame | None:
    if not ctx.frames:
        return None
    path = Path(image_path)
    name = path.name
    slot = _video_extract_slot(name)
    if slot is not None:
        n = max(_max_extract_slot(name) + 1, 1)
        idx = int((slot + 0.5) / n * len(ctx.frames))
        return ctx.frames[min(max(idx, 0), len(ctx.frames) - 1)]

    rank = _path_rank(ctx, path)
    if rank is not None:
        idx = int(rank * (len(ctx.frames) - 1))
        return ctx.frames[min(max(idx, 0), len(ctx.frames) - 1)]

    synced = _nearest_odometry_by_unix(path, ctx.frames)
    if synced is not None:
        return synced
    return None


def intrinsics_for_image(image_path: Path | str, frame: CaptureFrame | None) -> np.ndarray:
    if frame is not None:
        return frame.K.copy()
    from pipeline.frontends.photo_exif import exif_summary, intrinsics_matrix

    p = Path(image_path)
    if not p.is_file() or p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".heic"}:
        w = 640.0
        return intrinsics_matrix({"samples": [{"width": w, "height": 480}]}, default_focal_px=0.9 * w)
    meta, _ = exif_summary([p])
    row = (meta.get("samples") or [{}])[0]
    w = float(row.get("width") or 1920)
    return intrinsics_matrix(meta, default_focal_px=0.9 * max(w, 1080.0))


def _rank_images(paths: list[Path]) -> dict[str, float]:
    if len(paths) < 2:
        return {}
    timed: list[tuple[str, float]] = []
    for p in paths:
        if not p.is_file():
            continue
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        t = image_timestamp_s(p)
        if t is None:
            continue
        timed.append((key, t))
    if len(timed) < 2:
        return {}
    timed.sort(key=lambda x: x[1])
    t0, t1 = timed[0][1], timed[-1][1]
    span = max(t1 - t0, 1e-3)
    out: dict[str, float] = {}
    for k, t in timed:
        r = (t - t0) / span
        out[k] = r
        out[Path(k).name] = r
    return out


def _path_rank(ctx: DamageViewContext, path: Path) -> float | None:
    for key in (path.name, str(path)):
        if key in ctx.image_time_rank:
            return ctx.image_time_rank[key]
    try:
        resolved = str(path.resolve())
        return ctx.image_time_rank.get(resolved)
    except OSError:
        return None


def _nearest_odometry_by_unix(path: Path, frames: list[CaptureFrame]) -> CaptureFrame | None:
    t_img = image_timestamp_s(path)
    if t_img is None or t_img < 1e8:
        return None
    odom = [f.timestamp_s for f in frames]
    if not odom or min(odom) < 1e8:
        return None
    return min(frames, key=lambda f: abs(f.timestamp_s - t_img))


def _video_extract_slot(name: str) -> int | None:
    m = re.search(r"housefloor_damage_.*_(\d+)\.jpg$", name, re.I)
    return int(m.group(1)) if m else None


def _max_extract_slot(name: str) -> int:
    m = re.search(r"housefloor_damage_.*_(\d+)\.jpg$", name, re.I)
    return int(m.group(1)) if m else 0
