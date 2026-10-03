#!/usr/bin/env python3
"""Download captures listed in data/manifest.csv, check their sha256 and unpack them."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.io.stray_zip import ingest_zip_to_capture  # noqa: E402
MANIFEST = ROOT / "data" / "manifest.csv"
DEFAULT_CAPTURE_ROOT = ROOT / "data" / "captures"
DRIVE_FILE_ID = re.compile(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:[^#]*&)?id=)([\w-]+)")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def direct_url(url: str) -> str:
    """Turn a Google Drive share link into a direct download link; other URLs are returned unchanged."""
    match = DRIVE_FILE_ID.search(url)
    if match is None:
        return url
    return f"https://drive.usercontent.google.com/download?id={match.group(1)}&export=download&confirm=t"


def confirm_url(page: str) -> str | None:
    """Drive can answer with a "can't scan for viruses" page; its form holds the link to the file."""
    form = re.search(r'<form[^>]*action="([^"]+)"[^>]*>(.*?)</form>', page, re.S)
    if form is None:
        return None
    fields = {}
    for tag in re.findall(r"<input[^>]*>", form.group(2)):
        name, value = re.search(r'name="([^"]+)"', tag), re.search(r'value="([^"]*)"', tag)
        if 'type="hidden"' in tag and name and value:
            fields[name.group(1)] = html.unescape(value.group(1))
    if "id" not in fields:
        return None
    return f"{html.unescape(form.group(1))}?{urllib.parse.urlencode(fields)}"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    link = direct_url(url)
    for _ in range(2):
        print(f"Downloading {link} -> {dest}")
        with urllib.request.urlopen(link) as resp:
            if "text/html" not in resp.headers.get("Content-Type", ""):
                with dest.open("wb") as f:
                    shutil.copyfileobj(resp, f, 1024 * 1024)
                return
            page = resp.read().decode("utf-8", "replace")
        link = confirm_url(page)
        if link is None:
            break
    raise RuntimeError(f"{url} returned a web page, not the file; is it shared with 'Anyone with the link'?")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_ids", nargs="*", help="only these captures (default: every row with a url)")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--dest", type=Path, default=DEFAULT_CAPTURE_ROOT, help="captures go to <dest>/<capture_id>/")
    args = parser.parse_args(argv)
    if not args.manifest.is_file():
        print(f"Missing {args.manifest}", file=sys.stderr)
        return 1

    with args.manifest.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("manifest empty", file=sys.stderr)
        return 1

    for row in rows:
        cid = (row.get("capture_id") or "").strip()
        if not cid or (args.capture_ids and cid not in args.capture_ids):
            continue
        url = (row.get("url") or "").strip()
        if not url or url.upper() == "TODO":
            print(f"[skip] {cid}: no url in the manifest")
            continue

        dest_dir = args.dest / cid
        archive = dest_dir / f"{cid}.zip"
        expected = (row.get("sha256") or "").strip().lower()
        check = bool(expected) and expected != "todo"
        if check and archive.is_file() and sha256_file(archive) == expected:
            print(f"[ok] {cid}: already downloaded")
        else:
            try:
                download(url, archive)
            except (OSError, RuntimeError) as err:
                print(f"[fail] {cid}: {err}", file=sys.stderr)
                return 1
            if check:
                if sha256_file(archive) != expected:
                    print(f"[fail] {cid}: sha256 mismatch", file=sys.stderr)
                    return 1
                print(f"[ok] {cid}: sha256 verified")

        ingest_zip_to_capture(archive, dest_dir)
        print(f"[ok] {cid}: extracted to {dest_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
