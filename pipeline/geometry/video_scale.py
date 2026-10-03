"""When rgb.mp4 and odometry.csv coexist, scale video geometry to odometry path span."""

from __future__ import annotations

from pathlib import Path

from pipeline.frontends.stray_lidar import load_stray_capture


def odometry_xz_span(root: Path) -> float | None:
    if not (root / "odometry.csv").is_file():
        return None
    cf = load_stray_capture(root)
    if len(cf.frames) < 3:
        return None
    xs = [float(fr.T_world_cam[0, 3]) for fr in cf.frames]
    zs = [float(fr.T_world_cam[2, 3]) for fr in cf.frames]
    return max(float(max(xs) - min(xs)), float(max(zs) - min(zs)), 0.05)


def room_xz_span(room: dict) -> float:
    xs: list[float] = []
    zs: list[float] = []
    for w in room.get("walls", []):
        for p in w.get("polyline_m", []):
            xs.append(float(p[0]))
            zs.append(float(p[1]))
    if not xs:
        return 0.5
    return max(max(xs) - min(xs), max(zs) - min(zs), 0.05)


def scale_room_xy(room: dict, factor: float) -> None:
    if abs(factor - 1.0) < 0.02:
        return
    f = float(factor)
    for w in room.get("walls", []):
        for p in w.get("polyline_m", []):
            p[0] = float(p[0]) * f
            p[1] = float(p[1]) * f
        lm = w.get("length_m", {})
        if "value_m" in lm:
            v = float(lm["value_m"]) * f
            half = (float(lm.get("hi", v)) - float(lm.get("lo", v))) / 2.0 * f
            lm["value_m"] = lm["value"] = v
            lm["lo"] = v - half
            lm["hi"] = v + half
    fa = room.get("floor_area_m2", {})
    if "value_m" in fa:
        v = float(fa["value_m"]) * (f * f)
        half = (float(fa.get("hi", v)) - float(fa.get("lo", v))) / 2.0 * (f * f)
        fa["value_m"] = fa["value"] = v
        fa["lo"] = v - half
        fa["hi"] = v + half
    tx, ty, tz = room["pose_world"]["translation_m"]
    room["pose_world"]["translation_m"] = [float(tx) * f, ty, float(tz) * f]


def align_video_room_to_odometry(room: dict, capture_root: Path) -> list[str]:
    odom = odometry_xz_span(capture_root)
    if odom is None:
        return []
    vid = room_xz_span(room)
    if vid < 0.1:
        return []
    factor = odom / vid
    factor = max(0.5, min(factor, 8.0))
    scale_room_xy(room, factor)
    return [f"video footprint scaled ×{factor:.2f} to odometry path span ({odom:.2f} m)"]
