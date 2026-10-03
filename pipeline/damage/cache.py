"""Cached per-image damage cues (brief rule 6 — keyed by input hash + detector version)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

DETECTOR_VERSION = "damage_detect_v3"
ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / ".cache" / "damage"


def read_image_hits(image_path: Path) -> list[dict] | None:
    path = _cache_file(image_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("version") != DETECTOR_VERSION:
        return None
    hits = data.get("hits")
    return list(hits) if isinstance(hits, list) else None


def write_image_hits(image_path: Path, hits: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_file(image_path)
    payload = {"version": DETECTOR_VERSION, "image": image_path.name, "hits": hits}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_vision_tags(image_path: Path) -> list[str] | None:
    path = _cache_file(image_path, suffix=".vision.json")
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("version") != DETECTOR_VERSION:
        return None
    tags = data.get("tags")
    return list(tags) if isinstance(tags, list) else None


def write_vision_tags(image_path: Path, tags: list[str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_file(image_path, suffix=".vision.json")
    payload = {"version": DETECTOR_VERSION, "image": image_path.name, "tags": tags}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _cache_file(image_path: Path, *, suffix: str = ".json") -> Path:
    h = hashlib.sha256()
    h.update(DETECTOR_VERSION.encode())
    try:
        h.update(image_path.read_bytes()[:4_000_000])
    except OSError:
        h.update(str(image_path).encode())
    return CACHE_DIR / f"{h.hexdigest()}{suffix}"
