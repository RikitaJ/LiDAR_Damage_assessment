"""Build Manhattan rectangle room from wall lengths (photo tier)."""

from __future__ import annotations

from typing import Any

from pipeline.config import SIGMA, InputTier
from pipeline.measure.intervals import with_interval


def rectangle_room_from_wall_lengths(
    room_id: str,
    name: str,
    lengths_m: list[float],
    *,
    tier: InputTier,
    ceiling_m: float = 2.5,
    area_m2: float | None = None,
    notes: str = "photo_rect",
) -> dict[str, Any]:
    """Four wall lengths clockwise → closed rectangle."""
    L = [max(float(x), 0.5) for x in lengths_m[:4]]
    while len(L) < 4:
        L.append(L[-1] if L else 3.0)

    span_x = max(L[0], L[2])
    span_z = max(L[1], L[3])
    corners = [
        [0.0, 0.0],
        [span_x, 0.0],
        [span_x, span_z],
        [0.0, span_z],
    ]
    sig = SIGMA[tier]
    sigma_len = max(sig.length_m, span_x * sig.footprint_rel)
    walls: list[dict] = []
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        length = float(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5)
        walls.append(
            {
                "id": f"{room_id}-W{i + 1}",
                "length_m": with_interval(length, sigma_len, notes=notes, tier=tier, kind="wall"),
                "polyline_m": [a, b],
                "openings": [],
            }
        )
    area = area_m2 if area_m2 and area_m2 > 1.0 else span_x * span_z
    sig_a = max(area * sig.footprint_rel, area * 0.12)
    return {
        "room_id": room_id,
        "name": name,
        "floor_area_m2": with_interval(area, sig_a, notes=notes, tier=tier, kind="footprint"),
        "ceiling_height_m": with_interval(
            ceiling_m, sig.height_m * 2, notes=notes, tier=tier, kind="height"
        ),
        "walls": walls,
        "pose_world": {"translation_m": [span_x / 2, 0.0, span_z / 2], "rotation_quat": [0, 0, 0, 1]},
        "_orphan_openings": [],
    }


def manhattan_room_from_wall_lengths(
    room_id: str,
    name: str,
    lengths_m: list[float],
    *,
    tier: InputTier,
    ceiling_m: float = 2.5,
    area_m2: float | None = None,
    notes: str = "photo_manhattan",
) -> dict[str, Any]:
    """Clockwise wall lengths with 90° turns (L-shapes and longer loops)."""
    L = [max(float(x), 0.5) for x in lengths_m if x is not None]
    if len(L) < 4:
        return rectangle_room_from_wall_lengths(
            room_id, name, L or [3.0, 3.0, 3.0, 3.0], tier=tier, ceiling_m=ceiling_m, area_m2=area_m2, notes=notes
        )
    if len(L) == 4:
        return rectangle_room_from_wall_lengths(
            room_id, name, L, tier=tier, ceiling_m=ceiling_m, area_m2=area_m2, notes=notes
        )

    corners = _trace_manhattan(L)
    sig = SIGMA[tier]
    walls: list[dict] = []
    max_span = 0.0
    for i, length_nominal in enumerate(L):
        a, b = corners[i], corners[i + 1]
        length = float(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5)
        max_span = max(max_span, length)
        sigma_len = max(sig.length_m, length * sig.footprint_rel)
        walls.append(
            {
                "id": f"{room_id}-W{i + 1}",
                "length_m": with_interval(length_nominal, sigma_len, notes=notes, tier=tier, kind="wall"),
                "polyline_m": [a, b],
                "openings": [],
            }
        )
    area = area_m2 if area_m2 and area_m2 > 1.0 else _shoelace_area(corners)
    sig_a = max(area * sig.footprint_rel, area * 0.12)
    xs = [p[0] for p in corners]
    zs = [p[1] for p in corners]
    cx, cz = (max(xs) + min(xs)) / 2, (max(zs) + min(zs)) / 2
    return {
        "room_id": room_id,
        "name": name,
        "floor_area_m2": with_interval(area, sig_a, notes=notes, tier=tier, kind="footprint"),
        "ceiling_height_m": with_interval(
            ceiling_m, sig.height_m * 2, notes=notes, tier=tier, kind="height"
        ),
        "walls": walls,
        "pose_world": {"translation_m": [cx, 0.0, cz], "rotation_quat": [0, 0, 0, 1]},
        "_orphan_openings": [],
    }


def _trace_manhattan(lengths: list[float]) -> list[list[float]]:
    x, z = 0.0, 0.0
    dirs = [(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0)]
    d = 0
    points: list[list[float]] = [[x, z]]
    for length in lengths:
        dx, dz = dirs[d % 4]
        x += dx * float(length)
        z += dz * float(length)
        points.append([x, z])
        d += 1
    return points


def _shoelace_area(points: list[list[float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for i in range(len(points) - 1):
        x1, z1 = points[i]
        x2, z2 = points[i + 1]
        area += x1 * z2 - x2 * z1
    return max(abs(area) / 2.0, 1.0)
