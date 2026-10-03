from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
from jsonschema import Draft202012Validator


def write_plan(payload: dict, schema_path: Path, out_json: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def render_plan(
    stitched: dict,
    rooms: list[dict],
    out_png: Path,
    *,
    damage_regions: list[dict] | None = None,
) -> str:
    from pipeline.export.plan_render import render_plan as _render_rich

    return _render_rich(stitched, rooms, out_png, damage_regions=damage_regions)
