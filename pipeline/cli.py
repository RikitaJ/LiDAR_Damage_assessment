from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.benchmark.ablation import drift_ablation
from pipeline.benchmark.gates import score, score_repeatability
from pipeline.benchmark.report import write_benchmark_report
from pipeline.config import InputTier, RunConfig
from pipeline.io.tier_detect import detect_tier
from pipeline.io.apple_import import import_apple
from pipeline.io.session import load_session
from pipeline.run import run_capture


def main() -> None:
    p = argparse.ArgumentParser(description="House floor plan pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Capture folder → plan.json + PNG")
    run.add_argument("--capture", type=Path, required=True)
    run.add_argument("--out", type=Path, default=None)
    run.add_argument(
        "--tier",
        default="auto",
        choices=["auto", "lidar", "video", "photos"],
        help="Input tier (auto detects Stray Scanner or manifest)",
    )
    run.add_argument("--no-loop-closure", action="store_true", help="Deprecated: use --drift off")
    run.add_argument("--drift", choices=["on", "off"], default="on", help="Drift / loop correction")

    imp = sub.add_parser("import-apple", help="Apple JSON folder → capture layout")
    imp.add_argument("--input", type=Path, required=True)
    imp.add_argument("--out", type=Path, required=True)
    imp.add_argument("--capture-id", default=None)
    imp.add_argument("--overwrite", action="store_true", help="Replace existing --out directory")

    sc = sub.add_parser("score", help="Gate report vs ground_truth.json")
    sc.add_argument("--capture", type=Path, required=True)
    sc.add_argument("--plan", type=Path, default=None)
    sc.add_argument("--tier", default="lidar")
    sc.add_argument("--repeat-plan", type=Path, default=None, help="Second plan.json for ceiling spread gate")

    br = sub.add_parser("benchmark-report", help="Run + score + ablation → REPORT.md")
    br.add_argument("--capture", type=Path, required=True)
    br.add_argument("--out", type=Path, default=None)

    rep = sub.add_parser("score-repeat", help="Repeatability between two plan.json runs")
    rep.add_argument("--plan-a", type=Path, required=True)
    rep.add_argument("--plan-b", type=Path, required=True)

    ab = sub.add_parser("ablate-drift", help="Footprint loop closure on vs off")
    ab.add_argument("--capture", type=Path, required=True)
    ab.add_argument("--out", type=Path, default=None)

    args = p.parse_args()

    if args.cmd == "import-apple":
        print(import_apple(args.input, args.out, args.capture_id, overwrite=args.overwrite))
        return

    if args.cmd == "score":
        capture = args.capture.resolve()
        session = load_session(capture)
        gt = capture / "ground_truth.json"
        if not gt.is_file():
            raise SystemExit(f"Missing {gt}")
        plan = args.plan or (capture / "out" / "plan.json")
        report = score(plan, gt, args.tier, args.repeat_plan)
        out = capture / "out" / "gate_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(json.dumps(report.to_dict(), indent=2))
        return

    if args.cmd == "score-repeat":
        report = score_repeatability(args.plan_a, args.plan_b)
        print(json.dumps(report.to_dict(), indent=2))
        return

    if args.cmd == "benchmark-report":
        path = write_benchmark_report(args.capture.resolve(), args.out)
        print(path)
        return

    if args.cmd == "ablate-drift":
        capture = args.capture.resolve()
        out = args.out or (capture / "out" / "ablation")
        result = drift_ablation(capture, out)
        path = out / "drift_ablation.json"
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return

    capture = args.capture.resolve()
    out_dir = args.out or (capture / "out")
    tier_override = None if args.tier == "auto" else InputTier(args.tier)
    tier = detect_tier(capture, tier_override)
    if tier == InputTier.PHOTOS:
        raise SystemExit("Photo tier not implemented yet. Use lidar, video, or auto.")
    drift_on = args.drift == "on" and not args.no_loop_closure
    cfg = RunConfig(tier=tier, loop_closure=drift_on, drift_correction=drift_on)
    print(run_capture(capture, out_dir, cfg))


if __name__ == "__main__":
    main()
