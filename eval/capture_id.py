"""Resolve benchmark capture_id from folder layout (manifest or directory name)."""

from __future__ import annotations

import json
from pathlib import Path


def resolve_capture_id(capture_dir: Path) -> str:
    capture_dir = capture_dir.resolve()
    manifest = capture_dir / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            cid = data.get("capture_id")
            if isinstance(cid, str) and cid.strip():
                return cid.strip()
        except json.JSONDecodeError:
            pass
    return capture_dir.name
