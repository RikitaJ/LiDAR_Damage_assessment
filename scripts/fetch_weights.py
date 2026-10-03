#!/usr/bin/env python3
"""Optional MobileSAM weights (GrabCut-free fast segment fallback works without this)."""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".cache" / "weights" / "mobile_sam.pt"
URL = "https://github.com/ChaoningZhang/MobileSAM/raw/master/weights/mobile_sam.pt"


def main() -> int:
    if DEST.is_file() and DEST.stat().st_size > 1_000_000:
        print(f"OK: {DEST}")
        return 0
    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {URL}")
    try:
        urllib.request.urlretrieve(URL, DEST)
    except OSError as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    print(f"Saved {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
