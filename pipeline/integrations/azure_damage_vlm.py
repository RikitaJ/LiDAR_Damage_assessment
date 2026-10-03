"""Optional Azure OpenAI vision for structured damage cues (Phase 5)."""

from __future__ import annotations

import base64
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

from pipeline.integrations.azure_optional import _env, _load_dotenv_once
from pipeline.integrations.azure_photo_vlm import _image_mime

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "damage_vlm"
PROMPT_VERSION = "damage_vlm_v1"


def estimate_damage_hits(image_path: Path) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    if not image_path.is_file():
        return [], warnings
    _load_dotenv_once()
    key = _env("AZURE_OPENAI_API_KEY")
    endpoint = _env("AZURE_OPENAI_ENDPOINT")
    if not key or not endpoint:
        return [], warnings

    deployment = _env("AZURE_OPENAI_DEPLOYMENT") or "gpt-4o"
    api_version = _env("AZURE_OPENAI_API_VERSION") or "2024-10-21"
    cache_key = _cache_key(image_path, deployment)
    cached = _read_cache(cache_key)
    if cached is not None:
        warnings.append("damage_vlm: using cached Azure damage response")
        return cached, warnings

    try:
        hits = _call(key, endpoint, deployment, api_version, image_path)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as e:
        warnings.append(f"damage_vlm: Azure call failed ({type(e).__name__})")
        return [], warnings

    _write_cache(cache_key, hits)
    if hits:
        warnings.append("damage_vlm: Azure OpenAI damage cues applied")
    return hits, warnings


def _call(
    key: str,
    endpoint: str,
    deployment: str,
    api_version: str,
    path: Path,
) -> list[dict]:
    url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    raw = path.read_bytes()
    if len(raw) > 4_000_000:
        raw = raw[:4_000_000]
    b64 = base64.b64encode(raw).decode("ascii")
    mime = _image_mime(path.suffix.lower())
    body = json.dumps(
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "List visible property damage in this image. JSON only: "
                                '{"items":[{"class":"water_stain|crack|mold",'
                                '"surface":"wall|ceiling",'
                                '"image_x_center":0-1,"image_y_center":0-1,'
                                '"width_fraction":0-1,"height_fraction":0-1,'
                                '"confidence":0-1}]}. '
                                "Use empty items if none. Do not invent damage."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }
            ],
            "max_tokens": 350,
            "temperature": 0.1,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=75) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    text = payload["choices"][0]["message"]["content"]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return []
    data = json.loads(text[start : end + 1])
    return _normalize_items(data.get("items") or [])


def _normalize_items(items: list) -> list[dict]:
    out: list[dict] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        cls = str(raw.get("class") or "").lower().replace(" ", "_")
        if cls in ("stain", "water_damage"):
            cls = "water_stain"
        if cls not in ("water_stain", "crack", "mold"):
            continue
        try:
            cx = float(raw.get("image_x_center", 0.5))
            cy = float(raw.get("image_y_center", 0.5))
            wf = max(0.03, min(0.6, float(raw.get("width_fraction", 0.12))))
            hf = max(0.03, min(0.5, float(raw.get("height_fraction", 0.1))))
            conf = max(0.0, min(1.0, float(raw.get("confidence", 0.65))))
        except (TypeError, ValueError):
            continue
        surface = str(raw.get("surface") or "wall").lower()
        u0 = max(0.0, cx - wf / 2)
        u1 = min(1.0, cx + wf / 2)
        out.append(
            {
                "class": cls,
                "surface_type": "ceiling" if surface == "ceiling" else "wall",
                "u_center_frac": cx,
                "u0_frac": u0,
                "u1_frac": u1,
                "bottom_above_floor_m": max(0.05, (1.0 - cy) * 0.45) if surface != "ceiling" else 2.0,
                "area_m2": 0.05 + wf * hf * 2.5,
                "score": 0.55 + conf * 0.35,
                "source": "azure_damage_vlm_v1",
            }
        )
    return out


def _cache_key(path: Path, deployment: str) -> str:
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())
    h.update(deployment.encode())
    h.update(path.read_bytes()[:8192])
    return h.hexdigest()


def _read_cache(key: str) -> list[dict] | None:
    p = CACHE_DIR / f"{key}.json"
    if not p.is_file():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return list(data.get("hits") or [])


def _write_cache(key: str, hits: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps({"hits": hits}), encoding="utf-8")
