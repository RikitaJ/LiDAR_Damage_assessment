"""Stray Scanner export → CaptureFrames (verify conventions vs StrayRobots/scanner)."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from pipeline.config import InputTier
from pipeline.schema.capture_frames import CaptureFrame, CaptureFrames


def load_stray_capture(root: Path, capture_id: str | None = None) -> CaptureFrames:
    root = root.resolve()
    warnings: list[str] = []
    cid = capture_id or root.name

    K = _load_camera_matrix(root / "camera_matrix.csv")
    if K is None:
        warnings.append("missing or invalid camera_matrix.csv; using placeholder intrinsics")
        K = np.eye(3)

    depth_dir = root / "depth"
    conf_dir = root / "confidence"
    depth_index: dict[int, Path] = {}
    conf_index: dict[int, Path] = {}
    if depth_dir.is_dir():
        for p in sorted(depth_dir.glob("*.png")):
            try:
                depth_index[int(p.stem)] = p
            except ValueError:
                continue
    if conf_dir.is_dir():
        for p in sorted(conf_dir.glob("*.png")):
            try:
                conf_index[int(p.stem)] = p
            except ValueError:
                continue
    depth_count = len(depth_index)
    if depth_count == 0:
        warnings.append("missing depth/ frames; geometry uses camera path only (wide uncertainty)")

    rgb = root / "rgb.mp4"
    if not rgb.is_file():
        warnings.append("missing rgb.mp4")

    frames = _load_odometry(root / "odometry.csv", K, depth_index, conf_index, warnings)
    if not frames:
        warnings.append("no poses in odometry.csv")

    scale_sigma = 0.02 if depth_count > 0 else 0.15

    return CaptureFrames(
        tier=InputTier.LIDAR,
        capture_id=cid,
        device="Stray Scanner (device unknown)",
        gravity_aligned=True,
        scale_sigma_rel=scale_sigma,
        frames=frames,
        warnings=warnings,
        rgb_video_path=rgb if rgb.is_file() else None,
    )


def _load_camera_matrix(path: Path) -> np.ndarray | None:
    if not path.is_file():
        return None
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        parts = [float(x.strip()) for x in line.split(",") if x.strip()]
        if len(parts) == 3:
            rows.append(parts)
    if len(rows) != 3:
        return None
    return np.array(rows, dtype=float)


def _quat_to_matrix(qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    x, y, z, w = qx, qy, qz, qw
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0.0],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0.0],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def _load_odometry(
    path: Path,
    K: np.ndarray,
    depth_index: dict[int, Path],
    conf_index: dict[int, Path],
    warnings: list[str],
) -> list[CaptureFrame]:
    if not path.is_file():
        warnings.append(f"missing {path.name}")
        return []

    frames: list[CaptureFrame] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
            try:
                idx = int(str(row.get("frame", "")).strip())
                ts = float(row["timestamp"])
                tx, ty, tz = float(row["x"]), float(row["y"]), float(row["z"])
                T = _quat_to_matrix(
                    float(row["qx"]),
                    float(row["qy"]),
                    float(row["qz"]),
                    float(row["qw"]),
                )
                T[0:3, 3] = [tx, ty, tz]
                if row.get("fx") and row.get("fy"):
                    fx, fy = float(row["fx"]), float(row["fy"])
                    cx = float(row["cx"]) if row.get("cx") else K[0, 2]
                    cy = float(row["cy"]) if row.get("cy") else K[1, 2]
                    K_frame = K.copy()
                    K_frame[0, 0], K_frame[1, 1] = fx, fy
                    K_frame[0, 2], K_frame[1, 2] = cx, cy
                else:
                    K_frame = K.copy()
            except (KeyError, TypeError, ValueError):
                continue

            depth_p = depth_index.get(idx)
            conf_p = conf_index.get(idx)

            frames.append(
                CaptureFrame(
                    index=idx,
                    timestamp_s=ts,
                    image_path=None,
                    K=K_frame,
                    T_world_cam=T,
                    depth_path=depth_p,
                    confidence_path=conf_p,
                )
            )

    frames.sort(key=lambda fr: fr.index)
    matched = sum(1 for fr in frames if fr.depth_path)
    if depth_index and matched < len(frames) * 0.5:
        warnings.append(
            f"depth matched {matched}/{len(frames)} odometry frames; check frame indices"
        )
    return frames
