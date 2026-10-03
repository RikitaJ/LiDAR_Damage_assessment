"""Deterministic concealed-damage rules (brief §5.8, configs/concealed_rules.json)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "configs" / "concealed_rules.json"

_WET_ROOM_HINTS = ("bath", "kitchen", "wc", "toilet", "utility", "laundry")


def load_concealed_rules() -> list[dict]:
    if not RULES_PATH.is_file():
        return []
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return list(data.get("rules") or [])


def evaluate_concealed_flags(
    damage_regions: list[dict],
    surfaces: list[dict],
    rooms: list[dict],
    *,
    adjacency: list[tuple[str, str, str]] | None = None,
) -> list[dict]:
    rules = load_concealed_rules()
    by_surface = {s["id"]: s for s in surfaces}
    room_names = {r["room_id"]: (r.get("name") or "").lower() for r in rooms}
    flags: list[dict] = []
    seen: set[str] = set()

    for dmg in damage_regions:
        if dmg.get("class") not in ("water_stain", "crack", "mold"):
            continue
        sid = dmg.get("surface_id") or ""
        surf = by_surface.get(sid)
        stype = surf["type"] if surf else "wall"
        for rule in rules:
            rid = rule["id"]
            match = rule.get("match") or {}
            if match.get("class") and match["class"] != dmg.get("class"):
                continue
            if match.get("surface_type") and match["surface_type"] != stype:
                continue
            if not _rule_fires(match, dmg, surf, room_names, adjacency or []):
                continue
            key = f"{rid}:{sid}:{dmg.get('id')}"
            if key in seen:
                continue
            seen.add(key)
            flags.append(
                {
                    "id": f"F-{len(flags) + 1}",
                    "rule_id": rid,
                    "rule": rule.get("description", rid),
                    "triggered_by": [dmg.get("id", "")],
                    "surfaces": [sid] if sid else [],
                    "rationale": _rationale(rule, dmg),
                }
            )
    return flags


def _rule_fires(
    match: dict,
    dmg: dict,
    surf: dict | None,
    room_names: dict[str, str],
    adjacency: list[tuple[str, str, str]],
) -> bool:
    if "bottom_above_floor_m_max" in match:
        bottom = _meas(dmg, "bottom_above_floor_m")
        if bottom is None or bottom > float(match["bottom_above_floor_m_max"]):
            return False
        return True
    if match.get("adjacent_wet_room"):
        if not surf:
            return False
        rid = surf.get("room_id", "")
        if any(h in room_names.get(rid, "") for h in _WET_ROOM_HINTS):
            return True
        for a, b, _ in adjacency:
            other = b if a == rid else a if b == rid else None
            if other and any(h in room_names.get(other, "") for h in _WET_ROOM_HINTS):
                return True
        return False
    if match.get("diagonal_from_opening"):
        return bool(dmg.get("diagonal_from_opening"))
    if match.get("margin_m") is not None and dmg.get("class") == "mold":
        return True
    if match.get("surface_type") == "ceiling" and dmg.get("class") == "water_stain":
        return surf is not None and surf.get("type") == "ceiling"
    return True


def _meas(dmg: dict, key: str) -> float | None:
    field = dmg.get(key)
    if isinstance(field, dict):
        try:
            return float(field.get("value_m", field.get("value")))
        except (TypeError, ValueError):
            return None
    try:
        return float(field) if field is not None else None
    except (TypeError, ValueError):
        return None


def _rationale(rule: dict, dmg: dict) -> str:
    return f"{rule.get('id')}: class={dmg.get('class')} surface={dmg.get('surface_id')}"
