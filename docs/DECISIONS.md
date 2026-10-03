# Decisions log

## Stray Scanner as LiDAR front-end (2026-10-03)

**What:** Added `CaptureFrames`, Stray folder detection, and a v0 room estimate from camera path when `depth/` is missing.

**Why:** The case study brief and gap report require company sample data (R41) and real depth/poses, not RoomPlan JSON alone.

**Rejected:** Rewriting the whole pipeline to `scanplan/` in one step; RoomPlan remains for the synthetic benchmark sample.

## Depth fusion v0 (2026-10-03)

**What:** When `depth/` PNGs exist, fuse high-confidence points into a floor box and ceiling height; otherwise keep camera-path box with wide uncertainty.

**Why:** Matches brief §5.2–5.5 and closes the path to R41 once full company captures are fetched.

**Rejected:** Full RANSAC wall fitting in this step (next iteration after pilot data).

## Stray depth geometry v1 + intervals (2026-10-03)

**What:** Fused confidence=2 depth into point clouds; Manhattan wall box + gap-based openings; all Stray measurements include `value`/`lo`/`hi`; `scripts/fetch_data.py` + `data/manifest.csv` for company capture.

**Why:** Steps 1–3 and 6 on the Stray completion checklist before render polish (4–5) and multi-room (8).

## Render, R39 filters, drift (2026-10-03)

**What:** Rich PNG (doors/windows/interval labels); hard-surface point filters + warnings; `--drift on|off`; Stray loop nudge + stitch overlap nudges; multi-room Stray via manifest `capture_format: stray` + segment index.

**Why:** Checklist items 4–5 and 8 for submission path; ablation must change footprint when drift toggles.

## Phase 1–2 stitch + gates (2026-10-03)

Multi-room placement shifts the child room along the door-wall inward normal (centroid projection) so footprints are not stacked on the same door point; overlap resolution re-locks doors instead of centroid nudges. Wall gates use cyclic rotation matching (not sorted lengths) per brief §5.9. Stitched footprint uses **union of room world bboxes** (`stitched_footprint_area_m2`) so multi-room plans are not scored as the largest single polygon only.

## Photo tier v0 (Phase 4, 2026-10-03)

Per-room folders → offline rectangle prior; optional Azure GPT-4o vision when `.env` keys present (cached under `.cache/photo_vlm`). Multi-room stitch uses **§5.6 layout solver** (`photo_layout`: door width pairing, 90° rotations, overlap penalty) when manifest adjacency is empty; otherwise manifest edges drive placement. Scale σ widens intervals from still count + VLM use. **Rejected:** folder names as adjacency hints; LiDAR `_place_by_doors` alone for photos (stacked footprints).

## Photo tier completion (Phase 4 v1, 2026-10-03)

**What:** Auto session from `rooms/*/photos/`; OpenCV sparse MVS scale cue; combined scale σ; Manhattan L-shapes; VLM `openings[]` (doors/windows); hub-style multi-edge adjacency inference; ORB doorway verification warnings; up to 8 stills to VLM.

**Why:** Close brief §5.4–5.6 gaps without shipping large MVS weights; keep cold walk-in offline-capable.

**Rejected:** Downloading multi-GB MapAnything/VGGT weights inside this repo (document as future hook); using folder names for adjacency.

## Photo accuracy pass (Phase 4 v2, 2026-10-03)

**What:** Door/ceiling prior metric rescale on VLM JSON; rectangle consistency (opposite walls + area); implausible VLM reject; two-batch median VLM when ≥6 stills; Hough aspect hint for offline/VLM refine; σ widened when metric cues disagree.

**Why:** Move photo wall/footprint toward ±8% without dense MVS weights.

**Rejected:** Ceiling-as-horizontal-scale (would distort walls); third VLM batch (cost/latency).

## Video tier completion (Phase 3, 2026-10-03)

Metric `--tier video` on Stray folders uses odometry loop closure, then **depth fusion** when enough points (same as LiDAR Stray), else path-buffer footprint. Flow-only clips get loop closure + optional odometry scale. COLMAP deferred (optional phase scope).

## Video tier v0 (Phase 3, 2026-10-03)

**What:** `pipeline/frontends/video.py` keyframes + optical-flow poses → same `CaptureFrames` / stitch / render path as Stray; `--tier video` or video-only folder; optional Azure env hook (offline by default).

**Why:** Brief requires three tiers; video shares backend with Stray/LiDAR work. Azure keys from Quanta testing RG via `.env` only (never in git).

**Rejected:** Calling Azure on every frame in v0 (cost, latency, rule 6 cold walk-in must run offline).

## Stray footprint v2 + pose loop closure (2026-04-03)

**What:** RANSAC floor plane, occupancy-grid footprint (not wall-band AABB), voxel downsample, loop closure on odometry *before* depth fusion; video footprint from buffered camera path.

**Why:** Real scans showed ~78–231 m² single-room footprints and drift ablation Δ=0 m² because wall translation did not change area.

**Rejected:** Post-hoc `apply_stray_loop_to_rooms` wall nudge only (kept as no-op for compatibility).

## Phase 5 damage v1 (2026-04-03)

**What:** `pipeline/damage/phase5.py` — net surfaces, RGB heuristics + optional Vision tags, JSON rules (`configs/concealed_rules.json`, `configs/scope_rules.json`), scope quantities with intervals; damage hatch on `floorplan.png`.

**Why:** Brief R6–R8 require surface-keyed damage, rule IDs, and scope without reading GT; offline walk-in must still emit full contract.

**Rejected:** Full SAM/detector stack in v1 (weights, latency); kept as heuristic + optional Azure with wide intervals until benchmark cache exists.

**Limitations:** `pipeline_meta.limitations[]` lists static v1 gaps plus per-run flags (no RGB, photo tier poses, R39); heuristic damage intervals widened in code so thin input stays honest (rules 5 and 9).

## Phase 5 damage v2 accuracy (2026-04-03)

**What:** `.cache/damage/` per-image hits; `project.py` room-aware walls, UV from image fractions, IoU merge, Vision fuse, CD-05 from door/window anchors; optional Hough crack cue.

**Why:** Brief §5.8 expects cache + surface-keyed regions; v1 default-wall placement was too weak for scoring and concealed rules.

**Rejected:** SAM weights in-repo for this deadline; 3D projection without poses.

## Phase 5 damage v3 accuracy (2026-04-03)

**What:** Heuristic v2 (mask bbox, ceiling ROI, image-x wall index); optional `azure_damage_vlm` structured cues; 3 video frames; `refine_region_confidence` tightens σ on high-score VLM hits.

**Why:** Better surface placement and extent without SAM; reuse Azure OpenAI keys already used for photo layout.

**Rejected:** Full mask projection pipeline until per-frame poses exist at photo tier.

## Phase 4 photo accuracy v2 (2026-04-03)

**What:** Apply sparse MVS span scale to room geometry (fuse with VLM via median); door height in layout pairing; ORB-filter inferred edges before stitch; camera-height metric cue; EXIF missing-focal widens σ.

**Why:** Brief §5.4–5.6: metric scale from multi-view + priors, not VLM alone; stitch disambiguation beyond door width.

**Rejected:** Dense MapAnything front-end in-repo; hard-dropping manifest adjacency on weak ORB (manifest still trusted).
