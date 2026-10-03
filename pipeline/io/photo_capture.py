"""Discover per-room photo folders without manifest (brief §5.4 layout)."""

from __future__ import annotations

from pathlib import Path

from pipeline.config import InputTier
from pipeline.io.session import RoomPaths, Session
from pipeline.tiers.photo_room_v0 import PHOTO_EXT

PHOTOS_SUBDIR = "photos"


def room_has_photos(room_dir: Path) -> bool:
    if not room_dir.is_dir():
        return False
    photos = room_dir / PHOTOS_SUBDIR
    if photos.is_dir() and _any_photo(photos):
        return True
    return _any_photo(room_dir)


def _any_photo(folder: Path) -> bool:
    return any(
        p.is_file() and p.suffix.lower() in PHOTO_EXT for p in folder.iterdir()
    )


def session_from_photo_folders(capture_dir: Path) -> Session | None:
    """Build a photo-tier session from `rooms/<id>/photos/` (no manifest)."""
    capture_dir = capture_dir.resolve()
    rooms_root = capture_dir / "rooms"
    if not rooms_root.is_dir():
        return None

    entries: list[tuple[str, Path]] = []
    for child in sorted(rooms_root.iterdir()):
        if not child.is_dir() or not room_has_photos(child):
            continue
        rid = child.name
        entries.append((rid, child))

    if not entries:
        return None

    rooms = [
        RoomPaths(rid, rid.replace("_", " ").title(), room_dir)
        for rid, room_dir in entries
    ]
    return Session(
        capture_id=capture_dir.name,
        tier=InputTier.PHOTOS,
        device_model="photo capture (auto)",
        has_lidar=False,
        rooms=rooms,
        adjacency=[],
    )
