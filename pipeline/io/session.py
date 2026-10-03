from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.config import InputTier
from pipeline.io.tier_detect import CaptureKind, detect_capture_kind, stray_scanner_root


@dataclass
class RoomPaths:
    room_id: str
    name: str
    lidar_dir: Path
    stray_segment: int | None = None
    stray_segment_count: int | None = None


@dataclass
class Session:
    capture_id: str
    tier: InputTier
    device_model: str
    has_lidar: bool
    rooms: list[RoomPaths]
    adjacency: list[tuple[str, str, str]]


def load_session(capture_dir: Path, tier_hint: InputTier | None = None) -> Session:
    capture_dir = capture_dir.resolve()
    if tier_hint == InputTier.VIDEO:
        return _session_video(capture_dir)

    kind = detect_capture_kind(capture_dir)
    if kind == CaptureKind.STRAY_SCANNER:
        root = stray_scanner_root(capture_dir)
        assert root is not None
        return Session(
            capture_id=capture_dir.name if root == capture_dir else root.name,
            tier=InputTier.LIDAR,
            device_model="Stray Scanner export",
            has_lidar=True,
            rooms=[RoomPaths("R1", "room_1", root)],
            adjacency=[],
        )

    if kind == CaptureKind.VIDEO_ONLY:
        return _session_video(capture_dir)

    manifest_path = capture_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Missing {manifest_path}. Expected manifest.json or Stray Scanner files (odometry.csv)."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tier_raw = manifest.get("tier", "lidar")
    try:
        tier = InputTier(tier_raw)
    except ValueError as e:
        raise ValueError(f"manifest.json: unknown tier '{tier_raw}'") from e
    if tier in (InputTier.VIDEO, InputTier.PHOTOS):
        root = capture_dir
        entries = manifest["rooms"]
        rooms = [
            RoomPaths(
                entry["room_id"],
                entry.get("name", entry["room_id"]),
                root,
            )
            for entry in entries
        ]
        seen = {r.room_id for r in rooms}
        adj: list[tuple[str, str, str]] = []
        for e in manifest.get("adjacency", []):
            a, b = e.get("room_a"), e.get("room_b")
            if not a or not b or a not in seen or b not in seen:
                continue
            adj.append((a, b, e.get("via_opening_id", "")))
        dev = manifest.get("device", {})
        if tier == InputTier.PHOTOS:
            photo_rooms: list[RoomPaths] = []
            for entry in entries:
                rid = entry["room_id"]
                room_dir = capture_dir / "rooms" / rid
                photo_rooms.append(
                    RoomPaths(rid, entry.get("name", rid), room_dir),
                )
            return Session(
                capture_id=manifest.get("capture_id", capture_dir.name),
                tier=InputTier.PHOTOS,
                device_model=dev.get("model", "photo capture"),
                has_lidar=False,
                rooms=photo_rooms,
                adjacency=adj,
            )
        return Session(
            capture_id=manifest.get("capture_id", capture_dir.name),
            tier=InputTier.VIDEO,
            device_model=dev.get("model", "video walkthrough"),
            has_lidar=False,
            rooms=rooms,
            adjacency=adj,
        )
    if not manifest.get("rooms"):
        raise ValueError("manifest.json: 'rooms' must be a non-empty list")

    stray_root = stray_scanner_root(capture_dir)
    if manifest.get("capture_format") == "stray" and stray_root is not None:
        entries = manifest["rooms"]
        n = len(entries)
        rooms = [
            RoomPaths(
                entry["room_id"],
                entry.get("name", entry["room_id"]),
                stray_root,
                stray_segment=int(entry.get("segment", i)),
                stray_segment_count=n,
            )
            for i, entry in enumerate(entries)
        ]
        seen = {r.room_id for r in rooms}
    else:
        rooms = []
        seen = set()
        for entry in manifest["rooms"]:
            rid = entry["room_id"]
            if rid in seen:
                raise ValueError(f"Duplicate room_id in manifest: {rid}")
            seen.add(rid)
            lidar = capture_dir / "rooms" / rid / "lidar"
            if not lidar.is_dir():
                raise FileNotFoundError(f"Missing rooms/{rid}/lidar")
            rooms.append(RoomPaths(rid, entry.get("name", rid), lidar))

    adj: list[tuple[str, str, str]] = []
    for e in manifest.get("adjacency", []):
        a, b = e.get("room_a"), e.get("room_b")
        if not a or not b or a not in seen or b not in seen:
            continue
        adj.append((a, b, e.get("via_opening_id", "")))
    dev = manifest.get("device", {})
    return Session(
        capture_id=manifest.get("capture_id", capture_dir.name),
        tier=tier,
        device_model=dev.get("model", "unknown"),
        has_lidar=bool(dev.get("has_lidar", True)),
        rooms=rooms,
        adjacency=adj,
    )


def _session_video(capture_dir: Path) -> Session:
    from pipeline.frontends.video import find_video_file

    root = stray_scanner_root(capture_dir) or capture_dir
    if find_video_file(root) is None and find_video_file(capture_dir) is None:
        raise FileNotFoundError(f"No video file under {capture_dir}")
    use = root if find_video_file(root) else capture_dir
    return Session(
        capture_id=use.name,
        tier=InputTier.VIDEO,
        device_model="video walkthrough",
        has_lidar=False,
        rooms=[RoomPaths("R1", "room_1", use)],
        adjacency=[],
    )
