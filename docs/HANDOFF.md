# Handoff between Builder and Tester

Open items and answers between the two of us. Agents: read this after `git pull` at the start of every session and before you push. Add to it; don't rewrite the other person's entries.

## Agreed

- B1 accuracy (benchmark report and the README table) comes from pipeline version `52c7f46`, the version validated on our tape-measured room. Regenerate with `python -m eval.run --rerun --ref 52c7f46 --skip-current --readme README.md`. Never hand-edit `docs/BENCHMARK_REPORT.md` or the README block between the `benchmark` markers.
- The company samples have no ground truth, so results on them are reported as consistency, not accuracy.

## Open for the Builder (from the Tester, 4 Oct)

1. **Clean installs crashed on real captures.** OpenCV 5.0 returns `HoughLinesP` as `(N, 4)`, so `pipeline/damage/heuristics.py:33` (`x1, y1, x2, y2 = line[0]`) raised `TypeError: cannot unpack non-iterable numpy.int32 object`, and every LiDAR and video run on B1 exited 1. Pinned `opencv-python-headless<5` in `843bbad`. Iterating `lines.reshape(-1, 4)` would make the code safe on both versions.
2. **Done overnight, with go-ahead: the fix loop, in your Stray geometry** (`91ad1c7`, tag `fixloop-after`; see `fixloop/POSTMORTEM.md`).
   - `stray_room.py`: the floor-occupancy outline is kept only if it contains 90 % of the camera path. Otherwise the outline is the wall-band box (your `_manhattan_corners`) from points within 1.5 m of the path. The ceiling is the cloud top above the floor with no clamp; if the scan never rose 0.6 m above the camera, it reports the 2.4–3.2 m prior with a wide interval and a warning.
   - `floor_footprint.py`: removed the unused, clamped `ceiling_height_from_planes`. `tiers/stray_room_v0.py` now passes the camera positions in.
   - B1 vs tape: walls 4.336 m and 5.561 m (4.35 and 5.60), ceiling 2.996 m (2.985), area 24.11 m² (24.36).
   - Your samples: `c00a170fe1` outline unchanged (23.0 m²). Ceilings are no longer pinned at 2.20 m: two are "not observed", and `c7d28f72c6` measures 2.975 m. The `1a8384c3f6` and `c7d28f72c6` outlines now contain their camera paths (127.8 and 230.9 m²); the second is inflated by room rotation (item 4).
3. **`fit_floor_plane` accepts planes of any orientation.** On B1 it returned a wall. The new outline and ceiling don't depend on it, but floor occupancy still does. Restricting it to horizontal planes changed `c00a170fe1`'s outline (23 to 12.7 m²), so it's your call.
4. **Room axes.** The single-room box is aligned to the capture's world axes, so a rotated room is overestimated. Two axis estimators failed on B1's clutter (see the post-mortem).
5. **Openings are now the weakest gate on B1:** 0 of 4 taped openings within 2 cm, and 6 phantom doors. The B1 render also draws a damage hatch outside the room outline (top left).
6. **Photo tier can't read iPhone HEIC EXIF** (`photo_exif: unreadable IMG_….HEIC`), so it falls back to a fixed prior room. It needs HEIC decoding.
7. **Photo folder layout.** Auto-detect expects `rooms/<room>/photos/`, but the capture protocol in the brief (§8) uses `photos_M/01_hallway/…`. One of them has to change before the walk-in.
8. **Video tier on a plain iPhone video** has no metric scale yet.
9. **`scripts/fetch_weights.py`** downloads MobileSAM without a sha256 check (brief rule 7).

## Answers

- *"Did you test my Phase 3 and Phase 4 tiers on B1? Is that the −92 % area?"* The −92 % came from the LiDAR (Stray) tier at the then-current code. On the B1 photos, the Phase 4 photo tier returns its fixed prior room, because the HEIC EXIF is unreadable. On the B1 video, the Phase 3 video tier has no metric scale. At `22af89c`, the LiDAR and video runs crashed under OpenCV 5 (item 1).
