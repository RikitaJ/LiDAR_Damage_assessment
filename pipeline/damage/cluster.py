"""Cluster damage cues in image space before UV projection (multi-view agreement)."""

from __future__ import annotations


def cluster_cross_view_hits(
    pairs: list[tuple[dict, dict]],
    *,
    u_tol: float = 0.14,
) -> list[tuple[dict, dict]]:
    """Merge hits from different stills that agree on room, class, and horizontal position."""
    if len(pairs) < 2:
        return pairs

    buckets: dict[tuple[str, str, str], list[tuple[dict, dict]]] = {}
    for room, hit in pairs:
        rid = str(room.get("room_id", ""))
        cls = str(hit.get("class") or "water_stain")
        st = str(hit.get("surface_type") or "wall")
        buckets.setdefault((rid, cls, st), []).append((room, hit))

    out: list[tuple[dict, dict]] = []
    for group in buckets.values():
        out.extend(_cluster_group(group, u_tol=u_tol))
    return out


def _cluster_group(group: list[tuple[dict, dict]], *, u_tol: float) -> list[tuple[dict, dict]]:
    if len(group) == 1:
        return group
    used = [False] * len(group)
    merged: list[tuple[dict, dict]] = []
    for i, (room_a, hit_a) in enumerate(group):
        if used[i]:
            continue
        cluster_hits = [hit_a]
        room = room_a
        used[i] = True
        ua = _u_center(hit_a)
        for j in range(i + 1, len(group)):
            if used[j]:
                continue
            room_b, hit_b = group[j]
            if room_b.get("room_id") != room.get("room_id"):
                continue
            if abs(_u_center(hit_b) - ua) <= u_tol:
                cluster_hits.append(hit_b)
                used[j] = True
        merged.append((room, _combine_hits(cluster_hits)))
    return merged


def _u_center(hit: dict) -> float:
    try:
        u0, u1 = hit.get("u0_frac"), hit.get("u1_frac")
        if u0 is not None and u1 is not None:
            return (float(u0) + float(u1)) / 2.0
        return float(hit.get("u_center_frac", 0.4))
    except (TypeError, ValueError):
        return 0.4


def _combine_hits(hits: list[dict]) -> dict:
    base = dict(hits[0])
    if len(hits) == 1:
        return base
    us = [_u_center(h) for h in hits]
    base["u_center_frac"] = sum(us) / len(us)
    u0s = [h.get("u0_frac") for h in hits if h.get("u0_frac") is not None]
    u1s = [h.get("u1_frac") for h in hits if h.get("u1_frac") is not None]
    if u0s and u1s:
        base["u0_frac"] = min(float(x) for x in u0s)
        base["u1_frac"] = max(float(x) for x in u1s)
    base["view_count"] = sum(int(h.get("view_count", 1)) for h in hits)
    base["score"] = min(0.94, max(float(h.get("score", 0.45)) for h in hits) + 0.06 * (len(hits) - 1))
    base["area_m2"] = max(float(h.get("area_m2", 0.08)) for h in hits)
    src = str(base.get("source", ""))
    if "+multi_view" not in src:
        base["source"] = (src + "+multi_view").lstrip("+")
    return base
