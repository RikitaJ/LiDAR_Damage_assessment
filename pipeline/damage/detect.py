"""RGB damage: cached cues, room-aware walls, merge + optional Azure Vision."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pipeline.config import InputTier
from pipeline.frontends.photo_pick import pick_spaced_photos
from pipeline.frontends.video import find_video_file
from pipeline.damage.cache import (
    read_image_hits,
    read_vision_tags,
    write_image_hits,
    write_vision_tags,
)
from pipeline.damage.project import (
    annotate_opening_geometry,
    fuse_vision_with_regions,
    hit_to_region,
    merge_regions_on_surface,
    room_for_image,
)
from pipeline.damage.refine import refine_region_confidence
from pipeline.damage.sanitize import filter_hits, sanitize_damage_regions

MAX_DETECT_IMAGES = 12
MAX_VIDEO_FRAMES = 3
_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def count_rgb_samples(capture_root: Path, rooms: list[dict]) -> int:
    return len(_sample_images(capture_root, rooms))


def detect_damage_regions(
    rooms: list[dict],
    capture_root: Path,
    tier: InputTier,
) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    if not rooms:
        warnings.append("damage: no rooms in plan — skipping detection")
        return [], warnings

    images = pick_spaced_photos(_sample_images(capture_root, rooms), MAX_DETECT_IMAGES)
    if not images:
        warnings.append("damage: no RGB stills for detection; regions empty")
        return [], warnings
    if len(images) == 1:
        warnings.append("damage: single RGB still — limited multi-view confidence")

    provisional: list[dict] = []
    seq = 0
    cache_reads = 0
    rooms_without_walls: set[str] = set()
    unreadable = 0

    for img in images:
        if not img.is_file() or img.stat().st_size == 0:
            warnings.append(f"damage: skip empty file {img.name}")
            continue
        room = room_for_image(capture_root, img, rooms)
        if not room:
            warnings.append(f"damage: no room for image {img.name}")
            continue
        rid = room.get("room_id", "?")
        if not (room.get("walls") or []):
            if rid not in rooms_without_walls:
                rooms_without_walls.add(rid)
                warnings.append(f"damage: room {rid} has no walls — cues cannot attach to surfaces")
            continue

        hits, from_cache, w = _hits_for_image(img)
        warnings.extend(w)
        if from_cache:
            cache_reads += 1
        if w and any("unreadable" in x for x in w):
            unreadable += 1
        for hit in hits:
            seq += 1
            reg = hit_to_region(hit, room, tier, f"D{seq}")
            if reg:
                provisional.append(reg)

        tags, tw = _vision_tags_for_image(img)
        warnings.extend(tw)
        if tags:
            provisional = fuse_vision_with_regions(provisional, tags, room, tier)

    if cache_reads:
        warnings.append(f"damage: {cache_reads} image cue(s) from .cache/damage")
    if unreadable:
        warnings.append(f"damage: {unreadable} unreadable image(s) skipped")

    regions = merge_regions_on_surface(provisional, tier)
    annotate_opening_geometry(regions, rooms)
    regions, sw = sanitize_damage_regions(regions, tier)
    warnings.extend(sw)
    warnings.extend(refine_region_confidence(regions, tier))

    if not regions and any("azure_vision" in w for w in warnings):
        warnings.append("damage: vision tags did not map to surface regions")

    return regions, warnings


def _hits_for_image(image_path: Path) -> tuple[list[dict], bool, list[str]]:
    warnings: list[str] = []
    cached = read_image_hits(image_path)
    if cached is not None:
        filtered, fw = filter_hits(cached)
        warnings.extend(fw)
        return filtered, True, warnings
    hits, w = _compute_image_hits(image_path)
    warnings.extend(w)
    write_image_hits(image_path, hits)
    return hits, False, warnings


def _vision_tags_for_image(image_path: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    if not image_path.is_file() or image_path.stat().st_size == 0:
        return [], warnings
    cached = read_vision_tags(image_path)
    if cached is not None:
        return [t for t in cached if isinstance(t, str) and t], warnings
    tags: list[str] = []
    try:
        from pipeline.integrations.azure_photo_vlm import azure_vision_damage_tags

        tags, vw = azure_vision_damage_tags(image_path)
        warnings.extend(vw)
    except ImportError:
        return [], warnings
    write_vision_tags(image_path, tags)
    return tags, warnings


def _damage_vlm_hits(image_path: Path) -> tuple[list[dict], list[str]]:
    try:
        from pipeline.integrations.azure_damage_vlm import estimate_damage_hits

        return estimate_damage_hits(image_path)
    except ImportError:
        return [], []


def _dedupe_hits(hits: list[dict]) -> list[dict]:
    out: list[dict] = []
    for hit in hits:
        if not any(
            h.get("class") == hit.get("class")
            and abs(float(h.get("u_center_frac", 0)) - float(hit.get("u_center_frac", 0))) < 0.12
            for h in out
        ):
            out.append(hit)
        else:
            for h in out:
                if h.get("class") == hit.get("class") and abs(
                    float(h.get("u_center_frac", 0)) - float(hit.get("u_center_frac", 0))
                ) < 0.12:
                    h["score"] = min(0.95, float(h.get("score", 0.5)) + 0.1)
                    h["source"] = str(h.get("source", "")) + "+agree"
    return out


def _compute_image_hits(image_path: Path) -> tuple[list[dict], list[str]]:
    from pipeline.damage.heuristics import crack_hit, stain_hits

    warnings: list[str] = []
    hits: list[dict] = []
    try:
        import cv2
    except ImportError:
        warnings.append("damage: opencv unavailable — image heuristics skipped")
        return hits, warnings

    bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if bgr is None:
        warnings.append(f"damage: unreadable image {image_path.name}")
        return hits, warnings

    h, w_img = bgr.shape[:2]
    if h < 32 or w_img < 32:
        warnings.append(f"damage: image too small {image_path.name} ({w_img}x{h})")
        return hits, warnings

    for stain in stain_hits(bgr, h, w_img):
        hits.append(stain)
        warnings.append(f"damage: heuristic {stain.get('surface_type', 'wall')} stain on {image_path.name}")
    crack = crack_hit(bgr, h, w_img)
    if crack:
        hits.append(crack)
        warnings.append(f"damage: heuristic crack cue on {image_path.name}")
    vlm_hits, vlm_w = _damage_vlm_hits(image_path)
    warnings.extend(vlm_w)
    hits = _dedupe_hits(hits + vlm_hits)
    return hits, warnings


def _sample_images(capture_root: Path, rooms: list[dict]) -> list[Path]:
    paths: list[Path] = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        paths.extend(sorted(capture_root.glob(ext)))
    for room in rooms:
        photos = capture_root / "rooms" / room["room_id"] / "photos"
        if photos.is_dir():
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.heic", "*.heif"):
                paths.extend(sorted(photos.glob(ext)))
    video = find_video_file(capture_root)
    if video:
        paths.extend(_extract_video_frames(video, MAX_VIDEO_FRAMES))
    seen: set[str] = set()
    unique: list[Path] = []
    for p in paths:
        if not p.is_file() or p.stat().st_size == 0:
            continue
        if p.suffix.lower() not in _PHOTO_EXT:
            continue
        if p.suffix.lower() == ".png" and "depth" in p.name.lower():
            continue
        if "depth" in str(p).lower() and p.suffix.lower() == ".png":
            continue
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _extract_video_frames(video: Path, n: int) -> list[Path]:
    try:
        import cv2
    except ImportError:
        return []
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        cap.release()
        return []
    total = max(int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0), 1)
    indices = [int(total * (i + 1) / (n + 1)) for i in range(n)]
    out: list[Path] = []
    tmp_dir = Path(tempfile.gettempdir())
    for i, idx in enumerate(indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        tmp = tmp_dir / f"housefloor_damage_{video.stem}_{i}.jpg"
        cv2.imwrite(str(tmp), frame)
        if tmp.is_file():
            out.append(tmp)
    cap.release()
    return out
