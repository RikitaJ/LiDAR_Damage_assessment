# Fix-loop declaration (written before the fix)

**Baseline:** tag `fixloop-before`, `docs/BENCHMARK_REPORT.md`. Room B1, LiDAR tier (Stray Scanner, iPhone 13 Pro), scored against tape ground truth (`data/ground_truth/lidar_B1_rep1.json`).

## 1. Worst gate and failing number

**LiDAR walls / floor area** (A1: walls ±2 cm, area ±2 %). The long walls measure **0.672 m against 5.600 m** taped (−4.93 m, about 250× the tolerance). The short walls measure 2.771 m against 4.350 m. The floor area is **1.86 m² against 24.36 m² (−92.4 %)**. None of the six tape values lies inside its 90 % interval. The ceiling gate fails as well: 2.200 m against 2.980 m.

## 2. Root-cause hypothesis and evidence

Since `817bab7`, the room outline is built from the floor the scanner can see: floor points, then an occupancy grid, then 2× erosion (`pipeline/geometry/floor_footprint.py`). In a furnished bedroom the bed and other furniture cover most of the floor, so the outline shrinks to the visible strip. The ceiling is the 92nd percentile of point heights above the floor, floored at 2.2 m (`floor_footprint.py:103-104`). In a furnished room most points are walls and furniture below 2.2 m, so the percentile lands under that floor and 2.200 m is reported with a tight interval.

Evidence:
- **Bisect on the same capture.**
  - `52c7f46`, outline from wall points: walls 4.324 m and 5.528 m, ceiling 2.958 m, area 23.90 m².
  - `817bab7` and every later commit: walls 0.672 m and 2.771 m, ceiling 2.200 m, area 1.86 m².
  - `--drift off` gives the same failure.
- **The run warns** `sparse floor occupancy; bbox fallback`.
- **The ceiling equals the clamp value,** 2.200 m, exactly.

To reproduce, check out a commit and run `python -m pipeline.cli run --capture data/captures/lidar_B1_rep1 --out out/<commit>`.

## 3. Fix to ship

- **Outline:** build it from wall-band points, using a Manhattan box fitted to the wall planes, as `52c7f46` did. Keep floor occupancy only as a cross-check that adds a warning when the two disagree.
- **Ceiling:** take the highest horizontal plane that covers a large share of the outline (brief §5.5). Remove the 2.2 m floor and warn instead.

## 4. Predicted numbers after the fix

These predictions are based on `52c7f46` on the same capture.

| Measurement | Before | Predicted after (range) | Gate | Predicted verdict |
|---|---|---|---|---|
| Floor area | 1.86 m², −92.4 % | 23.9 m² (23.2–24.6), about −2 % | ±2 % | borderline; pass more likely than fail |
| Short walls | 2.771 m | 4.32 m (4.30–4.36) | ±2 cm | borderline |
| Long walls | 0.672 m | 5.53 m (5.48–5.60) | ±2 cm | still fails, by about 7 cm |
| Ceiling | 2.200 m | 2.96 m (2.94–2.99) | ±1.5 cm | likely fails, by about 2 cm |

In short: every number moves by metres to centimetres, the area gate probably passes, and the wall and ceiling gates probably stay just outside tolerance. The post-mortem will compare these predictions against tag `fixloop-after`.
