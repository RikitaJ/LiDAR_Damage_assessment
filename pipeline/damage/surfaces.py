"""Wall/ceiling surfaces with net areas for damage + scope (brief §5.8)."""

from __future__ import annotations

from pipeline.config import InputTier, SIGMA
from pipeline.measure.intervals import with_interval


def build_surfaces(rooms: list[dict], tier: InputTier) -> list[dict]:
    out: list[dict] = []
    for room in rooms:
        rid = room["room_id"]
        ceil_m = float(room["ceiling_height_m"]["value_m"])
        for w in room.get("walls", []):
            length_m = float(w["length_m"]["value_m"])
            open_m2 = _opening_area_on_wall(w)
            gross = max(length_m * ceil_m, 0.1)
            net = max(gross - open_m2, 0.05)
            sig = max(net * SIGMA[tier].footprint_rel, 0.08)
            out.append(
                {
                    "id": w["id"],
                    "type": "wall",
                    "room_id": rid,
                    "wall_id": w["id"],
                    "net_area_m2": with_interval(net, sig, notes="surface_net", tier=tier, kind="footprint"),
                }
            )
        floor_a = float(room["floor_area_m2"]["value_m"])
        sig_f = max(floor_a * SIGMA[tier].footprint_rel, 0.05)
        out.append(
            {
                "id": f"{rid}-ceiling",
                "type": "ceiling",
                "room_id": rid,
                "net_area_m2": with_interval(floor_a, sig_f, notes="surface_ceiling", tier=tier, kind="footprint"),
            }
        )
    return out


def surface_by_id(surfaces: list[dict], surface_id: str) -> dict | None:
    for s in surfaces:
        if s["id"] == surface_id:
            return s
    return None


def _opening_area_on_wall(wall: dict) -> float:
    area = 0.0
    for op in wall.get("openings") or []:
        try:
            w_m = float(op.get("width_m", {}).get("value_m", 0))
            h_m = float(op.get("height_m", {}).get("value_m", 2.0))
            area += w_m * h_m
        except (TypeError, ValueError, AttributeError):
            continue
    return area
