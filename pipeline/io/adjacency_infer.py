"""Infer room adjacency from door widths in RoomPlan JSON (import helper)."""

from __future__ import annotations

import json
from pathlib import Path


def infer_adjacency(rooms_root: Path, room_ids: list[str]) -> list[dict]:
    doors: dict[str, list[tuple[str, float]]] = {}
    for rid in room_ids:
        path = rooms_root / rid / "lidar" / "room.json"
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for obj in data.get("doors", []) + data.get("openings", []):
            if not _is_door(obj):
                continue
            dims = obj.get("dimensions") or [0]
            oid = obj.get("identifier") or f"door_{rid}"
            doors.setdefault(rid, []).append((oid, float(dims[0])))

    edges: list[dict] = []
    for i, a in enumerate(room_ids):
        for b in room_ids[i + 1 :]:
            da, db = doors.get(a, []), doors.get(b, [])
            if not da or not db:
                continue
            best = min(((oa, ob, abs(wa - wb)) for oa, wa in da for ob, wb in db), key=lambda t: t[2])
            if best[2] < 0.25:
                edges.append({"room_a": a, "room_b": b, "via_opening_id": best[0]})
    return edges


def _is_door(obj: dict) -> bool:
    cat = obj.get("category", {})
    label = (cat.get("label") if isinstance(cat, dict) else str(cat)).lower()
    return "door" in label
