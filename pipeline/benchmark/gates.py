"""Score plan.json against ground_truth.json (Phase 2 gates, LiDAR-complete)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GateResult:
    tier: str
    passed: dict[str, bool] = field(default_factory=dict)
    metrics: dict[str, float | None] = field(default_factory=dict)
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"tier": self.tier, "passed": self.passed, "metrics": self.metrics, "details": self.details}


def score(
    plan_path: Path,
    ground_truth_path: Path,
    tier: str = "lidar",
    repeat_plan_path: Path | None = None,
) -> GateResult:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    gt = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    tol_open_cm = 2.0
    tol_ceil_cm = 1.5
    tol_ceil_spread_cm = 1.0
    footprint_tol = {"lidar": 0.02, "video": 0.03, "photos": 0.08}.get(tier, 0.08)
    wall_tol = {"lidar": 0.02, "video": 0.03, "photos": 0.08}.get(tier, 0.08)

    opening = _score_openings(plan, gt, tol_open_cm)
    ceiling = _score_ceilings(plan, gt, tol_ceil_cm)
    footprint = _score_footprint(plan, gt, footprint_tol)
    walls = _score_walls(plan, gt, wall_tol)
    overlap = _score_overlap(plan)
    calibration = _score_calibration(plan)

    ceil_repeat = {"pass": True, "skipped": True}
    if repeat_plan_path and repeat_plan_path.is_file():
        plan_b = json.loads(repeat_plan_path.read_text(encoding="utf-8"))
        ceil_repeat = _score_ceiling_repeat(plan, plan_b, gt, tol_ceil_spread_cm)

    passed = {
        "opening_85pct_2cm": opening["pass_rate"] >= 0.85 and opening["phantom_count"] == 0,
        "ceiling_1p5cm": ceiling["all_pass"],
        "ceiling_repeat_spread_1cm": ceil_repeat.get("pass", True),
        "footprint_tier": footprint["pass"],
        "walls_tier": walls["pass_rate"] >= 0.85,
        "stitch_no_overlap": overlap["pass"],
        "calibration_sane": calibration["pass"],
    }

    return GateResult(
        tier=tier,
        passed=passed,
        metrics={
            "opening_pass_rate": opening["pass_rate"],
            "opening_phantoms": float(opening["phantom_count"]),
            "opening_missed": float(opening["missed_count"]),
            "footprint_error_pct": footprint["error_pct"],
            "wall_pass_rate": walls["pass_rate"],
            "overlap_m2": overlap["overlap_m2"],
        },
        details={
            "openings": opening,
            "ceilings": ceiling,
            "ceiling_repeat": ceil_repeat,
            "footprint": footprint,
            "walls": walls,
            "overlap": overlap,
            "calibration": calibration,
        },
    )


def score_repeatability(plan_a: Path, plan_b: Path, tier: str = "lidar") -> GateResult:
    a = json.loads(plan_a.read_text(encoding="utf-8"))
    b = json.loads(plan_b.read_text(encoding="utf-8"))
    tol_m = 0.01
    tol_rel = 0.005

    by_a = {r["room_id"]: r for r in a["rooms"]}
    by_b = {r["room_id"]: r for r in b["rooms"]}
    common = set(by_a) & set(by_b)
    max_err = 0.0
    rows: list[dict] = []
    signed_deltas: list[float] = []

    for rid in common:
        la = sorted(w["length_m"]["value_m"] for w in by_a[rid]["walls"])
        lb = sorted(w["length_m"]["value_m"] for w in by_b[rid]["walls"])
        n = min(len(la), len(lb))
        for i in range(n):
            d = abs(la[i] - lb[i])
            max_err = max(max_err, d)
            signed_deltas.append(la[i] - lb[i])
            rows.append({"room_id": rid, "wall_index": i, "delta_m": d, "ref_m": la[i]})

    ok = (
        all(r["delta_m"] <= tol_m or r["delta_m"] / max(r["ref_m"], 1e-6) <= tol_rel for r in rows)
        if rows
        else False
    )
    bias_note = _bias_class(signed_deltas)
    return GateResult(
        tier=tier,
        passed={"repeatability_1cm_or_half_pct": ok},
        metrics={"repeatability_max_delta_m": max_err if rows else None},
        details={"pairs": rows, "bias_analysis": bias_note},
    )


def _bias_class(deltas: list[float]) -> dict:
    if not deltas:
        return {"kind": "unknown", "note": "no pairs"}
    mean = sum(deltas) / len(deltas)
    if all(abs(d) <= 0.001 for d in deltas):
        return {"kind": "repeatable", "mean_delta_m": mean}
    if all(d >= 0.005 for d in deltas) or all(d <= -0.005 for d in deltas):
        return {"kind": "repeatable_but_biased", "mean_delta_m": mean}
    return {"kind": "unrepeatable", "mean_delta_m": mean}


def _score_ceiling_repeat(plan_a: dict, plan_b: dict, gt: dict, tol_spread_cm: float) -> dict:
    gt_ceil = gt.get("ceiling_height_cm", {})
    by_a = {r["room_id"]: r for r in plan_a["rooms"]}
    by_b = {r["room_id"]: r for r in plan_b["rooms"]}
    rows = []
    all_pass = True
    for rid in set(by_a) & set(by_b):
        if rid not in gt_ceil:
            continue
        ca = by_a[rid]["ceiling_height_m"]["value_m"] * 100.0
        cb = by_b[rid]["ceiling_height_m"]["value_m"] * 100.0
        spread = abs(ca - cb)
        rows.append({"room_id": rid, "spread_cm": spread, "a_cm": ca, "b_cm": cb})
        if spread > tol_spread_cm:
            all_pass = False
    return {"pass": all_pass, "skipped": False, "rooms": rows}


def _score_overlap(plan: dict) -> dict:
    meta = plan.get("pipeline_meta", {})
    overlap = float(meta.get("overlap_m2", 0.0))
    return {"pass": overlap <= 0.05, "overlap_m2": overlap}


def _score_calibration(plan: dict) -> dict:
    """Fail if QA warnings exist and any sigma is tighter than tier floor (confident garbage)."""
    warnings = plan.get("pipeline_meta", {}).get("qa_warnings", [])
    issues: list[str] = []
    for room in plan.get("rooms", []):
        for wall in room.get("walls", []):
            for key in ("length_m",):
                conf = wall.get(key, {}).get("confidence", {})
                if conf.get("sigma_m", 0) < conf.get("tier_floor_m", 0) * 0.99:
                    issues.append(f"{room['room_id']}:{wall['id']} sigma below floor")
    orphan_fail = any("orphan" in w.lower() for w in warnings)
    ok = not issues and not orphan_fail
    return {"pass": ok, "issues": issues, "qa_warnings": warnings}


def _score_openings(plan: dict, gt: dict, tol_cm: float) -> dict:
    gt_list = _gt_openings(gt)
    pred_list = _pred_openings(plan)
    matched_pred = set()
    hits = 0
    for g in gt_list:
        best = None
        for i, p in enumerate(pred_list):
            if i in matched_pred:
                continue
            if g.get("room_id") and p["room_id"] != g["room_id"]:
                continue
            if g.get("kind") and p.get("kind") != g["kind"]:
                continue
            err = abs(p["width_cm"] - g["width_cm"])
            if best is None or err < best[0]:
                best = (err, i)
        if best and best[0] <= tol_cm:
            hits += 1
            matched_pred.add(best[1])

    missed = len(gt_list) - hits
    phantom = len(pred_list) - len(matched_pred)
    rate = hits / len(gt_list) if gt_list else 0.0
    return {"pass_rate": rate, "matched": hits, "missed_count": missed, "phantom_count": phantom}


def _gt_openings(gt: dict) -> list[dict]:
    if "openings_cm" in gt and isinstance(gt["openings_cm"], list):
        if gt["openings_cm"] and isinstance(gt["openings_cm"][0], dict):
            return gt["openings_cm"]
        return [{"width_cm": float(x)} for x in gt["openings_cm"]]
    return []


def _pred_openings(plan: dict) -> list[dict]:
    out: list[dict] = []
    for room in plan.get("rooms", []):
        for wall in room.get("walls", []):
            for op in wall.get("openings", []):
                out.append(
                    {
                        "room_id": room["room_id"],
                        "kind": op.get("kind"),
                        "width_cm": op["width_m"]["value_m"] * 100.0,
                    }
                )
    return out


def _score_ceilings(plan: dict, gt: dict, tol_cm: float) -> dict:
    gt_ceil = gt.get("ceiling_height_cm", {})
    rows = []
    all_pass = True
    for room in plan.get("rooms", []):
        rid = room["room_id"]
        if rid not in gt_ceil:
            continue
        pred = room["ceiling_height_m"]["value_m"] * 100.0
        err = abs(pred - gt_ceil[rid])
        rows.append({"room_id": rid, "error_cm": err})
        if err > tol_cm:
            all_pass = False
    return {"all_pass": all_pass, "rooms": rows}


def _score_footprint(plan: dict, gt: dict, tol: float) -> dict:
    if "footprint_area_m2" not in gt:
        return {"pass": False, "error_pct": None}
    pred = plan["stitched_plan"]["footprint_area_m2"]["value_m"]
    err = abs(pred - gt["footprint_area_m2"]) / gt["footprint_area_m2"]
    return {"pass": err <= tol, "error_pct": err}


def _score_walls(plan: dict, gt: dict, tol_rel: float) -> dict:
    gt_walls = gt.get("wall_lengths_cm", {})
    if not gt_walls:
        return {"pass_rate": 0.0, "rooms": []}
    ok = 0
    total = 0
    rows = []
    for room in plan.get("rooms", []):
        rid = room["room_id"]
        if rid not in gt_walls:
            continue
        pred = sorted(w["length_m"]["value_m"] * 100.0 for w in room["walls"])
        truth = sorted(float(x) for x in gt_walls[rid])
        n = min(len(pred), len(truth))
        for i in range(n):
            total += 1
            err = abs(pred[i] - truth[i]) / truth[i]
            if err <= tol_rel:
                ok += 1
            rows.append({"room_id": rid, "index": i, "rel_error": err})
    rate = ok / total if total else 0.0
    return {"pass_rate": rate, "rooms": rows}
