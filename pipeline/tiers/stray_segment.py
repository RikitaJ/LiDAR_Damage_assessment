"""Split a long Stray capture into room segments by camera path clusters."""

from __future__ import annotations

import numpy as np

from pipeline.schema.capture_frames import CaptureFrame, CaptureFrames


def subset_capture_frames(cf: CaptureFrames, segment: int, segment_count: int) -> CaptureFrames:
    if segment_count <= 1 or segment < 0 or segment >= segment_count:
        return cf
    labels = _cluster_frames(cf.frames, segment_count)
    picked = [fr for fr, lab in zip(cf.frames, labels) if lab == segment]
    if not picked:
        picked = cf.frames[segment :: segment_count]
    return CaptureFrames(
        tier=cf.tier,
        capture_id=f"{cf.capture_id}_seg{segment}",
        device=cf.device,
        gravity_aligned=cf.gravity_aligned,
        scale_sigma_rel=cf.scale_sigma_rel,
        frames=picked,
        warnings=list(cf.warnings) + [f"stray segment {segment + 1}/{segment_count}"],
        rgb_video_path=cf.rgb_video_path,
    )


def _cluster_frames(frames: list[CaptureFrame], k: int) -> list[int]:
    if len(frames) < k * 10:
        return [min(i * k // max(len(frames), 1), k - 1) for i in range(len(frames))]

    xz = np.array([[fr.T_world_cam[0, 3], fr.T_world_cam[2, 3]] for fr in frames], dtype=float)
    centroids = _init_centroids(xz, k)
    labels = np.zeros(len(frames), dtype=int)
    for _ in range(25):
        dists = np.linalg.norm(xz[:, None, :] - centroids[None, :, :], axis=2)
        labels = dists.argmin(axis=1)
        for j in range(k):
            members = xz[labels == j]
            if len(members):
                centroids[j] = members.mean(axis=0)
    return labels.tolist()


def _init_centroids(xz: np.ndarray, k: int) -> np.ndarray:
    idx = np.linspace(0, len(xz) - 1, k, dtype=int)
    return xz[idx].copy()
