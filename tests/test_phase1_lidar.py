from pathlib import Path

from pipeline.config import RunConfig
from pipeline.run import run_lidar

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "benchmark_sample"


def test_lidar_pipeline_produces_valid_plan():
    out = run_lidar(SAMPLE, SAMPLE / "out_phase1", RunConfig())
    data = out.read_text(encoding="utf-8")
    assert "stitched_plan" in data
    assert "living_room" in data
    assert (SAMPLE / "out_phase1" / "floorplan.png").exists()


def test_wall_lengths_match_roomplan():
    out = run_lidar(SAMPLE, SAMPLE / "out_phase1_b", RunConfig())
    import json

    plan = json.loads(out.read_text(encoding="utf-8"))
    living = next(r for r in plan["rooms"] if r["room_id"] == "living_room")
    lengths = sorted(w["length_m"]["value_m"] for w in living["walls"])
    assert 3.5 in lengths and 4.2 in lengths


def test_living_room_floor_area_realistic():
    import json

    out = run_lidar(SAMPLE, SAMPLE / "out_phase1_c", RunConfig())
    plan = json.loads(out.read_text(encoding="utf-8"))
    living = next(r for r in plan["rooms"] if r["room_id"] == "living_room")
    area = living["floor_area_m2"]["value_m"]
    assert 14.0 <= area <= 15.5
