"""Multi-room stitch: door adjacency graph + LiDAR door alignment + optional loop closure."""

from __future__ import annotations

from copy import deepcopy

import networkx as nx
import numpy as np

from pipeline.config import InputTier
from pipeline.geometry.floor_polygon import floor_area_m2
from pipeline.measure.confidence import area_m2


def stitch(
    rooms: list[dict],
    tier: InputTier,
    adjacency_hints: list[tuple[str, str, str]],
    loop_closure: bool,
) -> tuple[list[dict], dict]:
    rooms = deepcopy(rooms)
    edges = adjacency_hints or _infer_adjacency(rooms)
    g = nx.Graph()
    for r in rooms:
        g.add_node(r["room_id"])
    for a, b, oid in edges:
        g.add_edge(a, b, opening_id=oid)

    if tier == InputTier.LIDAR and edges:
        _place_by_doors(rooms, edges, loop_closure)
    else:
        _place_chain(rooms, g, loop_closure)

    global_walls = _walls_in_world(rooms)
    footprint = floor_area_m2(global_walls) or sum(r["floor_area_m2"]["value_m"] for r in rooms)

    stitched = {
        "footprint_area_m2": area_m2(footprint, tier),
        "adjacency": [{"room_a": a, "room_b": b, "via_opening_id": oid} for a, b, oid in edges],
        "global_walls": global_walls,
        "render_path": "",
    }
    return rooms, stitched


def _infer_adjacency(rooms: list[dict]) -> list[tuple[str, str, str]]:
    """Match doors between room pairs by similar width (LiDAR)."""
    out: list[tuple[str, str, str]] = []
    ids = [r["room_id"] for r in rooms]
    doors: dict[str, list[tuple[str, float]]] = {}
    for r in rooms:
        for w in r["walls"]:
            for op in w["openings"]:
                if op["kind"] == "door":
                    doors.setdefault(r["room_id"], []).append((op["id"], op["width_m"]["value_m"]))

    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            da, db = doors.get(a, []), doors.get(b, [])
            if not da or not db:
                continue
            best = min(((oa, ob, abs(wa - wb)) for oa, wa in da for ob, wb in db), key=lambda t: t[2])
            if best[2] < 0.25:
                out.append((a, b, best[0]))
    if not out and len(ids) >= 2:
        out.append((ids[0], ids[1], "inferred"))
    return out


def _matched_door_points(
    room_src: dict, room_anchor: dict, hint_id: str
) -> tuple[np.ndarray | None, np.ndarray | None]:
    src_doors = _door_points(room_src)
    anchor_doors = _door_points(room_anchor)
    if not src_doors or not anchor_doors:
        return None, None
    best = None
    for sid, sp, sw in src_doors:
        for aid, ap, aw in anchor_doors:
            if hint_id and (sid == hint_id or aid == hint_id):
                return sp, ap
            diff = abs(sw - aw)
            if best is None or diff < best[0]:
                best = (diff, sp, ap)
    if best:
        return best[1], best[2]
    return None, None


def _door_points(room: dict) -> list[tuple[str, np.ndarray, float]]:
    out: list[tuple[str, np.ndarray, float]] = []
    for w in room["walls"]:
        pl = w.get("polyline_m") or []
        if len(pl) < 2:
            continue
        for op in w["openings"]:
            if op["kind"] != "door":
                continue
            if "anchor_m" in op:
                pt = np.array(op["anchor_m"], dtype=float)
            else:
                p0, p1 = np.array(pl[0], float), np.array(pl[1], float)
                pt = (p0 + p1) / 2
            out.append((op["id"], pt, op["width_m"]["value_m"]))
    return out


def _door_point(room: dict, opening_id: str) -> np.ndarray | None:
    for w in room["walls"]:
        pl = w.get("polyline_m") or []
        if len(pl) < 2:
            continue
        for op in w["openings"]:
            if op["kind"] != "door":
                continue
            if opening_id and op["id"] != opening_id:
                continue
            if "anchor_m" in op:
                return np.array(op["anchor_m"], dtype=float)
            p0, p1 = np.array(pl[0], float), np.array(pl[1], float)
            return (p0 + p1) / 2
    for w in room["walls"]:
        pl = w.get("polyline_m") or []
        if len(pl) < 2:
            continue
        for op in w["openings"]:
            if op["kind"] == "door":
                if "anchor_m" in op:
                    return np.array(op["anchor_m"], dtype=float)
                p0, p1 = np.array(pl[0], float), np.array(pl[1], float)
                return (p0 + p1) / 2
    return None


def _place_by_doors(
    rooms: list[dict],
    edges: list[tuple[str, str, str]],
    loop_closure: bool,
) -> None:
    by_id = {r["room_id"]: r for r in rooms}
    root = rooms[0]["room_id"]
    poses: dict[str, np.ndarray] = {root: np.zeros(2)}

    for _ in range(max(len(rooms) * 2, 1)):
        progress = False
        for a, b, opening_id in edges:
            for src, anchor in ((a, b), (b, a)):
                if anchor not in poses or src in poses:
                    continue
                da, db = _matched_door_points(by_id[src], by_id[anchor], opening_id)
                if da is not None and db is not None:
                    poses[src] = poses[anchor] + (db - da)
                else:
                    poses[src] = poses[anchor] + np.array([4.0, 0.0])
                progress = True
        if len(poses) >= len(rooms):
            break
        if not progress:
            break

    for r in rooms:
        if r["room_id"] not in poses:
            poses[r["room_id"]] = np.array([4.0 * len(poses), 0.0])

    if loop_closure:
        for a, b, _ in edges:
            if a in poses and b in poses:
                d = poses[a] - poses[b]
                if np.linalg.norm(d) > 0.01:
                    poses[b] += d * 0.05

    _separate_overlapping(rooms, by_id, poses, edges)

    for r in rooms:
        tx, tz = poses[r["room_id"]]
        r["pose_world"] = {"translation_m": [float(tx), 0.0, float(tz)], "rotation_quat": [0, 0, 0, 1]}


def _separate_overlapping(
    rooms: list[dict],
    by_id: dict[str, dict],
    poses: dict[str, np.ndarray],
    edges: list[tuple[str, str, str]],
) -> None:
    for a, b, _ in edges:
        for src, anchor in ((a, b), (b, a)):
            if src not in poses or anchor not in poses:
                continue
            ca = _centroid_local(by_id[anchor])
            cs = _centroid_local(by_id[src])
            direction = cs - ca
            if float(np.linalg.norm(direction)) < 0.05:
                direction = np.array([1.0, 0.0])
            direction = direction / np.linalg.norm(direction)
            push = _room_span(by_id[src]) * 0.55 + _room_span(by_id[anchor]) * 0.45
            poses[src] = poses[anchor] + direction * push


def _centroid_local(room: dict) -> np.ndarray:
    pts = [p for w in room["walls"] for p in w.get("polyline_m", [])]
    if not pts:
        return np.zeros(2)
    arr = np.array(pts, dtype=float)
    return arr.mean(axis=0)


def _room_span(room: dict) -> float:
    pts = [p for w in room["walls"] for p in w.get("polyline_m", [])]
    if not pts:
        return 3.0
    xs = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    return max(max(xs) - min(xs), max(zs) - min(zs), 2.5)


def _place_chain(rooms: list[dict], g: nx.Graph, loop_closure: bool) -> None:
    if not rooms:
        return
    root = rooms[0]["room_id"]
    poses = {root: np.array([0.0, 0.0])}
    q = [root]
    seen = {root}
    step = 0.0
    while q:
        cur = q.pop(0)
        for nbr in g.neighbors(cur):
            if nbr in seen:
                if loop_closure:
                    poses[nbr] += (poses[cur] - poses[nbr]) * 0.05
                continue
            step += 4.0
            poses[nbr] = poses[cur] + np.array([step, 0.0])
            seen.add(nbr)
            q.append(nbr)
    for r in rooms:
        if r["room_id"] not in poses:
            step += 4.0
            poses[r["room_id"]] = np.array([step, 0.0])
        tx, tz = poses[r["room_id"]]
        r["pose_world"] = {"translation_m": [float(tx), 0.0, float(tz)], "rotation_quat": [0, 0, 0, 1]}


def _walls_in_world(rooms: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in rooms:
        tx, _, tz = r["pose_world"]["translation_m"]
        for w in r["walls"]:
            pl = w["polyline_m"]
            out.append(
                {
                    **w,
                    "id": f"{r['room_id']}_{w['id']}",
                    "polyline_m": [[p[0] + tx, p[1] + tz] for p in pl],
                }
            )
    return out
