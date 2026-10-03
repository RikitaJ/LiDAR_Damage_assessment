"""Photo tier v0: manifest rooms/*/photos → widened single-room priors (offline)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.config import InputTier, SIGMA
from pipeline.measure.intervals import with_interval

PHOTO_EXT = (".jpg", ".jpeg", ".png", ".heic", ".webp")


def parse_photo_room(room_dir: Path, room_id: str, name: str) -> tuple[dict[str, Any], list[str]]:
    tier = InputTier.PHOTOS
    warnings: list[str] = []
    photos = room_dir / "photos"
    if not photos.is_dir():
        photos = room_dir
    files = sorted(
        p for p in photos.iterdir() if p.is_file() and p.suffix.lower() in PHOTO_EXT
    )
    n = len(files)
    if n == 0:
        warnings.append("no photos found; emitting wide placeholder room")
        n = 4

    # Offline prior: more photos → slightly tighter guess, still wide vs LiDAR.
    side = 3.5 + max(0, 6 - n) * 0.35
    area = side * side * 0.85
    sigma_w = max(SIGMA[tier].length_m, side * SIGMA[tier].footprint_rel)
    sigma_a = max(SIGMA[tier].footprint_rel * area, area * 0.12)

    corners = [
        [0.0, 0.0],
        [side, 0.0],
        [side, side * 0.85],
        [0.0, side * 0.85],
    ]
    walls = []
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        length = float(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5)
        walls.append(
            {
                "id": f"{room_id}-W{i + 1}",
                "length_m": with_interval(length, sigma_w, notes="photo_v0_prior", tier=tier, kind="wall"),
                "polyline_m": [a, b],
                "openings": [],
            }
        )

    room = {
        "room_id": room_id,
        "name": name,
        "floor_area_m2": with_interval(
            area, sigma_a, notes="photo_v0_prior", tier=tier, kind="footprint"
        ),
        "ceiling_height_m": with_interval(
            2.5, SIGMA[tier].height_m * 2, notes="photo_v0_prior", tier=tier, kind="height"
        ),
        "walls": walls,
        "pose_world": {"translation_m": [side / 2, 0.0, side * 0.425], "rotation_quat": [0, 0, 0, 1]},
        "_orphan_openings": [],
    }

    from pipeline.integrations.azure_photo_vlm import estimate_room_from_photos

    est, vw = estimate_room_from_photos(files)
    warnings.extend(vw)
    if est:
        _merge_vlm_estimate(room, est, tier)
    else:
        warnings.append(f"photo v0: {n} stills; offline prior only")
    return room, warnings


def _merge_vlm_estimate(room: dict, est: dict, tier: InputTier) -> None:
    try:
        area = float(est["floor_area_m2"])
        ceil = float(est.get("ceiling_height_m", 2.5))
        lengths = est.get("wall_lengths_m") or []
    except (KeyError, TypeError, ValueError):
        return
    if area > 2.0:
        sig = max(area * SIGMA[tier].footprint_rel * 1.2, area * 0.1)
        room["floor_area_m2"] = with_interval(area, sig, notes="photo_vlm", tier=tier, kind="footprint")
    if ceil > 1.8:
        room["ceiling_height_m"] = with_interval(
            ceil, SIGMA[tier].height_m * 2, notes="photo_vlm", tier=tier, kind="height"
        )
    if isinstance(lengths, list) and len(lengths) >= 4 and len(room.get("walls", [])) >= 4:
        for i, w in enumerate(room["walls"][:4]):
            try:
                L = float(lengths[i])
            except (TypeError, ValueError):
                continue
            w["length_m"] = with_interval(
                L, max(SIGMA[tier].length_m, L * 0.08), notes="photo_vlm", tier=tier, kind="wall"
            )
