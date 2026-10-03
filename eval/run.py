"""Benchmark report: python -m eval.run [--rerun] [--ref COMMIT ...] --report docs/BENCHMARK_REPORT.md"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

from eval.accuracy import head_to_head, repeatability, score_room

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def pipeline_tree(ref: str | None, tmp: Path) -> Path:
    """The working tree, or a clean export of `ref` so older pipeline versions can be re-run exactly."""
    if ref is None:
        return ROOT
    tree = tmp / ref
    if not tree.is_dir():
        archive = subprocess.run(["git", "archive", "--format=tar", ref], cwd=ROOT, capture_output=True, check=True)
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(tree, filter="data")
    return tree


def run_pipeline(tree: Path, capture: Path, out: Path) -> tuple[int, float]:
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "pipeline.cli", "run", "--capture", str(capture), "--out", str(out), "--tier", "auto"],
        cwd=tree, env={**os.environ, "MPLBACKEND": "Agg", "PYTHONPATH": str(tree)}, capture_output=True, text=True,
    )
    return proc.returncode, time.perf_counter() - t0


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


def score_plan(plan: dict, gt: dict) -> list[tuple[str, list, dict]]:
    tier = plan.get("input_tier", "lidar")
    rooms = {r["room_id"]: r for r in plan.get("rooms", [])}
    scored = []
    for room_id in sorted(gt.get("ceiling_height_cm", {}) | gt.get("wall_lengths_cm", {})):
        if room_id in rooms:
            rows, openings = score_room(rooms[room_id], gt, room_id, tier)
            scored.append((room_id, rows, openings))
    return scored


def summary_row(label: str, scored: list[tuple[str, list, dict]]) -> str:
    rows = [r for _, rs, ops in scored for r in rs + ops.get("rows", [])]
    walls = [r for r in rows if r.name.startswith("Wall")]
    find = {r.name: r for r in rows}
    worst = max(walls, key=lambda r: abs(r.error / r.truth), default=None)
    cells = [
        f"{100 * worst.error / worst.truth:+.1f} %" if worst else "—",
        _fmt_error(find["Ceiling height"]) if "Ceiling height" in find else "—",
        f"{100 * find['Floor area (m²)'].error / find['Floor area (m²)'].truth:+.1f} %" if "Floor area (m²)" in find else "—",
        "; ".join(f"{ops['hits']} of {ops['taped']} within 2 cm, {ops['phantom']} phantom" for _, _, ops in scored if ops) or "—",
        f"{sum(r.covered for r in rows)} of {len(rows)}",
    ]
    return f"| {label} | " + " | ".join(cells) + " |"


def headline(label: str, scored: list[tuple[str, list, dict]]) -> str:
    geometry = [r for _, rs, _ in scored for r in rs]
    if not geometry:
        return f"- {label}: nothing to score."
    worst = 100 * max(abs(r.error / r.truth) for r in geometry)
    text = (f"- {label}: largest error on walls, ceiling and floor area is {worst:.1f} % of the tape value; "
            f"{sum(bool(r.passed) for r in geometry)} of {len(geometry)} strict gates pass")
    for _, _, ops in scored:
        if ops:
            text += f"; openings {ops['hits']} of {ops['taped']} within 2 cm ({ops['phantom']} phantom)"
    return text + "."


def head_to_head_section(app: dict, scored: list[tuple[str, list, dict]]) -> list[str]:
    rows = next((rs for room_id, rs, _ in scored if room_id == app.get("room_id", room_id)), [])
    h2h = head_to_head(rows, app)
    name = f"{app['app']} {app['version']}"
    lines = [
        f"### Head-to-head: {name}",
        "",
        f"| Dimension | Tape | Ours | {name} | Our error | Their error | Result |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in h2h["rows"]:
        lines.append(
            f"| {r['name']} | {r['truth']:.3f} | {r['ours']:.3f} | {r['theirs']:.3f} "
            f"| {100 * (r['ours'] - r['truth']):+.1f} cm | {100 * (r['theirs'] - r['truth']):+.1f} cm | {r['result']} |"
        )
    verdict = "pass" if h2h["passed"] else "**FAIL**"
    return lines + [
        "",
        f"Beat or tie on {h2h['beat_or_tie']} of {len(h2h['rows'])} shared dimensions "
        f"(gate ≥ 70 %; tie = errors within 3 mm): {verdict}. Their values: {app['source']}.",
        "",
    ]


def capture_section(title: str, scored: list[tuple[str, list, dict]], seconds: float | None) -> list[str]:
    lines = [f"## {title}", ""]
    if seconds is not None:
        lines += [f"Pipeline run: {seconds:.0f} s.", ""]
    covered = total = 0
    for room_id, rows, openings in scored:
        lines += [
            "| Measurement | Tape | Ours [90 % interval] | Error | Gate | Result | Tape inside interval |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in rows + openings.get("rows", []):
            result = {True: "pass", False: "**FAIL**", None: "—"}[row.passed]
            lines.append(
                f"| {row.name} | {row.truth:.3f} | {_fmt_interval(row)} | {_fmt_error(row)} "
                f"| {_fmt_gate(row.tolerance)} | {result} | {'yes' if row.covered else 'no'} |"
            )
            covered += row.covered
            total += 1
        lines.append("")
        if openings:
            verdict = "pass" if openings["passed"] else "**FAIL**"
            lines += [
                f"Openings: {openings['found']} found, {openings['taped']} taped; {openings['hits']} within 2 cm, "
                f"{openings['missed']} missed, {openings['phantom']} phantom. "
                f"Score {openings['hits']} / ({openings['taped']} + {openings['phantom']}) = {100 * openings['rate']:.0f} % "
                f"(gate ≥ 85 %): {verdict}.",
                "",
            ]
    lines += [f"Tape value inside the 90 % interval: {covered} of {total} measurements.", ""]
    return lines


def repeat_section(groups: dict[tuple[str, str, str], list[tuple[str, dict]]]) -> list[str]:
    lines = ["## Repeatability", ""]
    for (room, tier, label), items in sorted(groups.items()):
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                (id_a, plan_a), (id_b, plan_b) = items[i], items[j]
                rep = repeatability(plan_a["rooms"][0], plan_b["rooms"][0])
                deltas = ", ".join(f"{100 * w['delta']:.1f}" for w in rep["walls"])
                lines.append(
                    f"- {room} ({tier}, {label}), `{id_a}` vs `{id_b}`: wall deltas {deltas} cm "
                    f"(gate 1 cm or 0.5 % each: {'pass' if rep['walls_passed'] else '**FAIL**'}); "
                    f"ceiling spread {100 * rep['ceiling_spread']:.1f} cm "
                    f"(gate 1 cm: {'pass' if rep['ceiling_passed'] else '**FAIL**'})."
                )
    if len(lines) == 2:
        lines.append("No room has two captures at the same tier yet.")
    return lines + [""]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score pipeline runs against tape ground truth")
    p.add_argument("--captures", type=Path, default=ROOT / "data" / "captures")
    p.add_argument("--runs", type=Path, default=ROOT / "out")
    p.add_argument("--gt", type=Path, default=ROOT / "data" / "ground_truth")
    p.add_argument("--report", type=Path, default=ROOT / "docs" / "BENCHMARK_REPORT.md")
    p.add_argument("--manifest", type=Path, default=ROOT / "data" / "manifest.csv")
    p.add_argument("--apps", type=Path, default=ROOT / "data" / "app_exports", help="<app>_<capture_id>.json files")
    p.add_argument("--rerun", action="store_true", help="run the pipeline on each capture with ground truth first")
    p.add_argument("--ref", action="append", default=[], help="also run the pipeline as of this commit (repeatable)")
    args = p.parse_args(argv)

    with args.manifest.open(encoding="utf-8", newline="") as f:
        listed = {row["capture_id"] for row in csv.DictReader(f)}
    gts = {}
    for path in sorted(args.gt.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if path.stem in listed and data.get("_meta", {}).get("status") == "complete":
            gts[path.stem] = data

    head = git("rev-parse", "--short", "HEAD") or "unknown"
    versions = [(git("rev-parse", "--short", ref) or ref, ref) for ref in args.ref] + [(head, None)]
    command = "python -m eval.run" + (" --rerun" if args.rerun else "") + "".join(f" --ref {r}" for r in args.ref)
    sections: list[str] = []
    summary: list[str] = []
    headlines: list[str] = []
    groups: dict[tuple[str, str, str], list[tuple[str, dict]]] = {}
    missing: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for cid, gt in gts.items():
            for label, ref in versions:
                tag = cid if ref is None else f"{cid}@{label}"
                seconds = None
                if args.rerun:
                    capture = args.captures / cid
                    if not capture.is_dir():
                        missing.append(f"`{cid}`: capture not found under `{args.captures.name}/` (fetch it first)")
                        break
                    code, seconds = run_pipeline(pipeline_tree(ref, Path(tmp)), capture.resolve(), (args.runs / tag).resolve())
                    if code != 0:
                        missing.append(f"`{tag}`: pipeline exited with code {code}")
                        continue
                plan_path = args.runs / tag / "plan.json"
                if not plan_path.is_file():
                    missing.append(f"`{tag}`: no `{plan_path.name}` under `{args.runs.name}/{tag}/`")
                    continue
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                tier = plan.get("input_tier", "lidar")
                version = f"pipeline at `{label}`" + (" (current)" if ref is None else "")
                scored = score_plan(plan, gt)
                summary.append(summary_row(f"{cid} ({tier}), {version}", scored))
                headlines.append(headline(f"{cid}, {version}", scored))
                sections += capture_section(f"{cid} ({tier}), {version}", scored, seconds)
                for app_file in sorted(args.apps.glob(f"*_{cid}.json")):
                    sections += head_to_head_section(json.loads(app_file.read_text(encoding="utf-8")), scored)
                room = gt.get("_meta", {}).get("room")
                if room and len(plan.get("rooms", [])) == 1:
                    groups.setdefault((room, tier, label), []).append((cid, plan))

    lines = [
        "# Benchmark report",
        "",
        f"Generated by `{command}` at commit `{head}`. Ground truth is tape-measured "
        "(`data/ground_truth/`, assumptions listed in each file). Every number below comes from this script; "
        "do not edit by hand.",
        "",
        "## Summary",
        "",
        "| Capture and pipeline version | Worst wall | Ceiling | Floor area | Openings | Tape inside 90 % interval |",
        "|---|---|---|---|---|---|",
        *summary,
        "",
        *headlines,
        "",
        *sections,
        *repeat_section(groups),
    ]
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
