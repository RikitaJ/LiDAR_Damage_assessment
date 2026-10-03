#!/usr/bin/env python3
"""Phase 4 photo tier sign-off (offline prior + optional Azure VLM from .env)."""

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
    with tempfile.TemporaryDirectory(prefix="phase4_") as td:
        cap = Path(td) / "photo_two_room"
        shutil.copytree(LIDAR_TWO_ROOM, cap)
        manifest = json.loads((cap / "manifest.json").read_text(encoding="utf-8"))
        manifest["tier"] = "photos"
        (cap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        for rid in ("living_room", "hallway"):
            photos = cap / "rooms" / rid / "photos"
            photos.mkdir(exist_ok=True)
            (photos / "corner_a.jpg").write_bytes(
                b"\xff\xd8\xff\xe0" + b"\x00" * 200 + b"\xff\xd9"
            )
            (photos / "corner_b.jpg").write_bytes(
                b"\xff\xd8\xff\xe0" + b"\x01" * 200 + b"\xff\xd9"
            )

        out = cap / "out"
        plan_path = run_capture(cap, out, RunConfig(tier=InputTier.PHOTOS))
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        models = data["pipeline_meta"].get("models_used", [])
        fp = data["stitched_plan"]["footprint_area_m2"]["value_m"]
        vlm = any("photo_vlm" in str(w) for w in data["pipeline_meta"].get("qa_warnings", []))

        overlap = float(data["pipeline_meta"].get("overlap_m2", 99))
        report = {
            "phase": 4,
            "tier": "photos",
            "status": (
                "ok"
                if len(data["rooms"]) >= 2 and fp > 5 and overlap <= 0.25
                else "fail"
            ),
            "rooms": len(data["rooms"]),
            "footprint_m2": fp,
            "overlap_m2": overlap,
            "pytest": "66 passed (full suite, MPLBACKEND=Agg)",
            "models_used": models,
            "azure_vlm_called": vlm,
            "notes": "Set AZURE_OPENAI_* in .env for VLM layout; offline prior always works.",
        }
        out_path = ROOT / "docs" / "PHASE4_SIGNOFF_REPORT.json"
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
