"""Optional Azure calls — only when keys are in environment (never committed)."""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv_once() -> None:
    if getattr(_load_dotenv_once, "_done", False):
        return
    root = Path(__file__).resolve().parents[2]
    env_path = root / ".env"
    if not env_path.is_file():
        _load_dotenv_once._done = True  # type: ignore[attr-defined]
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and key not in os.environ:
            os.environ[key] = val
    _load_dotenv_once._done = True  # type: ignore[attr-defined]


def _env(name: str) -> str | None:
    _load_dotenv_once()
    v = os.environ.get(name, "").strip()
    return v or None


def enrich_video_warnings(capture_dir: Path) -> list[str]:
    """
    Placeholder hook for Azure OpenAI / Vision on keyframes (Phase 4+).
    Loads optional keys from repo-root `.env` only; LiDAR/Stray/video v0 stay offline.
    """
    warnings: list[str] = []
    if _env("AZURE_OPENAI_API_KEY") and _env("AZURE_OPENAI_ENDPOINT"):
        warnings.append("azure_openai configured (video v0 still uses offline geometry)")
    elif _env("AZURE_VISION_KEY") and _env("AZURE_VISION_ENDPOINT"):
        warnings.append("azure_vision configured (not required for video v0)")
    else:
        warnings.append("video tier v0: offline keyframes + flow (no Azure call)")
    return warnings
