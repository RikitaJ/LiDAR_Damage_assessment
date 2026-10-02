from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from jsonschema import Draft202012Validator


def write_plan(payload: dict, schema_path: Path, out_json: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def render_plan(stitched: dict, rooms: list[dict], out_png: Path) -> str:
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.set_aspect("equal")
    ax.set_title("Stitched floor plan (m)")

    for wall in stitched.get("global_walls", []):
        pl = wall["polyline_m"]
        if len(pl) < 2:
            continue
        xs, ys = [p[0] for p in pl], [p[1] for p in pl]
        ax.plot(xs, ys, "k-", lw=2)
        mx, my = (xs[0] + xs[1]) / 2, (ys[0] + ys[1]) / 2
        length = wall["length_m"]["value_m"]
        ax.text(mx, my, f"{length:.2f}m", fontsize=8, ha="center", color="navy")

    for r in rooms:
        tx, _, tz = r["pose_world"]["translation_m"]
        ax.text(tx, tz, r["name"], fontsize=10, fontweight="bold")

    ax.set_xlabel("X (m)")
    ax.set_ylabel("Z (m)")
    ax.grid(True, alpha=0.3)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out_png)
