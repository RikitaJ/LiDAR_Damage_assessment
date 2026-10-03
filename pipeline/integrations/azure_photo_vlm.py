"""Optional Azure OpenAI vision for photo tier (Phase 4) — offline when no keys."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from pipeline.integrations.azure_optional import _env, _load_dotenv_once

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "photo_vlm"
MAX_IMAGES = 8


def estimate_room_from_photos_merged(photo_paths: list[Path]) -> tuple[dict | None, list[str]]:
    """Two spaced VLM batches merged by median when ≥6 stills (accuracy)."""
    from pipeline.geometry.photo_metric import merge_vlm_estimates
    from pipeline.frontends.photo_pick import pick_spaced_photos

    warnings: list[str] = []
    if len(photo_paths) < 6:
        return estimate_room_from_photos(photo_paths)

    half = max(3, len(photo_paths) // 2)
    batch_a = pick_spaced_photos(photo_paths, half)
    batch_b = pick_spaced_photos(list(reversed(photo_paths)), half)
    e1, w1 = estimate_room_from_photos(batch_a)
    e2, w2 = estimate_room_from_photos(batch_b)
    warnings.extend(w1)
    warnings.extend(w2)
    merged = merge_vlm_estimates([e for e in (e1, e2) if e])
    if merged:
        warnings.append("photo_vlm: merged two VLM batches (median)")
        return merged, warnings
    return e1 or e2, warnings


def estimate_room_from_photos(photo_paths: list[Path]) -> tuple[dict | None, list[str]]:
    warnings: list[str] = []
    if not photo_paths:
        return None, warnings

    _load_dotenv_once()
    key = _env("AZURE_OPENAI_API_KEY")
    endpoint = _env("AZURE_OPENAI_ENDPOINT")
    deployment = _env("AZURE_OPENAI_DEPLOYMENT") or "gpt-4o"
    api_version = _env("AZURE_OPENAI_API_VERSION") or "2024-10-21"

    if not key or not endpoint:
        return None, warnings

    picked = photo_paths[:MAX_IMAGES]
    cache_key = _cache_key(picked)
    cached = _read_cache(cache_key)
    if cached is not None:
        warnings.append("photo_vlm: using cached Azure response")
        return cached, warnings

    try:
        est = _call_azure(key, endpoint, deployment, api_version, picked)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as e:
        warnings.append(f"photo_vlm: Azure call failed ({type(e).__name__}); offline prior kept")
        return None, warnings

    if est:
        _write_cache(cache_key, est)
        warnings.append("photo_vlm: Azure OpenAI layout estimate applied")
    return est, warnings


def _image_mime(suffix: str) -> str:
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix in (".png",):
        return "image/png"
    if suffix in (".webp",):
        return "image/webp"
    if suffix in (".heic", ".heif"):
        return "image/heic"
    return "image/jpeg"


def _cache_key(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.name.encode())
        h.update(p.read_bytes()[:8192])
    dep = _env("AZURE_OPENAI_DEPLOYMENT") or "gpt-4o"
    h.update(dep.encode())
    return h.hexdigest()


def _read_cache(key: str) -> dict | None:
    p = CACHE_DIR / f"{key}.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _write_cache(key: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(data), encoding="utf-8")


def _call_azure(
    key: str,
    endpoint: str,
    deployment: str,
    api_version: str,
    paths: list[Path],
) -> dict | None:
    url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "Estimate one room from these photos (Manhattan walls). "
                "Reply with JSON only: "
                '{"floor_area_m2": number, "ceiling_height_m": number, '
                '"wall_lengths_m": [4+ numbers metres clockwise], '
                '"openings": [{"kind":"door|window", "wall_index": int, '
                '"width_m": number, "height_m": number, "sill_m": number|null}], '
                '"door_height_m": number|null, '
                '"main_door_image_height_fraction": number|null, '
                '"door_on_wall": int|null, "door_width_m": number|null}. '
                "Prefer openings[] for doors and windows. "
                "door_height_m = visible door height in metres; "
                "main_door_image_height_fraction = door height / full image height (0-1). "
                "If unsure, use null fields."
            ),
        }
    ]
    for p in paths:
        raw = p.read_bytes()
        if len(raw) > 4_000_000:
            raw = raw[:4_000_000]
        b64 = base64.b64encode(raw).decode("ascii")
        mime = _image_mime(p.suffix.lower())
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

    body = json.dumps(
        {
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 400,
            "temperature": 0.2,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    text = payload["choices"][0]["message"]["content"]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        return None
    return data


def azure_vision_damage_tags(image_path: Path) -> tuple[list[str], list[str]]:
    """Optional Azure AI Vision tags for Phase 5 cues (offline if no vision key)."""
    warnings: list[str] = []
    _load_dotenv_once()
    key = _env("AZURE_VISION_KEY")
    endpoint = _env("AZURE_VISION_ENDPOINT")
    if not key or not endpoint or not image_path.is_file():
        return [], warnings

    url = f"{endpoint.rstrip('/')}/vision/v3.2/analyze?visualFeatures=Tags"
    raw = image_path.read_bytes()
    if len(raw) > 3_500_000:
        raw = raw[:3_500_000]
    req = urllib.request.Request(
        url,
        data=raw,
        headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/octet-stream"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        warnings.append("azure_vision: tag request failed")
        return [], warnings

    tags = [t.get("name", "") for t in data.get("tags", []) if t.get("name")]
    damage_like = [t for t in tags if t in ("crack", "stain", "mold", "damage", "rust", "peeling")]
    if tags:
        warnings.append(f"azure_vision: {len(tags)} tags")
    return damage_like, warnings
