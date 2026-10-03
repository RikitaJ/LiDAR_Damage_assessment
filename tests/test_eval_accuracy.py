import json

from eval.accuracy import Row, align_walls, head_to_head, repeatability, score_openings, score_room
from eval.run import README_END, README_START, main


def _m(value, half=0.05):
    return {"value": value, "lo": value - half, "hi": value + half}


def _room(walls, ceiling=2.96, area=23.9, openings=()):
    ops = [{"kind": kind, "width_m": _m(width)} for kind, width in openings]
    return {
        "room_id": "R1",
        "walls": [{"length_m": _m(w), "openings": ops if i == 0 else []} for i, w in enumerate(walls)],
        "ceiling_height_m": _m(ceiling),
        "floor_area_m2": _m(area, 1.5),
    }


TAPED = [
    {"room_id": "R1", "kind": "door", "width_cm": 88.9},
    {"room_id": "R1", "kind": "door", "width_cm": 88.9},
    {"room_id": "R1", "kind": "window", "width_cm": 70.0},
    {"room_id": "R1", "kind": "window", "width_cm": 70.0},
]
GT = {
    "_meta": {"status": "complete", "room": "B1"},
    "footprint_area_m2": 24.36,
    "ceiling_height_cm": {"R1": 298.5},
    "wall_lengths_cm": {"R1": [435, 560, 435, 560]},
    "openings_cm": TAPED,
}


def test_align_walls_handles_rotation_and_reversal():
    truth = [4.35, 5.60, 4.10, 5.20]
    assert align_walls([5.60, 4.10, 5.20, 4.35], truth) == [3, 0, 1, 2]
    assert align_walls([5.20, 4.10, 5.60, 4.35], truth) == [3, 2, 1, 0]


def test_align_walls_marks_missing_walls():
    assert align_walls([4.35, 5.60], [4.35, 5.60, 4.35, 5.60])[2:] == [None, None]
    assert align_walls([], [4.35]) == [None]


def test_row_gates_accuracy_and_coverage():
    wall = Row("Wall 1", 4.35, 4.324, 4.275, 4.373, ("abs", 0.02))
    assert wall.passed is False and wall.covered
    assert round(wall.accuracy, 1) == 99.4 and round(100 * wall.miss, 1) == 0.6
    area = Row("Floor area (m²)", 24.36, 23.90, 22.33, 25.48, ("rel", 0.02))
    assert area.passed is True and area.miss == 0.0
    assert Row("x", 1.0, 1.0, None, None, None).passed is None
    assert not Row("x", 1.0, 1.0, None, None, None).covered


def test_score_room_lidar_against_tape():
    rows, openings = score_room(_room([4.324, 5.528, 4.324, 5.528], openings=[("door", 0.90)] * 8), GT, "R1", "lidar")
    by_name = {r.name: r for r in rows}
    assert [r.name for r in rows][:4] == ["Wall 1", "Wall 2", "Wall 3", "Wall 4"]
    assert by_name["Wall 2"].passed is False and not by_name["Wall 2"].covered
    assert by_name["Ceiling height"].passed is False and by_name["Ceiling height"].covered
    assert by_name["Floor area (m²)"].passed is True
    assert (openings["hits"], openings["missed"], openings["phantom"]) == (2, 2, 6)
    assert openings["undetected"] == [("Window 1 width", 0.70), ("Window 2 width", 0.70)]
    assert openings["rate"] == 0.2 and not openings["passed"]


def test_inaccurate_opening_is_one_miss_not_a_phantom():
    result = score_openings(_room([4.35], openings=[("door", 0.95)]), TAPED[:1])
    assert (result["hits"], result["missed"], result["phantom"]) == (0, 1, 0)


def test_all_openings_within_2cm_pass():
    found = [("door", 0.895), ("door", 0.88), ("window", 0.71), ("window", 0.695)]
    result = score_openings(_room([4.35], openings=found), TAPED)
    assert result["hits"] == 4 and result["phantom"] == 0 and result["passed"]


def test_head_to_head_beat_tie_lose():
    rows, _ = score_room(_room([4.324, 5.528, 4.324, 5.528], ceiling=2.958), GT, "R1", "lidar")
    app = {"Wall 1": 4.30, "Wall 2": 5.60, "Wall 3": 4.322, "Wall 4": 5.62, "Ceiling height": 2.90}
    h2h = head_to_head(rows, [], app)
    assert [r["result"] for r in h2h["rows"]] == ["beat", "lose", "tie", "lose", "beat"]
    assert h2h["beat_or_tie"] == 3 and not h2h["passed"]


def test_head_to_head_counts_undetected_opening_as_lose():
    h2h = head_to_head([], [("Window 1 width", 0.70)], {"Window 1 width": 0.692, "Unknown": 1.0})
    assert h2h["rows"] == [{"name": "Window 1 width", "truth": 0.70, "ours": None, "theirs": 0.692, "result": "lose"}]


def test_video_tier_uses_relative_wall_gate():
    rows, _ = score_room(_room([4.30, 5.50, 4.30, 5.50]), GT, "R1", "video")
    assert all(r.passed for r in rows if r.name.startswith("Wall"))


def test_repeatability_gate():
    same = repeatability(_room([4.324, 5.528] * 2), _room([4.327, 5.531] * 2, ceiling=2.965))
    assert same["walls_passed"] and same["ceiling_passed"]
    off = repeatability(_room([4.324, 5.528] * 2), _room([4.36, 5.60] * 2, ceiling=2.99))
    assert not off["walls_passed"] and not off["ceiling_passed"]


def test_report_and_readme_from_existing_runs(tmp_path):
    gt_dir, runs, apps = tmp_path / "gt", tmp_path / "runs", tmp_path / "apps"
    gt_dir.mkdir()
    apps.mkdir()
    (gt_dir / "b1_rep1.json").write_text(json.dumps(GT), encoding="utf-8")
    (gt_dir / "todo.json").write_text(json.dumps({"_meta": {"status": "TODO"}}), encoding="utf-8")
    (gt_dir / "fixture.json").write_text(json.dumps(GT), encoding="utf-8")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("capture_id,tier\nb1_rep1,lidar\ntodo,lidar\n", encoding="utf-8")
    (runs / "b1_rep1").mkdir(parents=True)
    plan = {"input_tier": "lidar", "rooms": [_room([4.324, 5.528, 4.324, 5.528], openings=[("door", 0.90)])]}
    (runs / "b1_rep1" / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    app = {"app": "magicplan", "version": "2026.38.0", "source": "read from the app's plan view",
           "lengths_m": {"Wall 1": 4.36, "Wall 2": 5.59, "Wall 3": 4.36, "Wall 4": 5.59,
                         "Door 1 width": 0.885, "Window 1 width": 0.692},
           "floor_area_m2": 24.32}
    (apps / "magicplan_b1_rep1.json").write_text(json.dumps(app), encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text(f"intro\n{README_START}\nold\n{README_END}\noutro\n", encoding="utf-8")
    report = tmp_path / "REPORT.md"
    args = ["--gt", str(gt_dir), "--runs", str(runs), "--captures", str(tmp_path / "none"), "--manifest", str(manifest),
            "--apps", str(apps), "--report", str(report), "--readme", str(readme)]
    assert main(args) == 0
    text = report.read_text(encoding="utf-8")
    assert "## b1_rep1 (lidar), pipeline at `" in text
    assert "| -1.3 % | -2.5 cm (-0.8 %) | -1.9 % | 1 of 4 within 2 cm, 0 phantom | 5 of 7 |" in text
    assert "| Wall 2 | 5.600 | 5.528 [5.478, 5.578] | -7.2 cm (-1.3 %) | 98.7 % | ±2 cm | miss by 5.2 cm | no |" in text
    assert "Score 1 / (4 + 0) = 25 % (gate ≥ 85 %): miss." in text
    assert "3 missed (not detected: Door 2 width, Window 1 width, Window 2 width), 0 phantom" in text
    assert "Tape value inside the 90 % interval: 5 of 7 measurements." in text
    assert "within 1.9 % of the tape value (98.1 % accuracy or better on each); 1 of 6 strict gates pass" in text
    assert "| Wall 1 | 4.350 | 4.324 | 4.360 | -2.6 cm | +1.0 cm | lose |" in text
    assert "| Window 1 width | 0.700 | not detected | 0.692 | — | -0.8 cm | lose |" in text
    assert "Beat or tie on 0 of 6 measurements (gate ≥ 70 %; tie = errors within 3 mm): miss." in text
    assert "todo" not in text and "fixture" not in text and "FAIL" not in text

    block = readme.read_text(encoding="utf-8")
    assert block.startswith("intro\n" + README_START) and block.endswith(README_END + "\noutro\n") and "old" not in block
    assert "| Wall 1 | 4.350 | 4.324 [4.274, 4.374] | -2.6 cm (-0.6 %) | 4.360 | +1.0 cm (+0.2 %) |" in block
    assert "| Floor area (m²) | 24.360 | 23.900 [22.400, 25.400] | -0.46 m² (-1.9 %) | 24.320 | -0.04 m² (-0.2 %) |" in block
    assert "| Ceiling height | 2.985 | 2.960 [2.910, 3.010] | -2.5 cm (-0.8 %) | — | — |" in block
    assert "| Window 1 width | 0.700 | not detected | — | 0.692 | -0.8 cm (-1.1 %) |" in block
    assert "| Door 2 width | 0.889 | not detected | — | — | — |" in block
    assert "Ceiling height ±1.5 cm: miss by 1.0 cm" in block and "head-to-head ≥ 70 % beat or tie: 0 of 6 (miss)" in block


def test_skip_current_reports_only_refs(tmp_path):
    gt_dir = tmp_path / "gt"
    gt_dir.mkdir()
    (gt_dir / "b1_rep1.json").write_text(json.dumps(GT), encoding="utf-8")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("capture_id,tier\nb1_rep1,lidar\n", encoding="utf-8")
    report = tmp_path / "REPORT.md"
    args = ["--gt", str(gt_dir), "--runs", str(tmp_path / "runs"), "--captures", str(tmp_path / "none"),
            "--manifest", str(manifest), "--apps", str(tmp_path / "apps"), "--report", str(report), "--skip-current"]
    assert main(args) == 0
    text = report.read_text(encoding="utf-8")
    assert "--skip-current" in text and "## b1_rep1" not in text
