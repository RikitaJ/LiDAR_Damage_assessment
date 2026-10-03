from pipeline.config import InputTier
from pipeline.damage.cluster import cluster_cross_view_hits
from pipeline.damage.scope_engine import _damage_area, build_scope_line_items
from pipeline.measure.intervals import with_interval


def test_cluster_merges_same_u_across_views():
    room = {"room_id": "R1", "walls": [{"id": "R1-W1", "length_m": {"value_m": 4.0}}]}
    h1 = {"class": "water_stain", "u_center_frac": 0.35, "score": 0.5, "source": "a"}
    h2 = {"class": "water_stain", "u_center_frac": 0.38, "score": 0.55, "source": "b"}
    out = cluster_cross_view_hits([(room, h1), (room, h2)])
    assert len(out) == 1
    _, merged = out[0]
    assert merged.get("view_count", 1) >= 2
    assert "multi_view" in merged.get("source", "")


def test_damage_area_from_polygon():
    tier = InputTier.LIDAR
    dmg = {
        "polygon_surface": [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]],
        "area_m2": with_interval(0.05, 0.01, notes="stale", tier=tier, kind="footprint"),
    }
    assert abs(_damage_area(dmg) - 2.0) < 1e-6


def test_scope_polygon_drives_stain_prime_qty():
    tier = InputTier.LIDAR
    surfaces = [
        {
            "id": "R1-W1",
            "type": "wall",
            "net_area_m2": with_interval(10.0, 0.5, notes="t", tier=tier, kind="footprint"),
        }
    ]
    dmg = {
        "id": "D1",
        "surface_id": "R1-W1",
        "class": "water_stain",
        "polygon_surface": [[0.0, 0.0], [1.0, 0.0], [1.0, 0.5], [0.0, 0.5]],
        "area_m2": with_interval(0.02, 0.01, notes="t", tier=tier, kind="footprint"),
    }
    items = build_scope_line_items([dmg], [], surfaces, tier)
    prime = next(i for i in items if i["code"] == "STAIN-BLOCK-PRIME")
    assert abs(prime["quantity"]["value_m"] - 0.5) < 1e-6
