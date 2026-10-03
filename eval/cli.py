"""CLI: python -m eval.cli score --capture <dir> [--plan path] [--tier lidar|video|photos]"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.calibrate import fit_and_write
from eval.report import write_report


def main() -> None:
    p = argparse.ArgumentParser(description="Eval: score vs GT, calibrate from fixture")
    sub = p.add_subparsers(dest="cmd", required=True)
    cal = sub.add_parser("calibrate", help="Fit configs/calibration.json from lidar_two_room fixture")
    cal.set_defaults(cmd="calibrate")
    tpl = sub.add_parser("gt-template", help="Create data/ground_truth/<capture_id>.json skeleton")
    tpl.add_argument("--capture", type=Path, required=True)
    tpl.add_argument("--overwrite", action="store_true")
    tpl.set_defaults(cmd="gt-template")
    sc = sub.add_parser("score", help="Gate report for one capture")
    sc.add_argument("--capture", type=Path, required=True)
    sc.add_argument("--plan", type=Path, default=None)
    sc.add_argument("--tier", default="lidar")
    sc.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    if args.cmd == "calibrate":
        path = fit_and_write()
        print(path.read_text(encoding="utf-8"))
        return

    if args.cmd == "gt-template":
        from eval.gt_template import write_gt_template

        out = write_gt_template(args.capture.resolve(), overwrite=args.overwrite)
        print(out)
        return

    path = write_report(args.capture.resolve(), args.out, plan_path=args.plan, tier=args.tier)
    data = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
