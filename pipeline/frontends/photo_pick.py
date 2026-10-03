"""Shared photo file selection for photo tier."""

from __future__ import annotations

from pathlib import Path


def pick_spaced_photos(files: list[Path], n: int) -> list[Path]:
    if n <= 0 or not files:
        return []
    if len(files) <= n:
        return list(files)
    step = (len(files) - 1) / max(n - 1, 1)
    return [files[int(round(i * step))] for i in range(n)]
