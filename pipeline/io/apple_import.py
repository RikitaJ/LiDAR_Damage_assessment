"""Normalize a folder of Apple JSON exports into our capture layout."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from pipeline.io.adjacency_infer import infer_adjacency


def import_apple(input_dir: Path, out_dir: Path, capture_id: str | None = None) -> Path:
    input_dir, out_dir = input_dir.resolve(), out_dir.resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    rooms_root = out_dir / "rooms"
    rooms_root.mkdir(parents=True)

    by_room: dict[str, str] = {}
    for path in sorted(input_dir.rglob("*.json")):
        if path.name in ("manifest.json", "ground_truth.json"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {path}") from e
        if not data.get("walls"):
            continue
        rid = path.stem.replace(" ", "_").lower()
        if rid in by_room:
            continue
        lidar = rooms_root / rid / "lidar"
        lidar.mkdir(parents=True)
        (lidar / "room.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        by_room[rid] = path.stem

    if not by_room:
        raise FileNotFoundError(f"No RoomPlan JSON under {input_dir}")

    entries = [{"room_id": rid, "name": name} for rid, name in sorted(by_room.items())]
    room_ids = [e["room_id"] for e in entries]
    adjacency = infer_adjacency(rooms_root, room_ids) if len(room_ids) > 1 else []
    manifest = {
        "capture_id": capture_id or out_dir.name,
        "tier": "lidar",
        "device": {"model": "iPhone 15 Pro", "has_lidar": True},
        "rooms": entries,
        "adjacency": adjacency,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out_dir
