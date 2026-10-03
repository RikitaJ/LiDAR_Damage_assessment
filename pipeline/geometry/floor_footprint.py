"""Floor plane + occupancy footprint (reduces walk-path inflation vs axis bbox)."""

from __future__ import annotations

import numpy as np

try:
    from shapely.geometry import LineString, MultiPoint
except ImportError:  # pragma: no cover
    LineString = None  # type: ignore
    MultiPoint = None  # type: ignore

FLOOR_RANSAC_ITERS = 64
FLOOR_INLIER_M = 0.045
FLOOR_SLICE_M = 0.06
OCC_GRID_M = 0.12
OCC_MIN_HITS = 4
PATH_BUFFER_M = 1.15
PATH_SHRINK_M = 0.35


def fit_floor_plane(pts: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, float]:
    """Return unit normal (Y-up) and plane offset n·p = d."""
    best_n = np.array([0.0, 1.0, 0.0], dtype=float)
    best_d = float(np.median(pts[:, 1]))
    best_count = 0
    if len(pts) < 30:
        return best_n, best_d

    for _ in range(FLOOR_RANSAC_ITERS):
        idx = rng.choice(len(pts), size=3, replace=False)
        p0, p1, p2 = pts[idx]
        n = np.cross(p1 - p0, p2 - p0)
        norm = float(np.linalg.norm(n))
        if norm < 1e-8:
            continue
        n = n / norm
        if n[1] < 0:
            n = -n
        d = float(np.dot(n, p0))
        dist = np.abs(pts @ n - d)
        count = int((dist < FLOOR_INLIER_M).sum())
        if count > best_count:
            best_count = count
            best_n, best_d = n, d
    return best_n, best_d


def floor_slice_xz(pts: np.ndarray, n: np.ndarray, d: float) -> np.ndarray:
    dist = np.abs(pts @ n - d)
    floor = pts[dist <= FLOOR_SLICE_M]
    if len(floor) < 40:
        floor = pts[dist <= FLOOR_SLICE_M * 2.5]
    return floor[:, [0, 2]] if len(floor) else pts[:, [0, 2]]


def footprint_from_floor_xz(
    floor_xz: np.ndarray,
    *,
    rng: np.random.Generator,
) -> tuple[list[list[float]], float, list[str]]:
    warnings: list[str] = []
    if len(floor_xz) < 30:
        warnings.append("too few floor points; using tight bbox")
        return _corners_bbox(floor_xz), _area_bbox(floor_xz), warnings

    med = np.median(floor_xz, axis=0)
    d = np.linalg.norm(floor_xz - med, axis=1)
    keep = d <= float(np.percentile(d, 90))
    xz = floor_xz[keep] if np.any(keep) else floor_xz

    corners, area = _occupancy_footprint(xz, warnings)
    if corners is None:
        corners = _snap_manhattan(_corners_bbox(xz))
        area = _polygon_area(corners)
    return corners, area, warnings


def footprint_from_path_xz(xs: np.ndarray, zs: np.ndarray) -> tuple[list[list[float]], float]:
    """Video / sparse trajectory: buffer camera path, not a 3×3 placeholder."""
    if LineString is None or len(xs) < 2:
        return _path_bbox_corners(xs, zs), max(float(xs.max() - xs.min()) * float(zs.max() - zs.min()), 0.5)

    line = LineString([(float(x), float(z)) for x, z in zip(xs, zs)])
    poly = line.buffer(PATH_BUFFER_M, cap_style=2, join_style=2)
    if poly.is_empty:
        return _path_bbox_corners(xs, zs), 1.0
    shrunk = poly.buffer(-PATH_SHRINK_M)
    if not shrunk.is_empty and shrunk.area > 2.0:
        poly = shrunk
    rect = poly.minimum_rotated_rectangle
    coords = list(rect.exterior.coords)
    raw = [[float(coords[i][0]), float(coords[i][1])] for i in range(min(4, len(coords)))]
    corners = _snap_manhattan(raw)
    return corners, _polygon_area(corners)


def _occupancy_footprint(
    xz: np.ndarray,
    warnings: list[str],
) -> tuple[list[list[float]] | None, float]:
    min_x, min_z = float(xz[:, 0].min()), float(xz[:, 1].min())
    max_x, max_z = float(xz[:, 0].max()), float(xz[:, 1].max())
    span = max(max_x - min_x, max_z - min_z, 0.5)
    nx = max(2, int(span / OCC_GRID_M))
    nz = max(2, int(span / OCC_GRID_M))
    grid = np.zeros((nx, nz), dtype=np.int32)
    ix = np.clip(((xz[:, 0] - min_x) / span * (nx - 1)).astype(int), 0, nx - 1)
    iz = np.clip(((xz[:, 1] - min_z) / span * (nz - 1)).astype(int), 0, nz - 1)
    for i, j in zip(ix, iz):
        grid[i, j] += 1

    nonzero = grid[grid > 0]
    if len(nonzero) == 0:
        return None, 0.0
    thresh = max(OCC_MIN_HITS, int(np.percentile(nonzero, 30)))
    occ = grid >= thresh
    for _ in range(2):
        eroded = occ.copy()
        for i in range(nx):
            for j in range(nz):
                if not occ[i, j]:
                    continue
                if i == 0 or i == nx - 1 or j == 0 or j == nz - 1:
                    eroded[i, j] = False
                    continue
                if not (occ[i - 1, j] and occ[i + 1, j] and occ[i, j - 1] and occ[i, j + 1]):
                    eroded[i, j] = False
        occ = eroded

    cells: list[tuple[float, float]] = []
    for i in range(nx):
        for j in range(nz):
            if occ[i, j]:
                cx = min_x + (i + 0.5) / nx * span
                cz = min_z + (j + 0.5) / nz * span
                cells.append((cx, cz))

    if len(cells) < 8:
        warnings.append("sparse floor occupancy; bbox fallback")
        return None, 0.0

    if MultiPoint is None:
        return None, 0.0

    hull = MultiPoint(cells).convex_hull
    if hull.is_empty or hull.area < 0.8:
        return None, 0.0

    rect = hull.minimum_rotated_rectangle
    coords = list(rect.exterior.coords)
    raw = [[float(coords[i][0]), float(coords[i][1])] for i in range(min(4, len(coords)))]
    corners = _snap_manhattan(raw)
    return corners, _polygon_area(corners)


def _snap_manhattan(corners: list[list[float]]) -> list[list[float]]:
    xs = [c[0] for c in corners]
    zs = [c[1] for c in corners]
    return [
        [min(xs), min(zs)],
        [max(xs), min(zs)],
        [max(xs), max(zs)],
        [min(xs), max(zs)],
    ]


def _corners_bbox(xz: np.ndarray) -> list[list[float]]:
    return [
        [float(xz[:, 0].min()), float(xz[:, 1].min())],
        [float(xz[:, 0].max()), float(xz[:, 1].min())],
        [float(xz[:, 0].max()), float(xz[:, 1].max())],
        [float(xz[:, 0].min()), float(xz[:, 1].max())],
    ]


def _path_bbox_corners(xs: np.ndarray, zs: np.ndarray) -> list[list[float]]:
    return _corners_bbox(np.column_stack([xs, zs]))


def _area_bbox(xz: np.ndarray) -> float:
    return max(float(xz[:, 0].max() - xz[:, 0].min()) * float(xz[:, 1].max() - xz[:, 1].min()), 0.5)


def _polygon_area(corners: list[list[float]]) -> float:
    if len(corners) < 3:
        return 0.5
    area = 0.0
    for i in range(len(corners)):
        x0, z0 = corners[i]
        x1, z1 = corners[(i + 1) % len(corners)]
        area += x0 * z1 - x1 * z0
    return max(abs(area) * 0.5, 0.5)
