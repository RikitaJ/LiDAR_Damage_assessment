"""Cyclic wall-length alignment for gate scoring (brief §5.9)."""

from __future__ import annotations


def wall_pass_rate(
    pred_cm: list[float],
    truth_cm: list[float],
    *,
    tol_cm: float | None,
    tol_rel: float,
) -> tuple[float, list[dict]]:
    if not truth_cm:
        return 0.0, []
    if not pred_cm:
        return 0.0, [{"index": i, "err_cm": float("inf"), "rel_error": 1.0} for i in range(len(truth_cm))]

    best_rate = -1.0
    best_rows: list[dict] = []
    n_t = len(truth_cm)

    for reverse in (False, True):
        base = list(reversed(truth_cm)) if reverse else list(truth_cm)
        for rot in range(n_t):
            rotated = base[rot:] + base[:rot]
            n = min(len(pred_cm), len(rotated))
            rows: list[dict] = []
            ok = 0
            for i in range(n):
                err = abs(pred_cm[i] - rotated[i])
                rel = err / max(rotated[i], 1e-6)
                pass_wall = err <= tol_cm if tol_cm is not None else rel <= tol_rel
                if pass_wall:
                    ok += 1
                rows.append({"index": i, "err_cm": err, "rel_error": rel})
            for i in range(n, len(truth_cm)):
                rows.append({"index": i, "err_cm": float("inf"), "rel_error": 1.0})
            rate = ok / len(truth_cm)
            if rate > best_rate:
                best_rate = rate
                best_rows = rows

    return best_rate, best_rows
