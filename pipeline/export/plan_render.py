"""Floor plan PNG: walls, dimensions, doors, windows."""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def render_plan(stitched: dict, rooms: list[dict], out_png: Path) -> str:
    fig, ax = plt.subplots(figsize=(14, 14))
    ax.set_aspect("equal")
    fp = stitched.get("footprint_area_m2") or {}
    fp_v = fp.get("value_m", fp.get("value"))
    title = "Stitched floor plan (m)"
    if fp_v is not None:
        title += f" — footprint {float(fp_v):.1f} m²"
    ax.set_title(title)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Z (m)")
    ax.grid(True, alpha=0.25)

    for room in rooms:
        _draw_room(ax, room)

    for wall in stitched.get("global_walls", []):
        pl = wall.get("polyline_m") or []
        if len(pl) < 2:
            continue
        xs, ys = [p[0] for p in pl], [p[1] for p in pl]
        ax.plot(xs, ys, color="#cccccc", lw=1, zorder=1)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return str(out_png)


def _draw_room(ax, room: dict) -> None:
    tx, _, tz = room["pose_world"]["translation_m"]
    name = room.get("name", room.get("room_id", ""))
    cx, cz = tx, tz
    for w in room.get("walls", []):
        pl = w.get("polyline_m") or []
        if len(pl) < 2:
            continue
        p0 = np.array(pl[0], float) + np.array([tx, tz])
        p1 = np.array(pl[1], float) + np.array([tx, tz])
        openings = w.get("openings") or []
        _draw_wall_with_openings(ax, p0, p1, openings, tx, tz)
        meas = w.get("length_m") or {}
        label = _format_meas(meas)
        mid = (p0 + p1) / 2
        ax.text(mid[0], mid[1], label, fontsize=8, ha="center", color="navy", zorder=5)

    ax.text(cx, cz, name, fontsize=11, fontweight="bold", ha="center", zorder=6)


def _format_meas(meas: dict) -> str:
    v = meas.get("value_m", meas.get("value", 0.0))
    lo, hi = meas.get("lo"), meas.get("hi")
    if lo is not None and hi is not None:
        return f"{v:.2f}m\n[{lo:.2f}-{hi:.2f}]"
    return f"{v:.2f}m"


def _draw_wall_with_openings(ax, p0: np.ndarray, p1: np.ndarray, openings: list, tx: float, tz: float) -> None:
    wall_vec = p1 - p0
    length = float(np.linalg.norm(wall_vec))
    if length < 1e-6:
        return
    u = wall_vec / length

    gaps: list[tuple[float, float, dict]] = []
    for op in openings:
        width = float(op.get("width_m", {}).get("value_m", 0.9))
        if "anchor_m" in op:
            anchor = np.array(op["anchor_m"], float) + np.array([tx, tz])
            t = float(np.dot(anchor - p0, u))
        else:
            t = length / 2
        t0 = max(0.0, t - width / 2)
        t1 = min(length, t + width / 2)
        gaps.append((t0, t1, op))

    gaps.sort(key=lambda g: g[0])
    cursor = 0.0
    for t0, t1, op in gaps:
        if t0 > cursor:
            ax.plot([p0[0] + u[0] * cursor, p0[0] + u[0] * t0], [p0[1] + u[1] * cursor, p0[1] + u[1] * t0], "k-", lw=2.5, zorder=3)
        kind = op.get("kind", "opening")
        mid = p0 + u * ((t0 + t1) / 2)
        if kind == "window":
            perp = np.array([-u[1], u[0]]) * 0.08
            ax.plot([mid[0] - perp[0], mid[0] + perp[0]], [mid[1] - perp[1], mid[1] + perp[1]], "b-", lw=2, zorder=4)
            ax.plot([mid[0] - perp[0], mid[0] + perp[0]], [mid[1] - perp[1], mid[1] + perp[1]], "b--", lw=1, zorder=4)
        else:
            _draw_door_arc(ax, p0 + u * t0, p0 + u * t1, u)
        cursor = t1
    if cursor < length:
        ax.plot([p0[0] + u[0] * cursor, p1[0]], [p0[1] + u[1] * cursor, p1[1]], "k-", lw=2.5, zorder=3)
    if not gaps:
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], "k-", lw=2.5, zorder=3)


def _draw_door_arc(ax, a: np.ndarray, b: np.ndarray, u: np.ndarray) -> None:
    width = float(np.linalg.norm(b - a))
    if width < 0.01:
        return
    perp = np.array([-u[1], u[0]])
    hinge = a
    angles = np.linspace(0, math.pi / 2, 16)
    arc = [hinge + u * width * math.cos(t) + perp * width * math.sin(t) for t in angles]
    ax.plot([p[0] for p in arc], [p[1] for p in arc], color="saddlebrown", lw=1.5, zorder=4)
