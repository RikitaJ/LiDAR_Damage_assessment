"""Project image bbox corners through camera onto wall surface UV (brief §5.8)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import InputTier
from pipeline.damage.frame_lookup import DamageViewContext, frame_for_image, intrinsics_for_image
from pipeline.damage.project import pick_wall_id, wall_length_m
from pipeline.schema.capture_frames import CaptureFrame

PROJ_TAG = "camera_proj_v1"


def _resolve_wall_id(room: dict, hit: dict, tier: InputTier) -> str | None:
    cls = str(hit.get("class") or "water_stain")
    wall_id = pick_wall_id(room, cls=cls, hit=hit)
    door_wall = room.get("_photo_door_wall_id")
    if tier == InputTier.PHOTOS and door_wall and cls == "water_stain":
        try:
            uc = float(hit.get("u_center_frac", 0.5))
        except (TypeError, ValueError):
            uc = 0.5
        if 0.22 < uc < 0.78:
            return str(door_wall)
    return wall_id


def project_hits_on_image(
    hits: list[dict],
    *,
    room: dict,
    tier: InputTier,
    image_path,
    view_ctx: DamageViewContext,
    img_w: int,
    img_h: int,
) -> tuple[list[dict], list[str]]:
    if not hits or img_w < 8 or img_h < 8:
        return hits, []
    warnings: list[str] = []
    frame = frame_for_image(view_ctx, image_path)
    K = intrinsics_for_image(image_path, frame)
    out: list[dict] = []
    for hit in hits:
        wall_id = _resolve_wall_id(room, hit, tier)
        if not wall_id or wall_id.endswith("-ceiling"):
            out.append(hit)
            continue
        use_pose = frame is not None and tier in (InputTier.LIDAR, InputTier.VIDEO)
        if use_pose:
            uv = _project_calibrated(hit, room, wall_id, K, frame, img_w, img_h)
            tag = "camera_pose_v1"
        else:
            uv = _project_photo_standoff(hit, room, wall_id, K, img_w, img_h)
            tag = "exif_wall_plane_v1"
        if not uv:
            out.append(hit)
            continue
        merged = dict(hit)
        merged.update(uv)
        merged["source"] = _tag_source(merged.get("source", ""), PROJ_TAG, tag)
        merged["wall_id_hint"] = wall_id
        out.append(merged)
    if any(PROJ_TAG in h.get("source", "") for h in out):
        warnings.append(f"damage: camera projection on {Path(image_path).name}")
    return out, warnings


def _tag_source(src: str, *tags: str) -> str:
    for t in tags:
        if t not in src:
            src = f"{src}+{t}" if src else t
    return src


def _sample_pixels(hit: dict, w: int, h: int) -> list[tuple[float, float]]:
    u0 = float(hit.get("u0_frac", hit.get("u_center_frac", 0.4) - 0.08))
    u1 = float(hit.get("u1_frac", hit.get("u_center_frac", 0.4) + 0.08))
    v0 = float(hit.get("v0_frac", 0.35))
    v1 = float(hit.get("v1_frac", 0.85))
    u0, u1 = max(0.0, min(u0, u1)), min(1.0, max(u0, u1))
    v0, v1 = max(0.0, min(v0, v1)), min(1.0, max(v0, v1))
    uc, vc = (u0 + u1) / 2, (v0 + v1) / 2
    pts = [(u0, v0), (u1, v0), (u1, v1), (u0, v1), (uc, vc)]
    return [(px * w, py * h) for px, py in pts]


def _wall_segment_world(room: dict, wall_id: str) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    for w in room.get("walls") or []:
        if w.get("id") != wall_id:
            continue
        pl = w.get("polyline_m") or []
        if len(pl) < 2:
            return None
        p0 = _room_to_world_3(pl[0], room)
        p1 = _room_to_world_3(pl[1], room)
        d = p1 - p0
        ln = float(np.linalg.norm(d))
        if ln < 1e-6:
            return None
        d /= ln
        up = np.array([0.0, 1.0, 0.0])
        n = np.cross(d, up)
        n /= max(float(np.linalg.norm(n)), 1e-6)
        return p0, d, n
    return None


def _room_to_world_3(p: list[float], room: dict) -> np.ndarray:
    tx, _, tz = room.get("pose_world", {}).get("translation_m", [0.0, 0.0, 0.0])
    return np.array([float(p[0]) + float(tx), 0.0, float(p[1]) + float(tz)], dtype=float)


def _pixel_ray_world(u: float, v: float, K: np.ndarray, T_world_cam: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    Kinv = np.linalg.inv(K)
    d_cam = Kinv @ np.array([u, v, 1.0], dtype=float)
    d_cam /= max(float(np.linalg.norm(d_cam)), 1e-9)
    R = T_world_cam[:3, :3]
    t = T_world_cam[:3, 3]
    direction = R @ d_cam
    direction /= max(float(np.linalg.norm(direction)), 1e-9)
    return t, direction


def _intersect_plane(origin: np.ndarray, direction: np.ndarray, p0: np.ndarray, normal: np.ndarray) -> np.ndarray | None:
    denom = float(np.dot(direction, normal))
    if abs(denom) < 1e-8:
        return None
    s = float(np.dot(p0 - origin, normal)) / denom
    if s <= 0.05:
        return None
    return origin + s * direction


def _uv_from_rays(
    hit: dict,
    room: dict,
    wall_id: str,
    K: np.ndarray,
    T: np.ndarray,
    img_w: int,
    img_h: int,
) -> dict[str, Any] | None:
    seg = _wall_segment_world(room, wall_id)
    if seg is None:
        return None
    p0, d_wall, normal = seg
    wl = wall_length_m(room, wall_id)
    ceil_m = float(room.get("ceiling_height_m", {}).get("value_m", 2.5))
    us: list[float] = []
    vs: list[float] = []
    for px, py in _sample_pixels(hit, img_w, img_h):
        origin, direction = _pixel_ray_world(px, py, K, T)
        pt = _intersect_plane(origin, direction, p0, normal)
        if pt is None:
            continue
        us.append(float(np.dot(pt - p0, d_wall)))
        vs.append(float(pt[1]))
    if len(us) < 2:
        return None
    u0, u1 = max(0.0, min(us)), min(wl, max(us))
    v0, v1 = max(0.0, min(vs)), min(ceil_m, max(vs))
    if u1 - u0 < 0.04 or v1 - v0 < 0.04:
        return None
    return {
        "u0_frac": u0 / wl,
        "u1_frac": u1 / wl,
        "u_center_frac": (u0 + u1) / (2.0 * wl),
        "v0_frac": v0 / max(ceil_m, 0.1),
        "v1_frac": v1 / max(ceil_m, 0.1),
        "bottom_above_floor_m": v0,
        "area_m2": max((u1 - u0) * (v1 - v0), 0.04),
    }


def _project_calibrated(
    hit: dict, room: dict, wall_id: str, K: np.ndarray, frame: CaptureFrame, img_w: int, img_h: int
) -> dict[str, Any] | None:
    return _uv_from_rays(hit, room, wall_id, K, frame.T_world_cam, img_w, img_h)


def _project_photo_standoff(
    hit: dict, room: dict, wall_id: str, K: np.ndarray, img_w: int, img_h: int
) -> dict[str, Any] | None:
    seg = _wall_segment_world(room, wall_id)
    if seg is None:
        return None
    _p0, _d, normal = seg
    eye = _camera_eye(room, normal)
    T = _look_at_T(eye, -normal)
    return _uv_from_rays(hit, room, wall_id, K, T, img_w, img_h)


def _camera_eye(room: dict, wall_normal: np.ndarray) -> np.ndarray:
    xs, zs = [], []
    for w in room.get("walls") or []:
        for p in w.get("polyline_m") or []:
            xs.append(float(p[0]))
            zs.append(float(p[1]))
    tx, _, tz = room.get("pose_world", {}).get("translation_m", [0.0, 0.0, 0.0])
    cx = sum(xs) / max(len(xs), 1) + float(tx)
    cz = sum(zs) / max(len(zs), 1) + float(tz)
    n = np.array(wall_normal, dtype=float)
    n = n / max(float(np.linalg.norm(n)), 1e-6)
    return np.array([cx, 1.45, cz], dtype=float) + n * 1.75


def _look_at_T(eye: np.ndarray, forward: np.ndarray) -> np.ndarray:
    f = forward / max(float(np.linalg.norm(forward)), 1e-6)
    up = np.array([0.0, 1.0, 0.0])
    r = np.cross(up, f)
    r /= max(float(np.linalg.norm(r)), 1e-6)
    u = np.cross(f, r)
    T = np.eye(4)
    T[:3, 0] = r
    T[:3, 1] = u
    T[:3, 2] = f
    T[:3, 3] = eye
    return T
