"""Read basic EXIF from photo stills (focal length / dimensions)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    TAGS = {}


def image_timestamp_s(path: Path) -> float | None:
    """Best-effort capture time (Unix s) from EXIF or file mtime."""
    path = Path(path)
    if Image is None or not path.is_file():
        try:
            return path.stat().st_mtime
        except OSError:
            return None
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            if exif:
                for tag_id, val in exif.items():
                    if TAGS.get(tag_id) not in ("DateTimeOriginal", "DateTime"):
                        continue
                    raw = str(val).strip()
                    try:
                        return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S").timestamp()
                    except ValueError:
                        continue
    except OSError:
        pass
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def exif_summary(photo_paths: list[Path]) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    meta: dict = {"count": len(photo_paths), "samples": []}
    if Image is None or not photo_paths:
        return meta, warnings

    for p in photo_paths[:4]:
        try:
            with Image.open(p) as im:
                w, h = im.size
                row = {"file": p.name, "width": w, "height": h}
                exif = im.getexif()
                if exif:
                    for tag_id, val in exif.items():
                        name = TAGS.get(tag_id, str(tag_id))
                        if name in ("FocalLength", "FocalLengthIn35mmFilm", "Make", "Model"):
                            row[name] = val
                meta["samples"].append(row)
        except OSError:
            warnings.append(f"photo_exif: unreadable {p.name}")
    if not meta["samples"]:
        warnings.append("photo_exif: no readable images for intrinsics hint")
    warnings.extend(focal_sanity_warnings(meta))
    return meta, warnings


def focal_sanity_warnings(meta: dict) -> list[str]:
    warnings: list[str] = []
    saw_focal = False
    for row in meta.get("samples") or []:
        if row.get("FocalLengthIn35mmFilm") or row.get("FocalLength"):
            saw_focal = True
            break
    if meta.get("samples") and not saw_focal:
        warnings.append("photo_exif: no focal length in EXIF — default intrinsics; scale σ widened")
    return warnings


def intrinsics_matrix(meta: dict, *, default_focal_px: float = 900.0) -> "np.ndarray":
    """Approximate K from EXIF 35 mm equivalent or image size."""
    import numpy as np

    focal = default_focal_px
    width = 1920.0
    for row in meta.get("samples") or []:
        width = float(row.get("width") or width)
        fl35 = row.get("FocalLengthIn35mmFilm")
        if fl35:
            focal = width * float(fl35) / 36.0
            break
        fl = row.get("FocalLength")
        if fl:
            try:
                focal = float(fl) * 50.0
            except (TypeError, ValueError):
                pass
            break
    cx, cy = width / 2.0, width * 0.5625 / 2.0
    return np.array([[focal, 0.0, cx], [0.0, focal, cy], [0.0, 0.0, 1.0]], dtype=float)
