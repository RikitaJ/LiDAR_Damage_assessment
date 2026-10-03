"""Legacy wall nudge — loop closure now applied to poses before depth fusion."""

from __future__ import annotations

from pathlib import Path


def apply_stray_loop_to_rooms(rooms: list[dict], lidar_dir: Path, enabled: bool) -> list[str]:
    del rooms, lidar_dir, enabled
    return []
