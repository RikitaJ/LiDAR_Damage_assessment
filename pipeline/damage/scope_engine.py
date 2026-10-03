"""Scope line items from damage + surfaces (configs/scope_rules.json)."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.config import InputTier, SIGMA
from pipeline.measure.intervals import with_interval

ROOT = Path(__file__).resolve().parents[2]
SCOPE_PATH = ROOT / "configs" / "scope_rules.json"
MARGIN_M = 0.15


def load_scope_mappings() -> list[dict]:
    if not SCOPE_PATH.is_file():
        return []
    return list(json.loads(SCOPE_PATH.read_text(encoding="utf-8")).get("mappings") or [])


def build_scope_line_items(
    damage_regions: list[dict],
    concealed_flags: list[dict],
    surfaces: list[dict],
    tier: InputTier,
) -> list[dict]:
    mappings = load_scope_mappings()
    by_surface = {s["id"]: s for s in surfaces}
    items: list[dict] = []
    seq = 0

    for dmg in damage_regions:
        cls = dmg.get("class")
        sid = dmg.get("surface_id") or ""
        surf = by_surface.get(sid)
        stype = surf["type"] if surf else "wall"
        for mapping in mappings:
            if mapping.get("damage_class") != cls:
                continue
            if mapping.get("surface_type") != stype:
                continue
            for spec in mapping.get("items") or []:
                seq += 1
                qty = _quantity(spec.get("quantity"), dmg, surf, tier)
                items.append(
                    {
                        "id": f"S{seq}",
                        "surface_id": sid,
                        "code": spec.get("code", "ITEM"),
                        "description": spec.get("description", ""),
                        "unit": "m2" if qty.get("value_m", 0) != 1 else "each",
                        "quantity": qty,
                        "because": [dmg.get("id", ""), *[f["id"] for f in concealed_flags if sid in f.get("surfaces", [])]],
                    }
                )
    return items


def _quantity(kind: str | None, dmg: dict, surf: dict | None, tier: InputTier) -> dict:
    if kind == "fixed_1":
        return with_interval(1.0, 0.0, notes="scope_fixed", tier=tier, kind="opening")
    if kind == "surface_net_area_m2" and surf:
        return dict(surf["net_area_m2"])
    area = _damage_area(dmg)
    if kind in ("damage_area_with_margin_m2", "damage_area_m2"):
        if kind == "damage_area_with_margin_m2":
            side = (area**0.5 + MARGIN_M) ** 2
            return with_interval(side, side * 0.2, notes="scope_patch", tier=tier, kind="footprint")
        return with_interval(max(area, 0.05), max(area * 0.25, SIGMA[tier].footprint_rel), notes="scope_damage", tier=tier, kind="footprint")
    return with_interval(max(area, 0.05), max(area * 0.25, SIGMA[tier].footprint_rel), notes="scope_damage", tier=tier, kind="footprint")


def _damage_area(dmg: dict) -> float:
    fa = dmg.get("area_m2") or dmg.get("floor_area_m2")
    if isinstance(fa, dict):
        return float(fa.get("value_m", 0.05))
    try:
        return float(fa) if fa else 0.05
    except (TypeError, ValueError):
        return 0.05
