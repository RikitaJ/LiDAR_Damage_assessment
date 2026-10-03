"""Phase 5 v0: rule-based damage hints + optional Vision tags (no GT in pipeline)."""

from __future__ import annotations

from pathlib import Path

from pipeline.config import InputTier
from pipeline.frontends.video import find_video_file


def infer_damage_regions(
    rooms: list[dict],
    qa_warnings: list[str],
    capture_root: Path,
    tier: InputTier,
) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    regions: list[dict] = []

    for w in qa_warnings:
        low = w.lower()
        if "r39" in low or "glass" in low or "mirror" in low:
            regions.append(
                {
                    "kind": "surface_risk",
                    "severity": "review",
                    "notes": w,
                    "source": "qa_rule_v0",
                }
            )
        if "sparse depth" in low or "sparse floor" in low:
            regions.append(
                {
                    "kind": "geometry_uncertainty",
                    "severity": "info",
                    "notes": w,
                    "source": "qa_rule_v0",
                }
            )

    if tier == InputTier.LIDAR and (capture_root / "odometry.csv").is_file():
        regions.append(
            {
                "kind": "capture_lidar_scan",
                "severity": "info",
                "notes": "Stray depth capture; manual damage markup not automated in v0",
                "source": "tier_rule_v0",
            }
        )

    video = find_video_file(capture_root)
    if video and tier in (InputTier.VIDEO, InputTier.LIDAR):
        try:
            from pipeline.integrations.azure_photo_vlm import azure_vision_damage_tags

            tags, vw = azure_vision_damage_tags(_sample_frame_path(capture_root, video))
            warnings.extend(vw)
            for tag in tags:
                regions.append(
                    {
                        "kind": "vision_tag",
                        "severity": "review",
                        "notes": tag,
                        "source": "azure_vision_optional",
                    }
                )
        except ImportError:
            pass

    return regions, warnings


def build_scope_line_items(
    qa_warnings: list[str],
    damage_regions: list[dict],
    tier: InputTier,
) -> list[dict]:
    items: list[dict] = []
    if damage_regions:
        items.append(
            {
                "item": "verify_flagged_regions",
                "tier": tier.value,
                "count": len(damage_regions),
                "notes": "Automated hints only — not a repair estimate",
            }
        )
    if qa_warnings:
        items.append(
            {
                "item": "address_qa_warnings",
                "tier": tier.value,
                "notes": qa_warnings[0][:200],
            }
        )
    return items


def _sample_frame_path(capture_root: Path, video: Path) -> Path:
    """Use first photo still if present, else video path (Vision may reject video — best-effort)."""
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        hits = sorted(capture_root.glob(ext))
        if hits:
            return hits[0]
    photos = capture_root / "photos"
    if photos.is_dir():
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            hits = sorted(photos.glob(ext))
            if hits:
                return hits[0]
    return video
