"""Load ground truth JSON for scoring (never imported from pipeline/)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GT_DIR = ROOT / "data" / "ground_truth"


def gt_path_for_capture(capture_id: str) -> Path:
    return GT_DIR / f"{capture_id}.json"


def load_ground_truth(capture_id: str) -> tuple[dict | None, list[str]]:
    path = gt_path_for_capture(capture_id)
    if not path.is_file():
        return None, [f"missing {path}"]
    data = json.loads(path.read_text(encoding="utf-8"))
    notes: list[str] = []
    meta = data.get("_meta", {})
    if meta.get("status") == "TODO":
        notes.append("ground truth marked TODO — fill measured values before gate claims")
    if data.get("footprint_area_m2") in (None, "TODO"):
        notes.append("footprint_area_m2 not set")
    return data, notes


def gt_ready_for_gates(gt: dict) -> bool:
    if gt.get("_meta", {}).get("status") == "TODO":
        return False
    fp = gt.get("footprint_area_m2")
    if fp is None or fp == "TODO":
        return False
    return True
