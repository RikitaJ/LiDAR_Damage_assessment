"""Photo tier: rooms/*/photos → MVS cues + priors + optional Azure VLM layout."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.config import InputTier, SIGMA
from pipeline.frontends.photo_aspect import median_aspect_long_over_short
from pipeline.frontends.photo_exif import exif_summary
from pipeline.frontends.photo_pick import pick_spaced_photos
from pipeline.frontends.photo_mvs import run_photo_mvs
from pipeline.geometry.photo_metric import (
    apply_aspect_ratio_hint,
    apply_metric_to_estimate,
    prior_metric_scale,
    refine_rectangle_lengths,
    reject_implausible_estimate,
)
from pipeline.geometry.photo_rect import manhattan_room_from_wall_lengths, rectangle_room_from_wall_lengths
from pipeline.geometry.photo_scale import combined_scale_sigma_rel, room_wall_span_m
from pipeline.geometry.photo_priors import CEILING_PRIOR_M
from pipeline.measure.intervals import interval_notes, with_interval

PHOTO_EXT = (".jpg", ".jpeg", ".png", ".heic", ".webp")
DEFAULT_DOOR_WIDTH_M = 0.9
MAX_VLM_PHOTOS = 8


def parse_photo_room(room_dir: Path, room_id: str, name: str) -> tuple[dict[str, Any], list[str]]:
    tier = InputTier.PHOTOS
    warnings: list[str] = []
    if not room_dir.is_dir():
        warnings.append(f"photo: missing room folder {room_dir.name}; wide placeholder")

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

    exif_meta, exif_warn = exif_summary(files)
    warnings.extend(exif_warn)

    side = 3.5 + max(0, 6 - n) * 0.35
    area = side * side * 0.85
    lengths = [side, side * 0.85, side, side * 0.85]
    room = rectangle_room_from_wall_lengths(
        room_id,
        name,
        lengths,
        tier=tier,
        ceiling_m=2.5,
        area_m2=area,
        notes="photo_v0_prior",
    )

    mvs = run_photo_mvs(files)
    warnings.extend(mvs.warnings)

    from pipeline.integrations.azure_photo_vlm import estimate_room_from_photos_merged

    aspect_hint, aspect_warn = median_aspect_long_over_short(files)
    warnings.extend(aspect_warn)

    vlm_files = pick_spaced_photos(files, min(MAX_VLM_PHOTOS, max(3, n)))
    est, vw = estimate_room_from_photos_merged(vlm_files)
    warnings.extend(vw)
    vlm_used = False
    metric_spread = 0.0
    if est:
        ok, reason = reject_implausible_estimate(est)
        if not ok:
            warnings.append(f"photo_vlm: rejected ({reason}); offline prior kept")
        else:
            scale, metric_spread, mw = prior_metric_scale(est)
            warnings.extend(mw)
            est = apply_metric_to_estimate(est, scale)
            room = _apply_vlm_estimate(
                room_id, name, est, tier, room, aspect_hint=aspect_hint
            )
            vlm_used = True

    if not vlm_used:
        warnings.append(f"photo: {n} stills; offline prior (Azure optional via .env)")
        if aspect_hint:
            lens = refine_rectangle_lengths(
                [float(w["length_m"]["value_m"]) for w in room["walls"]],
                target_area_m2=float(room["floor_area_m2"]["value_m"]),
            )
            lens, aw2 = apply_aspect_ratio_hint(lens, aspect_hint)
            warnings.extend(aw2)
            room = rectangle_room_from_wall_lengths(
                room_id,
                name,
                lens,
                tier=tier,
                ceiling_m=float(room["ceiling_height_m"]["value_m"]),
                area_m2=float(room["floor_area_m2"]["value_m"]),
                notes="photo_aspect_prior",
            )

    ceil = float(room["ceiling_height_m"]["value_m"])
    if vlm_used:
        ceil_est = est.get("ceiling_height_m") if est else None
        try:
            c = float(ceil_est) if ceil_est is not None else ceil
            if CEILING_PRIOR_M[0] <= c <= CEILING_PRIOR_M[1] + 0.35:
                room["ceiling_height_m"]["value_m"] = c
                room["ceiling_height_m"]["value"] = c
        except (TypeError, ValueError):
            pass
        ceil = float(room["ceiling_height_m"]["value_m"])

    sigma_rel, scale_warn = combined_scale_sigma_rel(
        n if files else 4,
        vlm_used=vlm_used,
        ceiling_m=ceil,
        mvs=mvs,
        room_span_m=room_wall_span_m(room),
        metric_cue_spread=metric_spread,
    )
    warnings.extend(scale_warn)
    if not vlm_used and mvs.n_triangulated >= 12:
        warnings.append("photo: sparse multi-view scale cue applied (no dense depth model)")

    _ensure_connector_door(room, room_id, tier, prefer_longest_wall=vlm_used)
    _widen_intervals_for_scale_sigma(room, tier, sigma_rel)
    return room, warnings


def _apply_vlm_estimate(
    room_id: str,
    name: str,
    est: dict,
    tier: InputTier,
    fallback: dict,
    *,
    aspect_hint: float | None = None,
) -> dict:
    if est.get("floor_area_m2") is None:
        return fallback
    try:
        area = float(est["floor_area_m2"])
        ceil = float(est.get("ceiling_height_m") or 2.5)
        lengths = est.get("wall_lengths_m") or []
    except (TypeError, ValueError):
        return fallback
    if not isinstance(lengths, list) or len(lengths) < 4:
        return fallback
    try:
        lens = [float(x) for x in lengths if x is not None]
    except (TypeError, ValueError):
        return fallback
    if len(lens) < 4:
        return fallback

    if len(lens) == 4:
        lens = refine_rectangle_lengths(lens, target_area_m2=area if area > 2.0 else None)
        lens, _ = apply_aspect_ratio_hint(lens, aspect_hint)
        rebuilt = rectangle_room_from_wall_lengths(
            room_id,
            name,
            lens,
            tier=tier,
            ceiling_m=ceil if ceil > 1.8 else 2.5,
            area_m2=area if area > 2.0 else None,
            notes="photo_vlm",
        )
    else:
        rebuilt = manhattan_room_from_wall_lengths(
            room_id,
            name,
            lens,
            tier=tier,
            ceiling_m=ceil if ceil > 1.8 else 2.5,
            area_m2=area if area > 2.0 else None,
            notes="photo_vlm",
        )

    openings = est.get("openings")
    if isinstance(openings, list) and openings:
        _apply_openings_from_vlm(rebuilt, room_id, tier, openings)
    else:
        door = est.get("door_on_wall")
        try:
            wall_idx = int(door) if door is not None else -1
        except (TypeError, ValueError):
            wall_idx = -1
        if 0 <= wall_idx < len(rebuilt["walls"]):
            _add_door(rebuilt, wall_idx, room_id, tier, est.get("door_width_m"))
    return rebuilt


def _apply_openings_from_vlm(
    room: dict,
    room_id: str,
    tier: InputTier,
    openings: list[Any],
) -> None:
    walls = room.get("walls") or []
    for i, raw in enumerate(openings):
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "door").lower()
        if kind not in ("door", "window", "passage"):
            kind = "door"
        try:
            widx = int(raw.get("wall_index", raw.get("wall", 0)))
        except (TypeError, ValueError):
            widx = 0
        if widx < 0 or widx >= len(walls):
            continue
        width = raw.get("width_m", DEFAULT_DOOR_WIDTH_M)
        if kind == "window":
            _add_window(walls[widx], widx, room_id, tier, width, raw, suffix=i)
        else:
            _add_door(room, widx, room_id, tier, width, suffix=i)


def _ensure_connector_door(
    room: dict,
    room_id: str,
    tier: InputTier,
    *,
    prefer_longest_wall: bool,
) -> None:
    if any(w.get("openings") for w in room.get("walls", [])):
        return
    idx = 0
    if prefer_longest_wall:
        walls = room.get("walls") or []
        if walls:
            idx = max(
                range(len(walls)),
                key=lambda i: float(walls[i]["length_m"]["value_m"]),
            )
    _add_door(room, idx, room_id, tier, DEFAULT_DOOR_WIDTH_M)


def _widen_intervals_for_scale_sigma(room: dict, tier: InputTier, sigma_rel: float) -> None:
    for w in room.get("walls", []):
        lm = w.get("length_m") or {}
        v = float(lm.get("value_m", 0))
        extra = max(v * sigma_rel, SIGMA[tier].length_m)
        w["length_m"] = with_interval(
            v, extra, notes=interval_notes(lm, "photo"), tier=tier, kind="wall"
        )
    fa = room.get("floor_area_m2") or {}
    av = float(fa.get("value_m", 0))
    room["floor_area_m2"] = with_interval(
        av,
        max(av * sigma_rel, av * 0.12),
        notes=interval_notes(fa, "photo"),
        tier=tier,
        kind="footprint",
    )
    ch = room.get("ceiling_height_m") or {}
    cv = float(ch.get("value_m", 0))
    if cv > 0:
        room["ceiling_height_m"] = with_interval(
            cv,
            max(SIGMA[tier].height_m * 2, cv * sigma_rel),
            notes=interval_notes(ch, "photo"),
            tier=tier,
            kind="height",
        )


def _add_door(
    room: dict,
    wall_idx: int,
    room_id: str,
    tier: InputTier,
    width: Any,
    *,
    suffix: int = 0,
) -> None:
    walls = room.get("walls") or []
    if wall_idx >= len(walls):
        return
    try:
        w_m = float(width) if width is not None else DEFAULT_DOOR_WIDTH_M
    except (TypeError, ValueError):
        w_m = DEFAULT_DOOR_WIDTH_M
    w_m = max(0.65, min(w_m, 1.4))
    wall = walls[wall_idx]
    pl = wall.get("polyline_m") or []
    if len(pl) < 2:
        return
    p0, p1 = pl[0], pl[1]
    mid = [(float(p0[0]) + float(p1[0])) / 2, (float(p0[1]) + float(p1[1])) / 2]
    sig = max(SIGMA[tier].opening_m, w_m * 0.1)
    wall.setdefault("openings", []).append(
        {
            "id": f"{room_id}-door{suffix}",
            "kind": "door",
            "width_m": with_interval(w_m, sig, notes="photo_connector", tier=tier, kind="opening"),
            "height_m": with_interval(2.05, SIGMA[tier].height_m, notes="photo", tier=tier, kind="height"),
            "wall_id": wall["id"],
            "anchor_m": mid,
        }
    )


def _add_window(
    wall: dict,
    wall_idx: int,
    room_id: str,
    tier: InputTier,
    width: Any,
    raw: dict,
    *,
    suffix: int,
) -> None:
    try:
        w_m = float(width) if width is not None else 1.0
    except (TypeError, ValueError):
        w_m = 1.0
    w_m = max(0.4, min(w_m, 2.5))
    pl = wall.get("polyline_m") or []
    if len(pl) < 2:
        return
    p0, p1 = pl[0], pl[1]
    mid = [(float(p0[0]) + float(p1[0])) / 2, (float(p0[1]) + float(p1[1])) / 2]
    try:
        h_m = float(raw.get("height_m", 1.2))
        sill = float(raw.get("sill_m", 0.9))
    except (TypeError, ValueError):
        h_m, sill = 1.2, 0.9
    wall.setdefault("openings", []).append(
        {
            "id": f"{room_id}-window{suffix}",
            "kind": "window",
            "width_m": with_interval(w_m, w_m * 0.12, notes="photo_vlm", tier=tier, kind="opening"),
            "height_m": with_interval(h_m, SIGMA[tier].height_m, notes="photo_vlm", tier=tier, kind="height"),
            "sill_height_m": with_interval(sill, SIGMA[tier].height_m, notes="photo_vlm", tier=tier, kind="height"),
            "wall_id": wall["id"],
            "anchor_m": mid,
        }
    )
