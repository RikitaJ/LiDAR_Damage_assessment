import json

from eval.accuracy import Row, align_walls, repeatability, score_room
from eval.run import main


def _m(value, half=0.05):
    return {"value": value, "lo": value - half, "hi": value + half}


def _room(walls, ceiling=2.96, area=23.9, kinds=()):
    return {
        "room_id": "R1",
        "walls": [{"length_m": _m(w), "openings": [{"kind": k} for k in kinds] if i == 0 else []} for i, w in enumerate(walls)],
        "ceiling_height_m": _m(ceiling),
        "floor_area_m2": _m(area, 1.5),
    }


GT = {
    "_meta": {"status": "complete", "room": "B1"},
    "footprint_area_m2": 24.36,
    "ceiling_height_cm": {"R1": 298},
    "wall_lengths_cm": {"R1": [435, 560, 435, 560]},
    "opening_counts": {"R1": {"door": 2, "window": 2}},
}


def test_align_walls_handles_rotation_and_reversal():
    truth = [4.35, 5.60, 4.10, 5.20]
    assert align_walls([5.60, 4.10, 5.20, 4.35], truth) == [3, 0, 1, 2]
    assert align_walls([5.20, 4.10, 5.60, 4.35], truth) == [3, 2, 1, 0]


def test_align_walls_marks_missing_walls():
    assert align_walls([4.35, 5.60], [4.35, 5.60, 4.35, 5.60])[2:] == [None, None]
    assert align_walls([], [4.35]) == [None]


def test_row_gates_and_coverage():
    wall = Row("Wall 1", 4.35, 4.324, 4.275, 4.373, ("abs", 0.02))
    assert wall.passed is False and wall.covered
    area = Row("Floor area (m²)", 24.36, 23.90, 22.33, 25.48, ("rel", 0.02))
    assert area.passed is True
    assert Row("x", 1.0, 1.0, None, None, None).passed is None
    assert not Row("x", 1.0, 1.0, None, None, None).covered


def test_score_room_lidar_against_tape():
    rows, detection = score_room(_room([4.324, 5.528, 4.324, 5.528], kinds=("door",) * 8), GT, "R1", "lidar")
    by_name = {r.name: r for r in rows}
    assert [r.name for r in rows][:4] == ["Wall 1", "Wall 2", "Wall 3", "Wall 4"]
    assert by_name["Wall 2"].passed is False and not by_name["Wall 2"].covered
    assert by_name["Ceiling height"].passed is False and by_name["Ceiling height"].covered
    assert by_name["Floor area (m²)"].passed is True
    assert detection["missed"] == 2 and detection["phantom"] == 6


def test_video_tier_uses_relative_wall_gate():
    rows, _ = score_room(_room([4.30, 5.50, 4.30, 5.50]), GT, "R1", "video")
    assert all(r.passed for r in rows if r.name.startswith("Wall"))


def test_repeatability_gate():
    same = repeatability(_room([4.324, 5.528] * 2), _room([4.327, 5.531] * 2, ceiling=2.965))
    assert same["walls_passed"] and same["ceiling_passed"]
    off = repeatability(_room([4.324, 5.528] * 2), _room([4.36, 5.60] * 2, ceiling=2.99))
    assert not off["walls_passed"] and not off["ceiling_passed"]


def test_report_from_existing_runs(tmp_path):
    gt_dir, runs = tmp_path / "gt", tmp_path / "runs"
    gt_dir.mkdir()
    (gt_dir / "b1_rep1.json").write_text(json.dumps(GT), encoding="utf-8")
    (gt_dir / "todo.json").write_text(json.dumps({"_meta": {"status": "TODO"}}), encoding="utf-8")
    (gt_dir / "fixture.json").write_text(json.dumps(GT), encoding="utf-8")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("capture_id,tier\nb1_rep1,lidar\ntodo,lidar\n", encoding="utf-8")
    for cid in ("b1_rep1",):
        (runs / cid).mkdir(parents=True)
        plan = {"input_tier": "lidar", "rooms": [_room([4.324, 5.528, 4.324, 5.528])]}
        (runs / cid / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    report = tmp_path / "REPORT.md"
    args = ["--gt", str(gt_dir), "--runs", str(runs), "--captures", str(tmp_path / "none"),
            "--manifest", str(manifest), "--report", str(report)]
    assert main(args) == 0
    text = report.read_text(encoding="utf-8")
    assert "## b1_rep1 (lidar)" in text
    assert "| Wall 2 | 5.600 | 5.528 [5.478, 5.578] | -7.2 cm (-1.3 %) | ±2 cm | **FAIL** | no |" in text
    assert "Tape value inside the 90 % interval: 4 of 6 measurements." in text
    assert "todo" not in text and "fixture" not in text
