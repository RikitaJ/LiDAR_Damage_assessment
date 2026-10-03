import json
from pathlib import Path

from eval.gt_loader import gt_ready_for_gates, load_ground_truth
from eval.report import score_capture


def test_c00_gt_marked_todo():
    gt, notes = load_ground_truth("c00a170fe1")
    assert gt is not None
    assert not gt_ready_for_gates(gt)
    assert any("TODO" in n for n in notes)


def test_lidar_fixture_gt_ready():
    gt, notes = load_ground_truth("lidar_two_room_fixture")
    assert gt is not None
    assert gt_ready_for_gates(gt)
    assert not any("TODO" in n for n in notes)


def test_score_capture_without_complete_gt(tmp_path):
    cap = tmp_path / "cap1"
    cap.mkdir()
    (cap / "out").mkdir()
    plan = {
        "rooms": [{"room_id": "R1", "walls": [], "ceiling_height_m": {"value_m": 2.5}, "floor_area_m2": {"value_m": 10}}],
        "stitched_plan": {"footprint_area_m2": {"value_m": 10}},
        "pipeline_meta": {"qa_warnings": [], "overlap_m2": 0},
    }
    (cap / "out" / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    rep = score_capture(cap, cap / "out" / "plan.json")
    assert rep["ready"] is False
