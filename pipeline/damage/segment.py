"""Fast SAM-family segmentation: one MobileSAM load per image, else HSV crop refine."""

from __future__ import annotations

from pathlib import Path

SEGMENT_TAG_FAST = "sam_fast_hsv_v1"
SEGMENT_TAG_MOBILE = "mobile_sam_v1"
_MAX_SIDE = 512
_MAX_HITS_PER_IMAGE = 8
WEIGHTS_PATH = Path(__file__).resolve().parents[2] / ".cache" / "weights" / "mobile_sam.pt"

_predictor = None
_predictor_failed = False


def segment_hits_on_image(bgr, hits: list[dict]) -> list[dict]:
    """Refine bbox per hit; at most one MobileSAM set_image() per still."""
    if not hits:
        return hits
    out: list[dict] = []
    to_sam: list[tuple[int, dict, tuple[int, int, int, int]]] = []
    h, w = bgr.shape[:2]
    for i, hit in enumerate(hits[:_MAX_HITS_PER_IMAGE]):
        box = _hit_bbox_px(hit, w, h)
        if box is None:
            out.append(hit)
            continue
        refined = _fast_hsv_refine(bgr, hit, box)
        if refined is not None:
            out.append(refined)
        else:
            out.append(hit)
            to_sam.append((len(out) - 1, hit, box))

    predictor = _get_mobile_sam_predictor()
    if predictor is None or not to_sam:
        return out

    small, scale = _resize_for_segment(bgr)
    rgb = small[:, :, ::-1]
    try:
        predictor.set_image(rgb)
    except Exception:
        return out

    import numpy as np

    sh, sw = small.shape[:2]
    for out_idx, hit, box in to_sam:
        x0, y0, x1, y1 = (int(v * scale) for v in box)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(sw, x1), min(sh, y1)
        if x1 - x0 < 4 or y1 - y0 < 4:
            continue
        try:
            masks, _, _ = predictor.predict(
                box=np.array([x0, y0, x1, y1], dtype=float),
                multimask_output=False,
            )
        except Exception:
            continue
        if masks is None or len(masks) == 0:
            continue
        mask_full = _upscale_mask(masks[0], w, h, scale)
        updated = _hit_from_mask(out[out_idx], mask_full, w, h)
        updated["source"] = _append_source(updated.get("source", ""), SEGMENT_TAG_MOBILE)
        out[out_idx] = updated
    return out


def _append_source(src: str, tag: str) -> str:
    if tag in src:
        return src
    return f"{src}+{tag}" if src else tag


def _hit_bbox_px(hit: dict, w: int, h: int) -> tuple[int, int, int, int] | None:
    u0, u1 = hit.get("u0_frac"), hit.get("u1_frac")
    if u0 is not None and u1 is not None:
        x0 = int(max(0, min(w - 2, float(u0) * w)))
        x1 = int(max(x0 + 2, min(w, float(u1) * w)))
    else:
        cx = float(hit.get("u_center_frac", 0.4))
        half = 0.12
        x0 = int(max(0, (cx - half) * w))
        x1 = int(min(w, (cx + half) * w))
    if hit.get("surface_type") == "ceiling":
        y0, y1 = 0, max(8, int(h * 0.4))
    elif hit.get("class") == "crack":
        y0, y1 = int(h * 0.15), int(h * 0.95)
    else:
        y0, y1 = int(h * 0.2), h - 2
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    return x0, y0, x1, y1


def _fast_hsv_refine(bgr, hit: dict, box: tuple[int, int, int, int]) -> dict | None:
    """Tighten bbox from HSV in crop only (microseconds)."""
    import cv2
    import numpy as np

    x0, y0, x1, y1 = box
    crop = bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    cls = hit.get("class", "water_stain")
    if cls == "crack":
        band = _crack_band_mask(crop)
        if int(band.sum()) < 80:
            return None
        full = np.zeros(bgr.shape[:2], np.uint8)
        full[y0:y1, x0:x1] = band
        updated = _hit_from_mask(hit, full, bgr.shape[1], bgr.shape[0])
        updated["source"] = _append_source(updated.get("source", ""), SEGMENT_TAG_FAST)
        return updated

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    if hit.get("surface_type") == "ceiling":
        mask = cv2.inRange(hsv, (0, 0, 40), (180, 80, 220))
    else:
        mask = cv2.inRange(hsv, (5, 40, 40), (25, 255, 200))
    mask = cv2.medianBlur(mask, 5)
    if int(mask.sum()) < 800:
        return None
    full = np.zeros(bgr.shape[:2], np.uint8)
    full[y0:y1, x0:x1] = mask
    updated = _hit_from_mask(hit, full, bgr.shape[1], bgr.shape[0])
    updated["source"] = _append_source(updated.get("source", ""), SEGMENT_TAG_FAST)
    return updated


def _crack_band_mask(crop) -> object:
    import cv2
    import numpy as np

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 90, 200)
    return edges


def _hit_from_mask(
    hit: dict,
    mask,
    w: int,
    h: int,
    *,
    ox: int = 0,
    oy: int = 0,
    full_w: int | None = None,
    full_h: int | None = None,
) -> dict:
    import numpy as np

    full_w = full_w or w
    full_h = full_h or h
    if ox or oy:
        ys, xs = np.nonzero(mask > 30)
        if len(xs) == 0:
            return dict(hit)
        xs = xs + ox
        ys = ys + oy
    else:
        ys, xs = np.nonzero(mask > 30)
        if len(xs) < 4:
            return dict(hit)
    out = dict(hit)
    u0 = float(xs.min()) / max(full_w, 1)
    u1 = float(xs.max() + 1) / max(full_w, 1)
    v0 = float(ys.min()) / max(full_h, 1)
    v1 = float(ys.max() + 1) / max(full_h, 1)
    out["u0_frac"] = max(0.0, u0)
    out["u1_frac"] = min(1.0, u1)
    out["u_center_frac"] = (out["u0_frac"] + out["u1_frac"]) / 2.0
    out["v0_frac"] = v0
    out["v1_frac"] = v1
    frac_area = max((u1 - u0) * (v1 - v0), 0.003)
    out["area_m2"] = max(float(hit.get("area_m2", 0.08)), frac_area * 2.5)
    if hit.get("surface_type") != "ceiling":
        ceil_hint = 2.5
        out["bottom_above_floor_m"] = max(0.05, (1.0 - v1) * ceil_hint * 0.9)
    return out


def _resize_for_segment(bgr):
    import cv2

    h, w = bgr.shape[:2]
    scale = min(1.0, _MAX_SIDE / float(max(h, w)))
    if scale >= 1.0:
        return bgr, 1.0
    small = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return small, scale


def _upscale_mask(mask, w: int, h: int, scale: float):
    import cv2
    import numpy as np

    if scale >= 1.0:
        return (mask.astype(np.uint8) * 255)
    up = cv2.resize(mask.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
    return (up > 0).astype(np.uint8) * 255


def _get_mobile_sam_predictor():
    global _predictor, _predictor_failed
    if _predictor_failed:
        return None
    if _predictor is not None:
        return _predictor
    if not WEIGHTS_PATH.is_file():
        _predictor_failed = True
        return None
    try:
        import torch
        from mobile_sam import SamPredictor, sam_model_registry
    except ImportError:
        _predictor_failed = True
        return None
    try:
        sam = sam_model_registry["vit_t"](checkpoint=str(WEIGHTS_PATH))
        device = "cuda" if torch.cuda.is_available() else "cpu"
        sam.to(device=device)
        _predictor = SamPredictor(sam)
    except Exception:
        _predictor_failed = True
        return None
    return _predictor
