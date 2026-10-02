"""RoomPlan-style JSON → one room plan (metric geometry from Apple transforms)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import InputTier
from pipeline.geometry.floor_polygon import floor_area_m2
from pipeline.geometry.wall_graph import polygon_area_from_walls
from pipeline.measure.confidence import area_m2, m


def parse_room(lidar_dir: Path, room_id: str, name: str) -> dict[str, Any]:
    path = _find_json(lidar_dir)
    data = json.loads(path.read_text(encoding="utf-8"))
    tier = InputTier.LIDAR

    walls_out: list[dict] = []
    by_id: dict[str, dict] = {}

    raw_walls = data.get("walls") or []
    if not raw_walls:
        raise ValueError(f"Room {room_id}: scan JSON has no walls")

    for i, wall in enumerate(raw_walls):
        dims = wall.get("dimensions") or [0, 0, 0]
        length = float(dims[0])
        T = _transform(wall.get("transform"), wid := wall.get("identifier") or f"wall_{i}")
        w = {
            "id": wid,
            "length_m": m(length, tier),
            "polyline_m": _wall_line(T, length),
            "openings": [],
        }
        walls_out.append(w)
        by_id[wid] = w

    orphan_openings: list[str] = []
    for j, obj in enumerate(data.get("doors", []) + data.get("windows", []) + data.get("openings", [])):
        dims = obj.get("dimensions") or [0, 0, 0]
        kind = _opening_kind(obj)
        op = {
            "id": obj.get("identifier") or f"op_{j}",
            "kind": kind,
            "width_m": m(float(dims[0]), tier, "opening"),
            "height_m": m(float(dims[1]) if len(dims) > 1 else 2.0, tier, "height"),
            "wall_id": obj.get("parentIdentifier") or obj.get("wallIdentifier") or "",
        }
        anchor = _opening_anchor(obj)
        if anchor is not None:
            op["anchor_m"] = anchor
        parent = op["wall_id"]
        if parent in by_id:
            by_id[parent]["openings"].append(op)
        else:
            orphan_openings.append(op["id"])

    area = polygon_area_from_walls(walls_out) or _rect_area_from_walls(walls_out) or floor_area_m2(walls_out)
    ceiling = _ceiling_m(data)

    return {
        "room_id": room_id,
        "name": name,
        "floor_area_m2": area_m2(max(area, 0.01), tier),
        "ceiling_height_m": m(ceiling, tier, "height"),
        "walls": walls_out,
        "pose_world": {"translation_m": [0.0, 0.0, 0.0], "rotation_quat": [0.0, 0.0, 0.0, 1.0]},
        "_orphan_openings": orphan_openings,
    }


def _opening_anchor(obj: dict) -> list[float] | None:
    raw = obj.get("transform")
    if not raw or len(raw) != 16:
        return None
    T = np.array(raw, dtype=float).reshape(4, 4)
    return [float(T[0, 3]), float(T[2, 3])]


def _transform(raw: list | None, wall_id: str) -> np.ndarray:
    flat = list(raw) if raw is not None else np.eye(4).flatten().tolist()
    if len(flat) != 16:
        raise ValueError(f"Wall {wall_id}: transform must have 16 numbers, got {len(flat)}")
    return np.array(flat, dtype=float).reshape(4, 4)


def _find_json(lidar_dir: Path) -> Path:
    for name in ("room.json", "captured_room.json"):
        p = lidar_dir / name
        if p.is_file():
            return p
    files = list(lidar_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON in {lidar_dir}")
    return files[0]


def _wall_line(T: np.ndarray, length: float) -> list[list[float]]:
    o = T[:3, 3]
    x = T[:3, 0]
    e = o + x * length
    return [[float(o[0]), float(o[2])], [float(e[0]), float(e[2])]]


def _opening_kind(obj: dict) -> str:
    cat = obj.get("category", {})
    label = (cat.get("label") if isinstance(cat, dict) else str(cat)).lower()
    if "window" in label:
        return "window"
    if "door" in label:
        return "door"
    return "opening"


def _rect_area_from_walls(walls: list[dict]) -> float:
    """RoomPlan rooms are usually rectangles; use distinct wall lengths (most reliable)."""
    lengths = [w["length_m"]["value_m"] for w in walls if w["length_m"]["value_m"] > 0]
    if len(lengths) < 4:
        return 0.0
    uniq = sorted({round(x, 4) for x in lengths})
    if len(uniq) >= 2:
        return float(uniq[0] * uniq[-1])
    return 0.0


def _ceiling_m(data: dict) -> float:
    for wall in data.get("walls", []):
        dims = wall.get("dimensions") or []
        if len(dims) > 1 and dims[1]:
            return float(dims[1])
    return 2.5
