from pathlib import Path

from pipeline.config import InputTier
from pipeline.damage.concealed import evaluate_concealed_flags
from pipeline.damage.phase5 import run_damage_pipeline
from pipeline.damage.scope_engine import build_scope_line_items
from pipeline.damage.surfaces import build_surfaces
from pipeline.measure.intervals import with_interval


def _sample_room(*, name: str = "bedroom") -> dict:
    tier = InputTier.LIDAR
    return {
        "room_id": "R1",
        "name": name,
        "pose_world": {"translation_m": [0.0, 0.0, 0.0]},
        "ceiling_height_m": with_interval(2.5, 0.1, notes="test", tier=tier, kind="height"),
        "floor_area_m2": with_interval(12.0, 0.4, notes="test", tier=tier, kind="footprint"),
        "walls": [
            {
                "id": "R1-W1",
                "length_m": with_interval(4.0, 0.1, notes="test", tier=tier, kind="wall"),
                "polyline_m": [[0.0, 0.0], [4.0, 0.0]],
                "openings": [],
            }
        ],
    }


def _water_stain_low() -> dict:
    tier = InputTier.LIDAR
    return {
        "id": "D1",
        "surface_id": "R1-W1",
        "class": "water_stain",
        "polygon_surface": [[0.2, 0.1], [0.5, 0.1], [0.5, 0.4], [0.2, 0.4]],
        "area_m2": with_interval(0.12, 0.04, notes="test", tier=tier, kind="footprint"),
        "bottom_above_floor_m": with_interval(0.15, 0.05, notes="test", tier=tier, kind="height"),
    }


def test_surfaces_net_area():
    rooms = [_sample_room()]
    surfaces = build_surfaces(rooms, InputTier.LIDAR)
    wall = next(s for s in surfaces if s["type"] == "wall")
    assert wall["id"] == "R1-W1"
    assert wall["net_area_m2"]["value_m"] > 9.0


def test_concealed_cd01_fires():
    rooms = [_sample_room()]
    surfaces = build_surfaces(rooms, InputTier.LIDAR)
    flags = evaluate_concealed_flags([_water_stain_low()], surfaces, rooms)
    assert any(f["rule_id"] == "CD-01" for f in flags)


def test_scope_from_water_stain():
    rooms = [_sample_room()]
    surfaces = build_surfaces(rooms, InputTier.LIDAR)
    dmg = _water_stain_low()
    flags = evaluate_concealed_flags([dmg], surfaces, rooms)
    items = build_scope_line_items([dmg], flags, surfaces, InputTier.LIDAR)
    codes = {i["code"] for i in items}
    assert "PAINT-WALL" in codes
    assert "STAIN-BLOCK-PRIME" in codes
    assert "MOISTURE-INSP" in codes


def test_run_damage_pipeline_qa_concealed():
    rooms = [_sample_room()]
    surfaces, regions, concealed, scope, _, limits = run_damage_pipeline(
        rooms,
        ["sparse depth on floor — widen intervals"],
        Path("."),
        InputTier.LIDAR,
    )
    assert limits
    assert surfaces
    assert any(f.get("rule_id") == "QA-GEOMETRY" for f in concealed)


def test_plan_render_accepts_damage(tmp_path):
    from pipeline.export.plan_render import render_plan

    rooms = [_sample_room()]
    stitched = {"footprint_area_m2": {"value_m": 12.0}, "global_walls": []}
    png = tmp_path / "plan.png"
    render_plan(stitched, rooms, png, damage_regions=[_water_stain_low()])
    assert png.is_file() and png.stat().st_size > 500
