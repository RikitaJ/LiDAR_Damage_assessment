#!/usr/bin/env python3
"""Phase 5 damage + scope sign-off on LiDAR fixture (offline)."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import InputTier, RunConfig
from pipeline.run import run_capture

from tests.fixtures.capture_factory import LIDAR_TWO_ROOM


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="phase5_") as td:
        cap = Path(td) / "lidar_two_room"
        shutil.copytree(LIDAR_TWO_ROOM, cap)
        out = cap / "out"
        plan_path = run_capture(cap, out, RunConfig(tier=InputTier.LIDAR))
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        surfaces = data.get("surfaces") or []
        damage = data.get("damage_regions") or []
        concealed = data.get("concealed_damage_flags") or []
        scope = data.get("scope_line_items") or []
        png = out / "floorplan.png"

        limits = (data.get("pipeline_meta") or {}).get("limitations") or []
        report = {
            "phase": 5,
            "status": "ok" if surfaces and png.is_file() and limits else "fail",
            "surfaces_count": len(surfaces),
            "damage_regions_count": len(damage),
            "concealed_flags_count": len(concealed),
            "scope_items_count": len(scope),
            "limitations_count": len(limits),
            "floorplan_png_bytes": png.stat().st_size if png.is_file() else 0,
        }
        out_report = ROOT / "docs" / "PHASE5_SIGNOFF_REPORT.json"
        out_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
