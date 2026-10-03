"""Video walkthrough → CaptureFrames (Phase 3 v0: keyframes + visual-motion poses)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from pipeline.config import InputTier
from pipeline.schema.capture_frames import CaptureFrame, CaptureFrames

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore


VIDEO_NAMES = ("walkthrough.mp4", "walkthrough.mov", "video.mp4", "rgb.mp4", "capture.mp4")


def find_video_file(root: Path) -> Path | None:
    root = root.resolve()
    for name in VIDEO_NAMES:
        p = root / name
        if p.is_file():
            return p
    for ext in ("*.mp4", "*.mov", "*.MP4", "*.MOV"):
        hits = sorted(root.glob(ext))
        if hits:
            return hits[0]
    return None


def load_video_capture(root: Path, capture_id: str | None = None) -> CaptureFrames:
    root = root.resolve()
    warnings: list[str] = []
    cid = capture_id or root.name
    video = find_video_file(root)
    if video is None:
        warnings.append("no video file found")
        return CaptureFrames(
            tier=InputTier.VIDEO,
            capture_id=cid,
            device="video capture (unknown device)",
            gravity_aligned=False,
            scale_sigma_rel=0.25,
            frames=[],
            warnings=warnings,
        )

    if cv2 is None:
        warnings.append("opencv not installed; pip install opencv-python-headless")
        return CaptureFrames(
            tier=InputTier.VIDEO,
            capture_id=cid,
            device="video capture",
            gravity_aligned=False,
            scale_sigma_rel=0.25,
            frames=[],
            warnings=warnings,
            rgb_video_path=video,
        )

    meta = _probe_video_meta(video)
    if meta:
        warnings.extend(meta.get("warnings", []))

    keyframes = _extract_keyframes(video, target_fps=2.0, min_blur_var=80.0, warnings=warnings)
    if len(keyframes) < 3:
        warnings.append("too few sharp keyframes; widen all intervals")

    K = _default_intrinsics(keyframes[0]["width"], keyframes[0]["height"]) if keyframes else np.eye(3)
    frames = _poses_from_keyframes(keyframes, K)

    return CaptureFrames(
        tier=InputTier.VIDEO,
        capture_id=cid,
        device="video capture",
        gravity_aligned=False,
        scale_sigma_rel=0.22 if len(frames) >= 8 else 0.35,
        frames=frames,
        warnings=warnings,
        rgb_video_path=video,
    )


def _probe_video_meta(video: Path) -> dict | None:
    if cv2 is None:
        return None
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return {"warnings": [f"cannot open video: {video.name}"]}
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    w: list[str] = []
    if fps < 15:
        w.append("R39: low frame rate; tracking may be poor")
    if n < 30:
        w.append("R39: very short clip; layout uncertainty high")
    return {"warnings": w}


def _extract_keyframes(
    video: Path,
    *,
    target_fps: float,
    min_blur_var: float,
    warnings: list[str],
) -> list[dict]:
    assert cv2 is not None
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        warnings.append(f"failed to open {video.name}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps / target_fps)))
    out: list[dict] = []
    idx = 0
    kept = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if var >= min_blur_var:
                h, w = gray.shape
                out.append({"index": kept, "timestamp_s": idx / fps, "width": w, "height": h, "gray": gray})
                kept += 1
        idx += 1
    cap.release()
    if kept < idx / step * 0.3:
        warnings.append("R39: many blurry frames dropped (motion or low light)")
    return out


def _default_intrinsics(width: int, height: int) -> np.ndarray:
    f = 0.9 * max(width, height)
    return np.array([[f, 0, width / 2], [0, f, height / 2], [0, 0, 1]], dtype=float)


def _poses_from_keyframes(keyframes: list[dict], K: np.ndarray) -> list[CaptureFrame]:
    if not keyframes:
        return []

    frames: list[CaptureFrame] = []
    x, z = 0.0, 0.0
    yaw = 0.0
    prev_gray = keyframes[0]["gray"]

    for kf in keyframes:
        gray = kf["gray"]
        dx, dyaw = _flow_step(prev_gray, gray)
        prev_gray = gray
        x += dx * np.cos(yaw)
        z += dx * np.sin(yaw)
        yaw += dyaw

        cy = np.cos(yaw)
        sy = np.sin(yaw)
        T = np.array(
            [
                [cy, 0, sy, x],
                [0, 1, 0, 0],
                [-sy, 0, cy, z],
                [0, 0, 0, 1],
            ],
            dtype=float,
        )
        frames.append(
            CaptureFrame(
                index=int(kf["index"]),
                timestamp_s=float(kf["timestamp_s"]),
                image_path=None,
                K=K.copy(),
                T_world_cam=T,
                depth_path=None,
            )
        )
    return frames


def _flow_step(prev: np.ndarray, curr: np.ndarray) -> tuple[float, float]:
    assert cv2 is not None
    prev_s = cv2.resize(prev, (160, 120))
    curr_s = cv2.resize(curr, (160, 120))
    flow = cv2.calcOpticalFlowFarneback(prev_s, curr_s, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    fx = float(np.median(flow[..., 0])) * 0.002
    fy = float(np.median(flow[..., 1])) * 0.002
    step = float(np.hypot(fx, fy))
    dyaw = float(np.arctan2(fy, fx + 1e-6)) * 0.15
    return step, dyaw


def ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=False)
        return True
    except OSError:
        return False
