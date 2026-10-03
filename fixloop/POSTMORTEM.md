# Fix-loop post-mortem

**Declaration:** `fixloop/DECLARATION.md`, committed in `5747ffa` before any fix code. **Before:** tag `fixloop-before` (`2d3222e`). **After:** tag `fixloop-after` (`91ad1c7`). To regenerate everything below, run `bash fixloop/run.sh`. It writes `fixloop/REPORT.md`, `before/`, `after/` and `diff.patch`.

## Result on the declared gate: LiDAR walls / floor area (A1)

| B1 measurement (tape) | Before | After | Gate | After |
|---|---|---|---|---|
| Floor area (24.36 m²) | 1.86 m² (−92.4 %) | 24.11 m² (−1.0 %) | ±2 % | pass |
| Short walls (4.35 m) | 2.771 m | 4.336 m (−1.4 cm) | ±2 cm | pass |
| Long walls (5.60 m) | 0.672 m | 5.561 m (−3.9 cm) | ±2 cm | miss by 1.9 cm |
| Ceiling (2.985 m) | 2.200 m (−78.5 cm) | 2.996 m (+1.1 cm) | ±1.5 cm | pass |

Strict gates passing went from 0 of 6 to 4 of 6. The tape value lies inside the 90 % interval for 0 of 7 measurements before and 6 of 8 after.

## Prediction against result

| Measurement | Predicted (range) | Actual | In range? |
|---|---|---|---|
| Floor area | 23.9 m² (23.2–24.6) | 24.11 m² | yes |
| Short walls | 4.32 m (4.30–4.36) | 4.336 m | yes |
| Long walls | 5.53 m (5.48–5.60) | 5.561 m | yes |
| Ceiling | 2.96 m (2.94–2.99) | 2.996 m | no, 0.6 cm above |

Floor area passed, as predicted. The short walls passed and the long walls failed, both as predicted, though the long walls missed by 1.9 cm rather than the ~7 cm I predicted. The ceiling prediction was too pessimistic. I predicted a fail by ~2 cm; it passed. The prediction was based on `52c7f46`'s 2.958 m, but the fixed code measures the current point cloud after the hard-surface filter. The tape ceiling also gained a second reading after the declaration was written (2.98 m became a 2.985 m mean).

## Root cause: what the declaration got right and what it missed

- **Right:** an outline built from the visible floor collapses in a furnished room. The floor outline is now kept only when it contains at least 90 % of the camera path. On B1 it doesn't, so the outline comes from the wall-band box, built only from points within 1.5 m of the path.
- **Right:** the ceiling was a percentile clamped at 2.2 m. Before the fix it read exactly 2.200 m on B1 and on all three company samples.
- **Missed:** `fit_floor_plane` accepts a plane of any orientation. On B1 a wall has more points than the partly hidden floor, so the fit returned a wall. The camera path sat at the height of the "floor" instead of about 1.4 m above it. That turned the floor slice into a strip and pushed the ceiling below the clamp. The outline and ceiling no longer depend on that fit. The fit itself is unchanged, because constraining it to horizontal planes altered the company `single_room` outline, and that needs the Builder's review.

## Side effects on the company samples (no ground truth)

To reproduce: `housefloor run --capture data/captures/<id>` before and after.
- **`c00a170fe1` (single_room):** outline unchanged at 23.0 m². The ceiling was never observed, so it is now reported as the 2.4–3.2 m prior with a wide interval instead of a clamped 2.20 m.
- **`1a8384c3f6` (floor_only):** the ceiling was never observed, so it uses the prior. The outline now contains the camera path (127.8 m²).
- **`c7d28f72c6` (with_ceiling):** the ceiling is measured at 2.975 m instead of a clamped 2.20 m. The outline (230.9 m²) is inflated. The box is aligned to the capture's world axes, and this room is rotated relative to them.

## Still open

- **Long walls:** 3.9 cm short. Not diagnosed yet. Candidate causes are that the box edge follows the outermost wall points rather than the wall-plane centre, and depth noise at grazing angles.
- **Room axes:** a room rotated relative to the capture's start heading is overestimated. Two room-axis estimators were tried (histogram sharpness and edge support), and both failed on B1's clutter. Meanwhile the capture protocol should say to start the scan facing a wall squarely.
- **Openings:** the weakest gate now. 0 of 4 taped openings are within 2 cm, and there are 6 phantom openings. This is the next fix-loop candidate.
