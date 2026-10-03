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

## Video tier v0 (Phase 3, 2026-10-03)

**What:** `pipeline/frontends/video.py` keyframes + optical-flow poses → same `CaptureFrames` / stitch / render path as Stray; `--tier video` or video-only folder; optional Azure env hook (offline by default).

**Why:** Brief requires three tiers; video shares backend with Stray/LiDAR work. Azure keys from Quanta testing RG via `.env` only (never in git).

**Rejected:** Calling Azure on every frame in v0 (cost, latency, rule 6 cold walk-in must run offline).

## Stray footprint v2 + pose loop closure (2026-04-03)

**What:** RANSAC floor plane, occupancy-grid footprint (not wall-band AABB), voxel downsample, loop closure on odometry *before* depth fusion; video footprint from buffered camera path.

**Why:** Real scans showed ~78–231 m² single-room footprints and drift ablation Δ=0 m² because wall translation did not change area.

**Rejected:** Post-hoc `apply_stray_loop_to_rooms` wall nudge only (kept as no-op for compatibility).
