"""Extract Stray Scanner / company zip into a capture folder."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


def extract_stray_zip(zip_path: Path, dest_dir: Path) -> Path:
    zip_path = zip_path.resolve()
    dest_dir = dest_dir.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)

    # If zip contains a single top-level folder, use it as capture root when it has odometry.csv
    if not (dest_dir / "odometry.csv").is_file():
        subs = [p for p in dest_dir.iterdir() if p.is_dir()]
        if len(subs) == 1 and (subs[0] / "odometry.csv").is_file():
            return subs[0]
        for sub in subs:
            for cand in sub.rglob("odometry.csv"):
                root = cand.parent
                return root
    return dest_dir


def ingest_zip_to_capture(zip_path: Path, capture_root: Path) -> Path:
    """Extract zip; copy into capture_root if needed."""
    capture_root.mkdir(parents=True, exist_ok=True)
    tmp = capture_root / "_extract_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    root = extract_stray_zip(zip_path, tmp)
    if root != capture_root:
        for item in root.iterdir():
            target = capture_root / item.name
            if item.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        shutil.rmtree(tmp)
    return capture_root
