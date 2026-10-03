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
    items.extend(_moisture_items_from_concealed(concealed_flags, by_surface, tier))
    return items


_MOISTURE_CONCEALED = frozenset({"CD-01", "CD-02"})


def _moisture_items_from_concealed(
    concealed_flags: list[dict],
    by_surface: dict[str, dict],
    tier: InputTier,
) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for flag in concealed_flags:
        rid = flag.get("rule_id")
        if rid not in _MOISTURE_CONCEALED:
            continue
        for sid in flag.get("surfaces") or []:
            key = (sid, "MOISTURE-INSP")
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "id": f"S-moist-{len(out) + 1}",
                    "surface_id": sid,
                    "code": "MOISTURE-INSP",
                    "description": "Moisture inspection (concealed-damage rule)",
                    "unit": "each",
                    "quantity": with_interval(1.0, 0.0, notes=f"concealed_{rid}", tier=tier, kind="opening"),
                    "because": [flag.get("id", ""), *(flag.get("triggered_by") or [])],
                }
            )
    return out


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
    poly = dmg.get("polygon_surface")
    if poly and len(poly) >= 3:
        area = _polygon_area_m2(poly)
        if area > 0:
            return area
    fa = dmg.get("area_m2") or dmg.get("floor_area_m2")
    if isinstance(fa, dict):
        return float(fa.get("value_m", 0.05))
    try:
        return float(fa) if fa else 0.05
    except (TypeError, ValueError):
        return 0.05


def _polygon_area_m2(poly: list) -> float:
    try:
        pts = [(float(p[0]), float(p[1])) for p in poly]
    except (TypeError, ValueError, IndexError):
        return 0.0
    if len(pts) < 3:
        return 0.0
    area = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        area += x0 * y1 - x1 * y0
    return abs(area) / 2.0
