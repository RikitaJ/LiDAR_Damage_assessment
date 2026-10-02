from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.config import InputTier


@dataclass
class RoomPaths:
    room_id: str
    name: str
    lidar_dir: Path


@dataclass
class Session:
    capture_id: str
    tier: InputTier
    device_model: str
    has_lidar: bool
    rooms: list[RoomPaths]
    adjacency: list[tuple[str, str, str]]


def load_session(capture_dir: Path) -> Session:
    manifest_path = capture_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tier = InputTier(manifest["tier"])
    if not manifest.get("rooms"):
        raise ValueError("manifest.json: 'rooms' must be a non-empty list")
    rooms: list[RoomPaths] = []
    seen: set[str] = set()
    for entry in manifest["rooms"]:
        rid = entry["room_id"]
        if rid in seen:
            raise ValueError(f"Duplicate room_id in manifest: {rid}")
        seen.add(rid)
        lidar = capture_dir / "rooms" / rid / "lidar"
        if not lidar.is_dir():
            raise FileNotFoundError(f"Missing rooms/{rid}/lidar")
        rooms.append(RoomPaths(rid, entry.get("name", rid), lidar))

    adj = [
        (e["room_a"], e["room_b"], e.get("via_opening_id", ""))
        for e in manifest.get("adjacency", [])
    ]
    dev = manifest.get("device", {})
    return Session(
        capture_id=manifest.get("capture_id", capture_dir.name),
        tier=tier,
        device_model=dev.get("model", "unknown"),
        has_lidar=bool(dev.get("has_lidar", True)),
        rooms=rooms,
        adjacency=adj,
    )
