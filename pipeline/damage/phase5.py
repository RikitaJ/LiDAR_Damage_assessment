"""Phase 5 orchestration: surfaces → detect → concealed → scope."""

from __future__ import annotations

from pathlib import Path

from pipeline.config import InputTier
from pipeline.damage.concealed import evaluate_concealed_flags
from pipeline.damage.detect import detect_damage_regions
from pipeline.damage.limitations import collect_damage_limitations, widen_heuristic_regions
from pipeline.damage.sanitize import apply_r39_surface_review
from pipeline.damage.scope_engine import build_scope_line_items
from pipeline.damage.surfaces import build_surfaces


def run_damage_pipeline(
    rooms: list[dict],
    qa_warnings: list[str],
    capture_root: Path,
    tier: InputTier,
    *,
    adjacency: list[tuple[str, str, str]] | None = None,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[str], list[str]]:
    """Returns surfaces, damage_regions, concealed_flags, scope_items, warnings, limitations."""
    warnings: list[str] = []
    if not rooms:
        warnings.append("damage: empty rooms list — surfaces and damage omitted")
        return [], [], [], [], warnings, collect_damage_limitations(
            tier=tier,
            capture_root=capture_root,
            rooms=[],
            damage_regions=[],
            scope_items=[],
            qa_warnings=qa_warnings,
        )

    surfaces = build_surfaces(rooms, tier)
    regions, dw = detect_damage_regions(rooms, capture_root, tier)
    warnings.extend(apply_r39_surface_review(regions, qa_warnings))
    widen_heuristic_regions(regions)
    warnings.extend(dw)

    for w in qa_warnings:
        low = w.lower()
        if "mirror" in low or "glass" in low or "r39" in low:
            warnings.append(f"damage: surface review — {w[:120]}")

    concealed = evaluate_concealed_flags(regions, surfaces, rooms, adjacency=adjacency)
    concealed.extend(_qa_concealed(qa_warnings))
    scope = build_scope_line_items(regions, concealed, surfaces, tier)
    if not scope and regions:
        scope = [
            {
                "id": "S0",
                "surface_id": regions[0].get("surface_id", ""),
                "code": "VERIFY-DAMAGE",
                "description": "Verify detected damage regions",
                "unit": "each",
                "quantity": {"value_m": 1.0, "lo": 1.0, "hi": 1.0, "confidence": {"sigma_m": 0, "tier_floor_m": 0, "notes": "fallback"}},
                "because": [regions[0].get("id", "")],
            }
        ]
    limitations = collect_damage_limitations(
        tier=tier,
        capture_root=capture_root,
        rooms=rooms,
        damage_regions=regions,
        scope_items=scope,
        qa_warnings=qa_warnings,
    )
    return surfaces, regions, concealed, scope, warnings, limitations


def _qa_concealed(qa_warnings: list[str]) -> list[dict]:
    flags: list[dict] = []
    for w in qa_warnings:
        low = w.lower()
        if "sparse depth" in low or "sparse floor" in low:
            flags.append(
                {
                    "id": f"F-qa-{len(flags) + 1}",
                    "rule_id": "QA-GEOMETRY",
                    "rule": "Sparse geometry — damage extent uncertain",
                    "triggered_by": [],
                    "surfaces": [],
                    "rationale": w[:200],
                }
            )
    return flags
