"""Benchmark report: python -m eval.run [--rerun] --captures data/captures --runs out --report docs/BENCHMARK_REPORT.md"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from eval.accuracy import repeatability, score_room

ROOT = Path(__file__).resolve().parents[1]


def run_pipeline(capture: Path, out: Path) -> tuple[int, float]:
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "pipeline.cli", "run", "--capture", str(capture), "--out", str(out), "--tier", "auto"],
        cwd=ROOT, env={**os.environ, "MPLBACKEND": "Agg"}, capture_output=True, text=True,
    )
    return proc.returncode, time.perf_counter() - t0


def git_head() -> str:
    proc = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return proc.stdout.strip() or "unknown"


def _fmt_error(row) -> str:
    rel = 100 * row.error / row.truth
    if row.name.startswith("Floor area"):
        return f"{row.error:+.2f} m² ({rel:+.1f} %)"
    return f"{100 * row.error:+.1f} cm ({rel:+.1f} %)"


def _fmt_gate(tol) -> str:
    if tol is None:
        return "—"
    mode, value = tol
    return f"±{100 * value:g} cm" if mode == "abs" else f"±{100 * value:g} %"


def _fmt_interval(row) -> str:
    if row.lo is None or row.hi is None:
        return f"{row.value:.3f} (no interval)"
    return f"{row.value:.3f} [{row.lo:.3f}, {row.hi:.3f}]"


def capture_section(cid: str, plan: dict, gt: dict, seconds: float | None) -> list[str]:
    tier = plan.get("input_tier", "lidar")
    lines = [f"## {cid} ({tier})", ""]
    if seconds is not None:
        lines += [f"Pipeline run: {seconds:.0f} s.", ""]
    rooms = {r["room_id"]: r for r in plan.get("rooms", [])}
    covered = total = 0
    for room_id in sorted(gt.get("ceiling_height_cm", {}) | gt.get("wall_lengths_cm", {})):
        if room_id not in rooms:
            lines += [f"Room `{room_id}` from ground truth is missing from the plan.", ""]
            continue
        rows, detection = score_room(rooms[room_id], gt, room_id, tier)
        lines += [
            "| Measurement | Tape | Ours [90 % interval] | Error | Gate | Result | Tape inside interval |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in rows:
            result = {True: "pass", False: "**FAIL**", None: "—"}[row.passed]
            inside = "yes" if row.covered else "no"
            lines.append(
                f"| {row.name} | {row.truth:.3f} | {_fmt_interval(row)} | {_fmt_error(row)} "
                f"| {_fmt_gate(row.tolerance)} | {result} | {inside} |"
            )
            covered += row.covered
            total += 1
        lines.append("")
        if detection:
            truth = ", ".join(f"{n} {k}" for k, n in sorted(detection["truth"].items()))
            found = ", ".join(f"{n} {k}" for k, n in sorted(detection["found"].items())) or "none"
            lines += [
                f"Openings (count only; widths not taped, so the width gate is not scored): "
                f"tape {truth}; found {found}; {detection['missed']} missed, {detection['phantom']} phantom.",
                "",
            ]
    lines += [f"Tape value inside the 90 % interval: {covered} of {total} measurements.", ""]
    return lines


def repeat_section(groups: dict[tuple[str, str], list[tuple[str, dict]]]) -> list[str]:
    lines = ["## Repeatability", ""]
    found = False
    for (room, tier), items in sorted(groups.items()):
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                (id_a, plan_a), (id_b, plan_b) = items[i], items[j]
                rep = repeatability(plan_a["rooms"][0], plan_b["rooms"][0])
                deltas = ", ".join(f"{100 * w['delta']:.1f}" for w in rep["walls"])
                lines.append(
                    f"- {room} ({tier}), `{id_a}` vs `{id_b}`: wall deltas {deltas} cm "
                    f"(gate 1 cm or 0.5 % each: {'pass' if rep['walls_passed'] else '**FAIL**'}); "
                    f"ceiling spread {100 * rep['ceiling_spread']:.1f} cm "
                    f"(gate 1 cm: {'pass' if rep['ceiling_passed'] else '**FAIL**'})."
                )
                found = True
    if not found:
        lines.append("No room has two captures at the same tier yet.")
    return lines + [""]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score pipeline runs against tape ground truth")
    p.add_argument("--captures", type=Path, default=ROOT / "data" / "captures")
    p.add_argument("--runs", type=Path, default=ROOT / "out")
    p.add_argument("--gt", type=Path, default=ROOT / "data" / "ground_truth")
    p.add_argument("--report", type=Path, default=ROOT / "docs" / "BENCHMARK_REPORT.md")
    p.add_argument("--manifest", type=Path, default=ROOT / "data" / "manifest.csv")
    p.add_argument("--rerun", action="store_true", help="run the pipeline on each capture with ground truth first")
    args = p.parse_args(argv)

    with args.manifest.open(encoding="utf-8", newline="") as f:
        listed = {row["capture_id"] for row in csv.DictReader(f)}
    gts = {}
    for path in sorted(args.gt.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if path.stem in listed and data.get("_meta", {}).get("status") == "complete":
            gts[path.stem] = data

    lines = [
        "# Benchmark report",
        "",
        f"Generated by `python -m eval.run{' --rerun' if args.rerun else ''}` at commit `{git_head()}`. "
        "Ground truth is tape-measured (`data/ground_truth/`, assumptions listed in each file). "
        "Every number below comes from this script; do not edit by hand.",
        "",
    ]
    groups: dict[tuple[str, str], list[tuple[str, dict]]] = {}
    missing: list[str] = []
    for cid, gt in gts.items():
        seconds = None
        if args.rerun:
            capture = args.captures / cid
            if not capture.is_dir():
                missing.append(f"`{cid}`: capture not found under `{args.captures.name}/` (fetch it first)")
                continue
            code, seconds = run_pipeline(capture, args.runs / cid)
            if code != 0:
                missing.append(f"`{cid}`: pipeline exited with code {code}")
                continue
        plan_path = args.runs / cid / "plan.json"
        if not plan_path.is_file():
            missing.append(f"`{cid}`: no `{plan_path.name}` under `{args.runs.name}/{cid}/`")
            continue
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        lines += capture_section(cid, plan, gt, seconds)
        room = gt.get("_meta", {}).get("room")
        if room and len(plan.get("rooms", [])) == 1:
            groups.setdefault((room, plan.get("input_tier", "lidar")), []).append((cid, plan))

    lines += repeat_section(groups)
    if args.captures.is_dir():
        missing += [
            f"`{d.name}`: no tape ground truth (internal consistency only)"
            for d in sorted(args.captures.iterdir())
            if d.is_dir() and d.name not in gts
        ]
    if missing:
        lines += ["## Not scored", ""] + [f"- {m}" for m in missing] + [""]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines), encoding="utf-8")
    print(args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
