"""Post-detect score + interval refinement."""

from __future__ import annotations

from pipeline.config import InputTier, SIGMA


def refine_region_confidence(regions: list[dict], tier: InputTier) -> list[str]:
    warnings: list[str] = []
    for reg in regions:
        src = str(reg.get("source", ""))
        views = int(reg.get("view_count", 1))
        if "merge_v2" in src and views >= 2:
            reg["score"] = min(0.92, float(reg.get("score", 0.5)) + 0.06)
        if float(reg.get("score", 0)) >= 0.72 and "azure_damage_vlm" in src:
            _tighten_intervals(reg, tier, factor=0.82)
        if views >= 3:
            reg["score"] = min(0.95, float(reg.get("score", 0.5)) + 0.04)
            warnings.append(f"damage: region {reg.get('id')} confirmed on {views} views")
    return warnings


def _tighten_intervals(reg: dict, tier: InputTier, *, factor: float) -> None:
    for key in ("area_m2", "width_m", "height_m", "bottom_above_floor_m"):
        field = reg.get(key)
        if not isinstance(field, dict):
            continue
        conf = dict(field.get("confidence") or {})
        sig = float(conf.get("sigma_m", SIGMA[tier].footprint_rel)) * factor
        v = float(field.get("value_m", field.get("value", 0)))
        half = 1.645 * max(sig, 1e-6)
        field["lo"] = v - half
        field["hi"] = v + half
        conf["sigma_m"] = sig
        conf["tier_floor_m"] = sig
        field["confidence"] = conf
