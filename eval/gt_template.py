"""Generate empty ground-truth JSON skeleton (Tester fills measured values)."""

from __future__ import annotations

import json
from pathlib import Path

from eval.capture_id import resolve_capture_id
from eval.gt_loader import gt_path_for_capture


def build_gt_template(capture_dir: Path) -> dict:
    capture_dir = capture_dir.resolve()
    capture_id = resolve_capture_id(capture_dir)
    room_ids = _room_ids_from_capture(capture_dir)

    wall_lengths_cm = {rid: ["TODO", "TODO", "TODO", "TODO"] for rid in room_ids}
    ceiling_height_cm = {rid: "TODO" for rid in room_ids}
    openings_cm: list[dict] = []
    for rid in room_ids:
        openings_cm.append({"room_id": rid, "kind": "door", "width_cm": "TODO", "notes": "main door"})

    return {
        "_meta": {
            "status": "TODO",
            "capture_id": capture_id,
            "method": "tape per docs/ASSESSMENT_BRIEF.md §7",
            "measured_by": "TODO",
            "measured_on": "TODO",
        },
        "footprint_area_m2": "TODO",
        "wall_lengths_cm": wall_lengths_cm,
        "ceiling_height_cm": ceiling_height_cm,
        "openings_cm": openings_cm,
        "_instructions": {
            "footprint_area_m2": "Laser/tape whole-property stitched footprint (multi-room) or single room area",
            "wall_lengths_cm": "W1 = wall with entry door, then clockwise from above; cm corner-to-corner",
            "set_complete": 'Set _meta.status to "complete" when all TODO replaced with numbers',
        },
    }


def write_gt_template(capture_dir: Path, *, overwrite: bool = False) -> Path:
    capture_id = resolve_capture_id(capture_dir)
    path = gt_path_for_capture(capture_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and not overwrite:
        raise FileExistsError(f"{path} exists; pass overwrite=True")
    payload = build_gt_template(capture_dir)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _room_ids_from_capture(capture_dir: Path) -> list[str]:
    manifest = capture_dir / "manifest.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        rooms = data.get("rooms") or []
        ids = [r["room_id"] for r in rooms if isinstance(r, dict) and r.get("room_id")]
        if ids:
            return ids

    rooms_root = capture_dir / "rooms"
    if rooms_root.is_dir():
        ids = sorted(p.name for p in rooms_root.iterdir() if p.is_dir())
        if ids:
            return ids

    return ["room_1"]
