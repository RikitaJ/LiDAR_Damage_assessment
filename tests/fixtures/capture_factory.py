"""Synthetic captures for pytest only — not user-facing sample data."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
from PIL import Image

LIDAR_TWO_ROOM = Path(__file__).resolve().parent / "lidar_two_room"


def copy_lidar_two_room(dest: Path) -> Path:
    dest = dest.resolve()
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(LIDAR_TWO_ROOM, dest)
    return dest


def ground_truth_json() -> Path:
    return LIDAR_TWO_ROOM / "ground_truth.json"


def write_mini_stray_capture(root: Path, *, n_frames: int = 4) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "camera_matrix.csv").write_text(
        "500.0, 0.0, 16.0\n0.0, 500.0, 16.0\n0.0, 0.0, 1.0\n",
        encoding="utf-8",
    )
    depth_dir = root / "depth"
    conf_dir = root / "confidence"
    depth_dir.mkdir()
    conf_dir.mkdir()
    depth = np.zeros((48, 48), dtype=np.uint16)
    depth[6:42, 6:42] = 2800
    depth[20:28, 6:42] = 0
    conf = np.full((48, 48), 2, dtype=np.uint8)
    for i in range(n_frames):
        Image.fromarray(depth).save(depth_dir / f"{i:06d}.png")
        Image.fromarray(conf).save(conf_dir / f"{i:06d}.png")
    (root / "odometry.csv").write_text(
        "timestamp,frame,x,y,z,qx,qy,qz,qw\n"
        + "\n".join(f"{1+i}.0,{i},{i * 0.05},0,0,0,0,0,1" for i in range(n_frames))
        + "\n",
        encoding="utf-8",
    )


def write_mini_video_capture(root: Path) -> None:
    import cv2

    root.mkdir(parents=True, exist_ok=True)
    path = root / "walkthrough.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 10.0, (64, 64))
    if not writer.isOpened():
        raise RuntimeError("opencv VideoWriter failed (fixture mp4)")
    for i in range(8):
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        frame[:, :, 0] = min(255, i * 30)
        writer.write(frame)
    writer.release()
