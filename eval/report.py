"""Write benchmark-style gate reports from plan + GT."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pipeline.benchmark.gates import score

from eval.capture_id import resolve_capture_id
from eval.gt_loader import gt_ready_for_gates, load_ground_truth


def score_capture(
    capture_dir: Path,
    plan_path: Path | None = None,
    *,
    tier: str = "lidar",
) -> dict:
    capture_dir = capture_dir.resolve()
    capture_id = resolve_capture_id(capture_dir)
    if plan_path is None:
        plan_path = capture_dir / "out" / "plan.json"
    plan_path = plan_path.resolve()

    out: dict = {
        "capture_id": capture_id,
        "capture_dir": capture_dir.name,
        "plan": str(plan_path),
        "tier": tier,
        "ready": False,
        "notes": [],
    }
    if not plan_path.is_file():
        out["notes"].append(f"missing plan {plan_path}")
        return out

    gt, gt_notes = load_ground_truth(capture_id)
    out["notes"].extend(gt_notes)
    if gt is None:
        return out
    if not gt_ready_for_gates(gt):
        out["notes"].append("GT incomplete — gates not scored (fill data/ground_truth/*.json)")
        out["ready"] = False
        return out

    payload_gt = {k: v for k, v in gt.items() if not k.startswith("_")}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(payload_gt, tf)
        gt_file = Path(tf.name)
    try:
        report = score(plan_path, gt_file, tier)
        out["ready"] = True
        out["gates"] = report.to_dict()
    finally:
        gt_file.unlink(missing_ok=True)

    return out


def write_report(capture_dir: Path, dest: Path | None = None, **kwargs) -> Path:
    payload = score_capture(capture_dir, **kwargs)
    dest = dest or (capture_dir / "out" / "eval_report.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest
