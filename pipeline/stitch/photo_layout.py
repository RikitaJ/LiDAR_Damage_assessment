"""Photo-tier layout solver (brief §5.6): door pairing + 90° rotations + overlap score."""

from __future__ import annotations

from copy import deepcopy

import numpy as np

from pipeline.geometry.overlap import pairwise_overlap_m2

WALL_THICKNESS_M = 0.15
DOOR_WIDTH_TOL_M = 0.25


def infer_photo_adjacency(rooms: list[dict]) -> list[tuple[str, str, str]]:
    """Pair doors by width agreement only (never folder names)."""
    ids = [r["room_id"] for r in rooms]
    doors: dict[str, list[tuple[str, float]]] = {}
    for r in rooms:
        for w in r.get("walls", []):
            for op in w.get("openings", []):
                if op.get("kind") != "door":
                    continue
                doors.setdefault(r["room_id"], []).append(
                    (op["id"], float(op["width_m"]["value_m"]))
                )

    candidates: list[tuple[float, str, str, str]] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            da, db = doors.get(a, []), doors.get(b, [])
            if not da or not db:
                continue
            best = min(
                ((oa, ob, abs(wa - wb)) for oa, wa in da for ob, wb in db),
                key=lambda t: t[2],
            )
            oa, ob, err = best
            if err > DOOR_WIDTH_TOL_M:
                continue
            if not _mutual_best_door(a, oa, b, ob, doors, ids):
                continue
            candidates.append((err, a, b, oa))

    if not candidates:
        return []

    candidates.sort(key=lambda t: t[0])
    parent = {rid: rid for rid in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        parent[find(b)] = find(a)

    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    hub = max(ids, key=lambda rid: len(doors.get(rid, [])))
    if len(doors.get(hub, [])) >= 2:
        for oa, wa in doors[hub]:
            partner = _nearest_door_partner(hub, oa, wa, doors, ids)
            b, ob = partner
            if not b or not _mutual_best_door(hub, oa, b, ob, doors, ids):
                continue
            key = (hub, b, oa)
            if key in seen:
                continue
            out.append(key)
            seen.add(key)
            union(hub, b)

    for _err, a, b, oa in candidates:
        key = (a, b, oa)
        if key in seen:
            continue
        if find(a) == find(b):
            continue
        out.append(key)
        seen.add(key)
        union(a, b)

    return out


def _mutual_best_door(
    a: str,
    oa: str,
    b: str,
    ob: str,
    doors: dict[str, list[tuple[str, float]]],
    ids: list[str],
) -> bool:
    wa = next(w for oid, w in doors[a] if oid == oa)
    wb = next(w for oid, w in doors[b] if oid == ob)
    best_for_a = _nearest_door_partner(a, oa, wa, doors, ids)
    best_for_b = _nearest_door_partner(b, ob, wb, doors, ids)
    return best_for_a == (b, ob) and best_for_b == (a, oa)


def _nearest_door_partner(
    room_id: str,
    opening_id: str,
    width_m: float,
    doors: dict[str, list[tuple[str, float]]],
    ids: list[str],
) -> tuple[str, str]:
    best: tuple[float, str, str] | None = None
    for other in ids:
        if other == room_id:
            continue
        for oid, ow in doors.get(other, []):
            diff = abs(width_m - ow)
            if diff > DOOR_WIDTH_TOL_M:
                continue
            if best is None or diff < best[0] or (diff == best[0] and other < best[1]):
                best = (diff, other, oid)
    return (best[1], best[2]) if best else ("", "")


def layout_photo_rooms(rooms: list[dict], edges: list[tuple[str, str, str]]) -> None:
    """Place rooms in world frame; mutates rooms (rotation + pose_world)."""
    if not rooms:
        return
    by_id = {r["room_id"]: r for r in rooms}
    root = rooms[0]["room_id"]
    poses: dict[str, np.ndarray] = {root: np.zeros(2)}

    for _ in range(max(len(rooms) * 4, 1)):
        progress = False
        for a, b, opening_id in edges:
            for src, anchor in ((a, b), (b, a)):
                if anchor not in poses or src in poses:
                    continue
                best_q, best_pose, best_score = _best_rotation_placement(
                    by_id[src], by_id[anchor], opening_id, poses
                )
                if best_q:
                    rotate_room_local(by_id[src], best_q)
                poses[src] = best_pose
                progress = True
        if len(poses) >= len(rooms):
            break
        if not progress:
            break

    for r in rooms:
        rid = r["room_id"]
        if rid not in poses:
            poses[rid] = np.array([4.0 * len(poses), 0.0])
        tx, tz = float(poses[rid][0]), float(poses[rid][1])
        r["pose_world"] = {
            "translation_m": [tx, 0.0, tz],
            "rotation_quat": [0.0, 0.0, 0.0, 1.0],
        }

    _nudge_apart_if_overlap(rooms, by_id, poses, edges)


def rotate_room_local(room: dict, quarter_turns: int) -> None:
    q = int(quarter_turns) % 4
    if q == 0:
        return
    cx, cz = _centroid_local(room)
    for w in room.get("walls", []):
        pl = w.get("polyline_m") or []
        w["polyline_m"] = [_rotate_point(p, cx, cz, q) for p in pl]
        for op in w.get("openings", []):
            if "anchor_m" in op:
                op["anchor_m"] = _rotate_point(op["anchor_m"], cx, cz, q)


def _rotate_point(p: list, cx: float, cz: float, q: int) -> list[float]:
    x, z = float(p[0]) - cx, float(p[1]) - cz
    for _ in range(q):
        x, z = z, -x
    return [x + cx, z + cz]


def _best_rotation_placement(
    src_template: dict,
    anchor_room: dict,
    opening_id: str,
    anchor_poses: dict[str, np.ndarray],
) -> tuple[int, np.ndarray, float]:
    anchor_id = anchor_room["room_id"]
    ap = anchor_poses[anchor_id]
    best_q = 0
    best_pose = ap + np.array([4.0, 0.0])
    best_score = 1e9

    for q in range(4):
        scratch = deepcopy(src_template)
        if q:
            rotate_room_local(scratch, q)
        pose, door_err = _pose_align_door(scratch, anchor_room, opening_id, ap)
        if pose is None:
            continue
        score = _layout_score(scratch, anchor_room, pose, ap, door_err)
        if score < best_score:
            best_score = score
            best_q = q
            best_pose = pose
    return best_q, best_pose, best_score


def _pose_align_door(
    src: dict,
    anchor: dict,
    opening_id: str,
    anchor_pose: np.ndarray,
) -> tuple[np.ndarray | None, float]:
    da, db = _door_points(src, anchor, opening_id)
    if da is None or db is None:
        return anchor_pose + np.array([4.0, 0.0]), 1.0
    normal = _interior_normal(src, opening_id)
    pose = anchor_pose + (db - da)
    if normal is not None:
        cs = np.array(_centroid_local(src), dtype=float)
        shift = float(np.dot(cs - da, normal))
        if shift < 0.15:
            shift = min(_room_span(src), 2.5) * 0.42
        pose = pose + normal * (shift + WALL_THICKNESS_M)
    width_err = _door_width_mismatch(src, anchor, opening_id)
    return pose, width_err


def _layout_score(
    src: dict,
    anchor: dict,
    src_pose: np.ndarray,
    anchor_pose: np.ndarray,
    door_err: float,
) -> float:
    tmp_src = deepcopy(src)
    tmp_src["pose_world"] = {
        "translation_m": [float(src_pose[0]), 0.0, float(src_pose[1])],
        "rotation_quat": [0, 0, 0, 1],
    }
    tmp_anchor = deepcopy(anchor)
    tmp_anchor["pose_world"] = {
        "translation_m": [float(anchor_pose[0]), 0.0, float(anchor_pose[1])],
        "rotation_quat": [0, 0, 0, 1],
    }
    overlap = pairwise_overlap_m2([tmp_src, tmp_anchor])
    compact = float(np.linalg.norm(src_pose - anchor_pose))
    return overlap * 10.0 + door_err * 2.0 + compact * 0.05


def _nudge_apart_if_overlap(
    rooms: list[dict],
    by_id: dict[str, dict],
    poses: dict[str, np.ndarray],
    edges: list[tuple[str, str, str]],
) -> None:
    for _ in range(6):
        for r in rooms:
            tx, tz = poses[r["room_id"]]
            r["pose_world"]["translation_m"] = [float(tx), 0.0, float(tz)]
        if pairwise_overlap_m2(rooms) <= 0.05:
            return
        for a, b, oid in edges:
            for src, anchor in ((a, b), (b, a)):
                if src not in poses or anchor not in poses:
                    continue
                normal = _interior_normal(by_id[src], oid)
                if normal is None:
                    continue
                da, db = _door_points(by_id[src], by_id[anchor], oid)
                if da is None:
                    continue
                poses[src] = poses[anchor] + (db - da) + normal * (_room_span(by_id[src]) * 0.45)
        for r in rooms:
            rid = r["room_id"]
            tx, tz = poses[rid]
            r["pose_world"]["translation_m"] = [float(tx), 0.0, float(tz)]


def _door_points(
    src: dict, anchor: dict, opening_id: str
) -> tuple[np.ndarray | None, np.ndarray | None]:
    sd = _doors_local(src)
    ad = _doors_local(anchor)
    if not sd or not ad:
        return None, None
    for sid, sp, _ in sd:
        if opening_id and sid == opening_id:
            for _, ap, _ in ad:
                return sp, ap
    best = min(
        ((sp, ap, abs(sw - aw)) for sid, sp, sw in sd for _, ap, aw in ad),
        key=lambda t: t[2],
    )
    return best[0], best[1]


def _doors_local(room: dict) -> list[tuple[str, np.ndarray, float]]:
    out: list[tuple[str, np.ndarray, float]] = []
    for w in room.get("walls", []):
        pl = w.get("polyline_m") or []
        if len(pl) < 2:
            continue
        for op in w.get("openings", []):
            if op.get("kind") != "door":
                continue
            if "anchor_m" in op:
                pt = np.array(op["anchor_m"], dtype=float)
            else:
                p0, p1 = np.array(pl[0], float), np.array(pl[1], float)
                pt = (p0 + p1) / 2
            out.append((op["id"], pt, float(op["width_m"]["value_m"])))
    return out


def _door_width_mismatch(src: dict, anchor: dict, opening_id: str) -> float:
    sd = _doors_local(src)
    ad = _doors_local(anchor)
    if not sd or not ad:
        return 0.5
    best = min(
        abs(sw - aw) for _, _, sw in sd for _, _, aw in ad
    )
    return float(best)


def _interior_normal(room: dict, opening_id: str) -> np.ndarray | None:
    for w in room.get("walls", []):
        pl = w.get("polyline_m") or []
        if len(pl) < 2:
            continue
        for op in w.get("openings", []):
            if op.get("kind") != "door":
                continue
            if opening_id and op.get("id") != opening_id:
                continue
            p0 = np.array(pl[0], dtype=float)
            p1 = np.array(pl[1], dtype=float)
            tangent = p1 - p0
            tl = float(np.linalg.norm(tangent))
            if tl < 1e-6:
                continue
            tangent = tangent / tl
            normal = np.array([-tangent[1], tangent[0]], dtype=float)
            mid = (p0 + p1) * 0.5
            centroid = _centroid_local(room)
            if np.dot(centroid - mid, normal) < 0:
                normal = -normal
            return normal
    return None


def _centroid_local(room: dict) -> tuple[float, float]:
    pts = [p for w in room.get("walls", []) for p in w.get("polyline_m", [])]
    if not pts:
        return 0.0, 0.0
    arr = np.array(pts, dtype=float)
    return float(arr[:, 0].mean()), float(arr[:, 1].mean())


def _room_span(room: dict) -> float:
    pts = [p for w in room.get("walls", []) for p in w.get("polyline_m", [])]
    if not pts:
        return 3.0
    xs = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    return max(max(xs) - min(xs), max(zs) - min(zs), 2.5)
