"""Score a plan against tape ground truth: errors, gates (brief §3, A1) and interval coverage."""

from __future__ import annotations

from dataclasses import dataclass

# (mode, tolerance): "abs" in metres, "rel" as a fraction. None = no gate for that tier.
TOLERANCES: dict[str, dict[str, tuple[str, float] | None]] = {
    "lidar": {"wall": ("abs", 0.02), "area": ("rel", 0.02), "ceiling": ("abs", 0.015)},
    "video": {"wall": ("rel", 0.03), "area": None, "ceiling": ("abs", 0.015)},
    "photos": {"wall": ("rel", 0.08), "area": ("rel", 0.08), "ceiling": ("abs", 0.015)},
}
REPEAT_WALL_ABS_M = 0.01
REPEAT_WALL_REL = 0.005
REPEAT_CEILING_SPREAD_M = 0.01


@dataclass
class Row:
    name: str
    truth: float
    value: float
    lo: float | None
    hi: float | None
    tolerance: tuple[str, float] | None

    @property
    def error(self) -> float:
        return self.value - self.truth

    @property
    def passed(self) -> bool | None:
        if self.tolerance is None:
            return None
        mode, tol = self.tolerance
        err = abs(self.error) if mode == "abs" else abs(self.error) / self.truth
        return err <= tol

    @property
    def covered(self) -> bool:
        return self.lo is not None and self.hi is not None and self.lo <= self.truth <= self.hi


def measurement(m: dict) -> tuple[float, float | None, float | None]:
    return float(m.get("value", m.get("value_m"))), m.get("lo"), m.get("hi")


def align_walls(pred: list[float], truth: list[float]) -> list[int | None]:
    """Map each truth wall to a predicted wall index: best cyclic rotation, either direction."""
    n = len(pred)
    if n == 0:
        return [None] * len(truth)
    best: tuple[float, list[int | None]] | None = None
    for direction in (1, -1):
        for shift in range(n):
            idx = [(shift + direction * i) % n if i < n else None for i in range(len(truth))]
            cost = sum(abs(pred[j] - t) for j, t in zip(idx, truth) if j is not None)
            if best is None or cost < best[0]:
                best = (cost, idx)
    return best[1]


def score_room(room: dict, gt: dict, room_id: str, tier: str) -> tuple[list[Row], dict]:
    tol = TOLERANCES.get(tier, TOLERANCES["photos"])
    rows: list[Row] = []

    truth_walls = [cm / 100 for cm in gt.get("wall_lengths_cm", {}).get(room_id, [])]
    pred = [measurement(w["length_m"]) for w in room.get("walls", [])]
    for k, j in enumerate(align_walls([p[0] for p in pred], truth_walls)):
        if j is not None:
            v, lo, hi = pred[j]
            rows.append(Row(f"Wall {k + 1}", truth_walls[k], v, lo, hi, tol["wall"]))

    ceiling_cm = gt.get("ceiling_height_cm", {}).get(room_id)
    if ceiling_cm is not None:
        v, lo, hi = measurement(room["ceiling_height_m"])
        rows.append(Row("Ceiling height", ceiling_cm / 100, v, lo, hi, tol["ceiling"]))

    area = gt.get("footprint_area_m2")
    if area is not None:
        v, lo, hi = measurement(room["floor_area_m2"])
        rows.append(Row("Floor area (m²)", float(area), v, lo, hi, tol["area"]))

    detection = {}
    counts = gt.get("opening_counts", {}).get(room_id)
    if counts:
        found: dict[str, int] = {}
        for w in room.get("walls", []):
            for op in w.get("openings", []):
                found[op.get("kind", "opening")] = found.get(op.get("kind", "opening"), 0) + 1
        kinds = sorted(set(counts) | set(found))
        detection = {
            "truth": counts,
            "found": found,
            "missed": sum(max(0, counts.get(k, 0) - found.get(k, 0)) for k in kinds),
            "phantom": sum(max(0, found.get(k, 0) - counts.get(k, 0)) for k in kinds),
        }
    return rows, detection


def repeatability(room_a: dict, room_b: dict) -> dict:
    """Two captures of one room at one tier: per-wall agreement (1 cm or 0.5 %) and ceiling spread."""
    a = [measurement(w["length_m"])[0] for w in room_a.get("walls", [])]
    b = [measurement(w["length_m"])[0] for w in room_b.get("walls", [])]
    pairs = [(a[k], b[j]) for k, j in enumerate(align_walls(b, a)) if j is not None]
    walls = [
        {"a": x, "b": y, "delta": abs(x - y),
         "passed": abs(x - y) <= REPEAT_WALL_ABS_M or abs(x - y) / max(x, 1e-9) <= REPEAT_WALL_REL}
        for x, y in pairs
    ]
    spread = abs(measurement(room_a["ceiling_height_m"])[0] - measurement(room_b["ceiling_height_m"])[0])
    return {
        "walls": walls,
        "walls_passed": bool(walls) and all(w["passed"] for w in walls) and len(a) == len(b),
        "ceiling_spread": spread,
        "ceiling_passed": spread <= REPEAT_CEILING_SPREAD_M,
    }
