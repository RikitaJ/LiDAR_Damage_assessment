# Fix-loop declaration (pre-fix)

**Gate:** `footprint_tier` (LiDAR / Stray)  
**Failing number (pending GT):** Cannot assert pass until `data/ground_truth/c00a170fe1.json` has measured `footprint_area_m2`. Pipeline v2 reports **~33 m²** (drift on) vs v1 **~78 m²** on the same capture — error vs truth **TODO**.

**Hypothesis:** Footprint was dominated by axis-aligned bbox on wall-band / walk path; occupancy grid without erosion included trajectory bleed.

**Fix shipped (2026-04-03):** Floor RANSAC + occupancy grid + 2× morphological erosion; pose loop closure before fusion; optional video scale to odometry span when `rgb.mp4` + `odometry.csv` coexist.

**Predicted after fix (to verify when GT filled):** Footprint error vs measured area moves toward **≤2%** (A1 LiDAR assumption); if still above, next step is alpha-shape on floor points and wall line RANSAC (not bbox).

**Evidence:** Compare `out_stray/plan.json` vs `out_stray_v2/plan.json` on `c00a170fe1`; ablation v2 Δ≈4.6 m² (drift now affects geometry).
