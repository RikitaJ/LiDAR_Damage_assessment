#!/usr/bin/env python3
"""Download captures listed in data/manifest.csv (sha256 when provided)."""

from __future__ import annotations

import csv
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.io.stray_zip import ingest_zip_to_capture  # noqa: E402
MANIFEST = ROOT / "data" / "manifest.csv"
DEFAULT_CAPTURE_ROOT = ROOT / "single_room sample data_given"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {dest}")
    urllib.request.urlretrieve(url, dest)


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not MANIFEST.is_file():
        print(f"Missing {MANIFEST}", file=sys.stderr)
        return 1

    only_id = argv[0] if argv else None
    rows = list(csv.DictReader(MANIFEST.open(encoding="utf-8")))
    if not rows:
        print("manifest empty", file=sys.stderr)
        return 1

    for row in rows:
        cid = row.get("capture_id", "").strip()
        if not cid:
            continue
        if only_id and cid != only_id:
            continue
        url = (row.get("url") or "").strip()
        if not url or url.upper() == "TODO":
            print(f"[skip] {cid}: set url (+ sha256) in data/manifest.csv")
            continue

        dest_dir = DEFAULT_CAPTURE_ROOT / cid
        archive = dest_dir / f"{cid}.zip"
        download(url, archive)

        expected = (row.get("sha256") or "").strip()
        if expected and expected.upper() != "TODO":
            got = sha256_file(archive)
            if got.lower() != expected.lower():
                print(f"[fail] {cid}: sha256 mismatch", file=sys.stderr)
                return 1
            print(f"[ok] {cid}: sha256 verified")

        ingest_zip_to_capture(archive, dest_dir)
        print(f"[ok] {cid}: extracted to {dest_dir} (expect odometry.csv, depth/, confidence/)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
