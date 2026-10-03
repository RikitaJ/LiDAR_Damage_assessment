"""Sanitize room dicts — brief rule 5: warn, do not crash on bad real-world input."""

from __future__ import annotations

import math
from typing import Any


def sanitize_room(room: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for wall in room.get("walls", []):
        length = wall.get("length_m", {})
        v = length.get("value_m", length.get("value", 0.0))
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            warnings.append(f"{room.get('room_id')}: wall {wall.get('id')} invalid length → 0.01m placeholder")
            wall["length_m"] = _wide_placeholder(0.01)
            continue
        if v <= 0:
            warnings.append(f"{room.get('room_id')}: wall {wall.get('id')} non-positive length {v}")
            wall["length_m"] = _wide_placeholder(abs(float(v)) or 0.01)
        pl = wall.get("polyline_m") or []
        if len(pl) >= 2:
            a, b = pl[0], pl[1]
            if _points_equal(a, b):
                warnings.append(f"{room.get('room_id')}: wall {wall.get('id')} zero-length polyline adjusted")
                b = [float(a[0]) + max(float(v), 0.01), float(a[1])]
                wall["polyline_m"] = [a, b]
    area = room.get("floor_area_m2", {})
    av = area.get("value_m", area.get("value", 0.0))
    if av is None or (isinstance(av, float) and (math.isnan(av) or av <= 0)):
        warnings.append(f"{room.get('room_id')}: floor area invalid → wide placeholder")
        room["floor_area_m2"] = _wide_placeholder(9.0)
    return warnings


def _points_equal(a, b, eps: float = 1e-9) -> bool:
    return abs(float(a[0]) - float(b[0])) < eps and abs(float(a[1]) - float(b[1])) < eps


def _wide_placeholder(value: float) -> dict:
    from pipeline.measure.intervals import with_interval

    return with_interval(float(value), max(0.5, float(value) * 0.5), notes="invalid_input_placeholder")
