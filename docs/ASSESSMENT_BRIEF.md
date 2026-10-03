# ASSESSMENT_BRIEF.md

Single source of truth for this repo, written for the two of us and for any coding agent (Claude Code, Cursor).
**Agents: read this whole file at the start of every session.**
The original spec is `docs/Applied_AI_Case_Study.pdf`. If this brief and the PDF ever disagree, the PDF wins.

- **Deadline:** Sunday 4 Oct 2026, 10:00 IST. Target submission 09:30.
- **Roles:** *Builder* = pipeline (`scanplan/`). *Tester* = capture, ground truth, evaluation, data tooling, docs (`eval/`, `data/`, `scripts/`, `docs/`).
- Shared contracts (`scanplan/schema/`) change only by agreement. If the existing repo uses other folder names, keep this split anyway.

---

## 0. Ground rules (every agent, every human)

1. **Never invent numbers.** Every number in any report, README or table is produced by a script from raw data listed in `data/manifest.csv`. Not measured yet → write `TODO`. Never present synthetic data as real.
2. **Every measurement carries an interval.** No bare numbers in output JSON.
3. **The pipeline never reads ground truth.** Nothing under `scanplan/` may import from `eval/` or read `data/ground_truth/`. Ground truth is for scoring only.
4. **No per-capture tuning.** Thresholds are global constants or derived from the input itself. The walk-in space is unseen; anything tuned to our rooms will fail there.
5. **Never crash on real-world input.** Thin or bad input still emits the full contract, with wide intervals and entries in `warnings[]`.
6. **Deterministic.** Fixed seeds, sorted file iteration, pinned versions. Model outputs cached in `.cache/` keyed by (model id, model version, input hash). `--replay` reproduces every reported number exactly; the live path must also run.
7. **No large binaries in git.** Weights and raw captures are fetched by `scripts/fetch_weights.py` and `scripts/fetch_data.py` with sha256 checks.
8. **Honest, granular history.** Small commits whose messages say what changed and why, under your real identity. Never squash, rewrite or force-push shared history. Part 5 of the spec reads it.
9. **Don't silently rewrite a teammate's area.** Propose (gap report, PR description), agree, then change.
10. **Log decisions.** Every non-obvious choice gets 2–4 lines in `docs/DECISIONS.md`: what, why, what was rejected. The candidate defends every decision live with tools closed; this file is the prep.

---

## 1. What we're building

A phone-based property inspection system. Someone walks through a home with an iPhone; **one command per capture** returns:

- a dimensioned plan per room (walls, ceiling height, floor area, openings),
- all rooms stitched into one whole-property plan with correct adjacency,
- damage regions on specific surfaces with class and real-world extent,
- concealed-damage flags with the rule that fired,
- repair scope line items keyed to surfaces,
- a calibrated confidence interval on every measurement,
- as JSON plus a rendered plan.

Three input tiers (photos, video, LiDAR) produce the **same contract**; only interval widths may differ. The domain reads like insurance/restoration claims estimating.

**Scoring weights (prioritise accordingly):** walk-in test 30% · fix-loop delta 25% · verified benchmark accuracy across all three tiers 15% · compliance-matrix coverage 10% · head-to-head vs a consumer app 10% · capture-route quality 5% · process evidence 5%.

---

## 2. Requirements checklist

IDs are reused in `docs/COMPLIANCE_MATRIX.md` (requirement → file path → artifact → status).

| ID | Requirement (from the PDF unless noted) |
|---|---|
| R1 | Capture route. We use **Route 2**: a one-page stock-capture protocol a non-engineer follows literally (what to install, how to walk, how long, what to avoid, how to hand files to the pipeline). |
| R2 | Three input tiers, all mandatory, same output contract. PHOTO: 2–8 stills per room, any iPhone 15+, no depth, no poses, one folder per room. VIDEO: handheld walkthrough clip, any iPhone 15+. LIDAR: depth + poses + intrinsics on Pro-class devices. |
| R3 | Device matrix: which tier runs on which hardware and what accuracy each honestly delivers. |
| R4 | Per-room dimensioned plan: walls, ceiling height, floor area, openings. |
| R5 | Stitched multi-room plan with correct adjacency, produced from every tier including photos. |
| R6 | Per-surface damage regions with class and metric extent. |
| R7 | Concealed-damage flags with the rule that fired. |
| R8 | Scope line items keyed to surfaces. |
| R9 | A confidence interval on every measurement. Calibration is scored at every tier; confident garbage on thin input caps the total score. |
| R10 | One command per capture. |
| R11 | JSON to the published schema (schema NOT provided, see A2). |
| R12 | Rendered plan. The stitched plan should look like what a homeowner would recognise from Polycam or magicplan: every room placed, connected, dimensioned. |
| R13 | Benchmark: one multi-room capture, three or more rooms plus a connector. |
| R14 | Benchmark: one furnished room with staged damage spanning two damage classes. |
| R15 | Benchmark: the same rooms at all three tiers, the multi-room set included. At the photo tier it arrives as per-room folders and must still stitch. |
| R16 | Benchmark: at least one room captured twice at the same tier (repeatability). |
| R17 | Laser or tape ground truth on everything; raw sensor data and measurements submitted. |
| R18 | Round 1 gates apply (NOT provided, see A1). |
| R19 | Gate: opening widths (section 3). |
| R20 | Gate: ceiling height (section 3). |
| R21 | Gate: repeatability (section 3). |
| R22 | Gate: drift accountability (section 3). |
| R23 | Gate: photo-tier whole-property stitch (section 3). |
| R24 | Looser tier gates: photo wall lengths ±8% with calibrated intervals; video ±3%. |
| R25 | Head-to-head: on 2 benchmark rooms, our LiDAR-tier output vs one consumer scanning app (name the app and version, submit its export). One table, our error and theirs, dimension by dimension. Beat or tie on ≥70% of shared dimensions. |
| R26 | One-page fix declaration: the single worst-performing gate in our benchmark with the failing number; root-cause hypothesis and evidence; the fix and the number we predict after it. |
| R27 | Ship the fix: before run and after run, both regenerable by them, plus a readable diff. |
| R28 | Process evidence: commit as you work; the history must plausibly belong to the people who built it. |
| R29 | Deliverable: compliance matrix. |
| R30 | Deliverable: capture route document plus device matrix. |
| R31 | Deliverable: repo with README; fresh capture → running in under 15 minutes on a clean machine; one command per capture. |
| R32 | Deliverable: reproduction bundle. Regenerate every reported number from raw inputs. Cached model outputs are acceptable only if the cache replays deterministically and the live path also runs. |
| R33 | Deliverable: benchmark report. Gates at all three tiers, repeatability table, head-to-head table, timing. |
| R34 | Deliverable: fix-loop bundle. |
| R35 | Deliverable: technical report, max 6 pages. Architecture, tier design and device matrix, drift handling, error budget, calibration analysis, fix-loop story, known failure modes. |
| R36 | Deliverable: raw benchmark data. Sensor logs, ground truth, app exports. |
| R37 | Constraint: handheld consumer capture only. Any pretrained model, dataset or API allowed with disclosure. Nothing calls our own infrastructure. |
| R38 | Constraint: weights and large binaries fetched by script or volume. |
| R39 | Constraint: real properties contain mirrors, glass, wet-look surfaces and low light; cover them in the submission. |
| R40 | Walk-in test: they capture an unseen space with their own iPhone 15+, choose the tier on the day, follow our protocol literally; the pipeline runs cold in front of them and is scored live against their laser. All three tiers must be ready. |
| R41 | From the recruiter's email (not the PDF): run our code on the company's sample data (Drive folder linked in the email) and include the outputs. |

---

## 3. Gates

| Metric | Gate | Applies to | Notes |
|---|---|---|---|
| Opening widths | abs error ≤ 2 cm on ≥ 85% of openings | LiDAR (assumed, A3) | Detection is scored: a missed opening and a phantom opening each count as a miss. |
| Ceiling height | abs error ≤ 1.5 cm per room; where a room is captured more than once, spread across captures ≤ 1 cm | LiDAR (assumed, A3) | Report must say whether we are repeatable-but-biased or unrepeatable. Both fail. |
| Repeatability | two captures of the same room at the same tier agree within 1 cm or 0.5% per wall | LiDAR (assumed, A3) | Self-consistency, not ground truth. Report against both thresholds. |
| Drift accountability | report states what we do about accumulated drift on the multi-room capture; ablation shows the stitched footprint with correction on and off | multi-room LiDAR (and video) | "Poses used as-is" is an automatic fail on this row. |
| Photo whole-property stitch | per-room folders → one stitched plan, correct adjacency, no room overlaps; footprint within ±8% with calibrated intervals | photo | A photo path that handles single rooms only fails this row. |
| Photo walls | ±8% with calibrated intervals | photo | |
| Video walls | ±3% | video | |
| LiDAR walls / floor area | Round 1 gate, not provided | LiDAR | Working assumption A1 until confirmed. |
| Calibration | nominal 90% intervals cover about 90% of ground truth | all tiers | Overconfidence on thin input caps the total score. |
| Head-to-head | beat or tie on ≥ 70% of shared dimensions | LiDAR vs app | Define "tie" up front and print it in the table (proposal: difference in abs error ≤ 3 mm, the precision of tape ground truth). |

---

## 4. Open questions and working assumptions

Record each as `ASSUMPTION A#` in the compliance matrix until answered by email.

- **A1** Round 1 gates not provided. Assume LiDAR walls ±2 cm and floor area ±2%, adjacency exact. Replace when confirmed.
- **A2** Published JSON schema not provided. We define schema v0 (section 5.7) and will map to theirs if they send it.
- **A3** The strict gates (openings, ceiling, repeatability) are assumed to be LiDAR-tier. Photo and video are still reported against them, honestly.
- **A4** The PDF says "we provide no captures", but the email links sample data. Download it, run the pipeline on it, include outputs (R41).
- **A5** Devices. LiDAR benchmark on iPhone 13 Pro (Pro-class, valid). Photo/video benchmark on a borrowed iPhone 15+ if available; otherwise on the iPhone 13 Pro, disclosed as a deviation in the device matrix (spec says 15+). The pipeline must not depend on device model: read intrinsics from EXIF/container metadata, and test decoding on original iPhone 15/16 HEIC photos and HEVC video.
- **A6** Two-person team confirmed verbally by the recruiter (get it in writing on the email thread). Real authors in git; contributions credited in the README.
- **A7** Interval convention: central 90% intervals `[lo, hi]`.
- **A8** Ground truth by tape measure (the spec allows laser or tape). Method in section 7.

---

## 5. Architecture: three front-ends, one back-end

```
photos/<room>/*.HEIC ─┐
walkthrough.MOV ──────┼─▶ tier front-end ──▶ CaptureFrames ──▶ geometry back-end ──▶ RoomModels
Stray Scanner dir ────┘   (poses, metric      (posed RGB +        (planes, polygons,       │
                           depth, scale σ)     metric depth + σ)    openings, intervals)    ▼
                                                     stitching: one global frame + drift correction
                                                     (LiDAR/video) or opening-matching layout solver (photos)
                                                                          ▼
                                    damage (detect → segment → project onto surfaces) → rules → scope
                                                                          ▼
                                                 JSON (schema v0) + rendered plans + timing log
```

A tier front-end's only job is producing `CaptureFrames`. Everything downstream is shared. This is the core design decision: the same contract from every tier holds by construction.

### 5.1 `CaptureFrames` (canonical intermediate)

Per frame: `image` (path), `K` (3×3, pixels, for that image's resolution), `T_world_cam` (4×4, metres), `depth` (H×W metres, or None), `depth_sigma` (H×W, or None), `timestamp`.
Per capture: `tier`, `device`, `gravity_aligned` (bool), `scale_sigma_rel` (relative 1σ scale uncertainty), `warnings[]`.
World frame: right-handed, metres, **+Z up**. Document the conversion from ARKit's +Y-up.

### 5.2 LiDAR front-end (Stray Scanner)

Expected layout. **Verify against `docs/format.md` in github.com/StrayRobots/scanner and the StrayVisualizer code before writing the loader; do not guess conventions.**
`rgb.mp4`, `depth/NNNNNN.png` (uint16 millimetres, low resolution, about 256×192), `confidence/NNNNNN.png` (0/1/2), `odometry.csv` (timestamp, frame, x, y, z, qx, qy, qz, qw), `camera_matrix.csv` (intrinsics for the RGB resolution; rescale for the depth resolution), `imu.csv`.
ARKit camera axes: x right, y up, camera looks down −z. Use only confidence = 2 depth for geometry. Poses come from visual-inertial odometry and are metric; `scale_sigma_rel` is small.

### 5.3 Video front-end

Decode with PyAV/ffmpeg (HEVC). Select keyframes (about 2 fps; drop blurry frames by Laplacian variance). Then either:

- **(a)** a feed-forward multi-view model in overlapping chunks chained by Sim(3) (candidates: MapAnything for metric output; VGGT plus metric alignment), or
- **(b)** COLMAP/pycolmap SfM for poses, plus a metric monocular depth model (candidates: Depth Pro, MoGe-2) for scale and dense depth. CPU-friendlier.

Metric scale = robust median of per-frame scale ratios; `scale_sigma_rel` from their spread (MAD or bootstrap). Loop closure: the protocol ends the walk at the start view. Choose (a) or (b) based on available GPU and CPU runtime; verify weights availability and licences; disclose; log the choice in DECISIONS.md.

### 5.4 Photo front-end

Per room folder: intrinsics from EXIF (focal length, 35 mm equivalent), then a feed-forward multi-view model on that room's 2–8 photos → poses and dense depth.
Metric scale from the model if it is metric, cross-checked against priors (door height about 2.0–2.1 m, handheld camera height about 1.3–1.6 m, ceiling 2.4–3.2 m). `scale_sigma_rel` from disagreement among cues, with a minimum set by calibration.
Rooms are not in a common frame: stitching is done by the layout solver (5.6). **Folder names may be used as room labels only, never to infer adjacency.**

### 5.5 Geometry back-end (per room)

1. Fuse points (voxel 1–2 cm); carry per-point σ when available.
2. Gravity alignment. LiDAR: given by ARKit. Others: dominant horizontal-plane normal or vanishing points.
3. Floor = lowest large horizontal plane. Ceiling = highest horizontal plane covering a large share of the room footprint. Ignore small horizontal patches: **ceiling fans, lofts above doors (horizontal slabs around 2.1 m), false-ceiling coves, rugs, furniture tops**. Report the main ceiling height; flag multi-level ceilings.
4. Walls: points with horizontal normals between floor + 0.3 m and ceiling − 0.3 m → top-down 2D → Manhattan axes → line fitting (sequential RANSAC or Hough) → polygon by intersecting consecutive wall lines. Regularise to Manhattan within tolerance.
5. Openings: gaps in wall support along each wall line. Doors and passages reach the floor; windows have a sill. LiDAR "see-through" points beyond the wall plane confirm a gap. Width, height, sill and offset with intervals; refine edges with RGB if time allows. Phantom guards: mirrors produce geometry behind a wall plane that duplicates the room; wardrobe fronts and TVs are not openings.
6. Measurements: wall lengths (corner to corner), ceiling height, floor area (polygon), opening width/height/sill/offset. Wall IDs W1..Wn clockwise seen from above.

### 5.6 Stitching

**LiDAR and video (one continuous capture):** everything is in one global frame.

- Room segmentation on the 2D map: free space from floor points and the camera trajectory, walls from wall points; doorways are narrow passages (distance transform + watershed, merge tiny regions), or segment by trajectory doorway crossings.
- **Drift correction is mandatory and switchable** (`--drift on|off`): (i) loop closure start = end via ICP plus pose-graph optimisation (Open3D), and/or (ii) plane-anchored correction: snap each room's walls to the global Manhattan axes and make shared walls between adjacent rooms parallel with consistent thickness.
- Ablation output: stitched footprint vs ground truth with correction off and on.

**Photos (per-room folders, no common frame): layout solver.**

- Inputs: per-room polygons and openings with σ.
- Hypothesise door pairings across rooms (widths and heights agree within intervals; the connector can pair with many rooms).
- Place rooms so paired doors coincide on opposite faces of a wall of thickness t (prior 0.10–0.25 m), rotations in 90° steps after Manhattan alignment.
- Score = door-alignment residual + overlap penalty (shapely) + compactness. Optional verification: feature matching between the doorway photos of the two rooms.
- Output adjacency and the stitched plan; footprint intervals honest (wide).
- Measured wall thicknesses in ground truth are for evaluation only, never a pipeline input.

### 5.7 Output JSON, schema v0 (sketch; formalise as JSON Schema + pydantic in `scanplan/schema/`)

Every `{value, lo, hi}` is a measurement with a 90% interval. Values below are placeholders, not data.

```json
{
  "schema_version": "0.1",
  "capture": {
    "id": "lidar_M", "tier": "lidar", "device": "iPhone 13 Pro",
    "pipeline_version": "<git sha>",
    "models": [{"name": "<model>", "version": "<v>", "licence": "<licence>"}],
    "timing_s": {"total": 0.0},
    "warnings": []
  },
  "units": "metres",
  "interval_level": 0.90,
  "rooms": [{
    "id": "R1", "label": "bedroom",
    "polygon": [[0.0, 0.0], [0.0, 0.0]],
    "ceiling_height": {"value": 0.0, "lo": 0.0, "hi": 0.0},
    "floor_area": {"value": 0.0, "lo": 0.0, "hi": 0.0},
    "walls": [{"id": "R1-W1", "start": [0.0, 0.0], "end": [0.0, 0.0],
               "length": {"value": 0.0, "lo": 0.0, "hi": 0.0}}],
    "openings": [{"id": "R1-O1", "wall_id": "R1-W1", "type": "door|window|passage",
                  "offset": {"value": 0.0, "lo": 0.0, "hi": 0.0},
                  "width": {"value": 0.0, "lo": 0.0, "hi": 0.0},
                  "height": {"value": 0.0, "lo": 0.0, "hi": 0.0},
                  "sill": {"value": 0.0, "lo": 0.0, "hi": 0.0},
                  "connects_to": "R2"}]
  }],
  "adjacency": [{"a": "R1", "b": "R2", "via": ["R1-O1", "R2-O3"]}],
  "stitched": {
    "footprint_area": {"value": 0.0, "lo": 0.0, "hi": 0.0},
    "extent_x": {"value": 0.0, "lo": 0.0, "hi": 0.0},
    "extent_y": {"value": 0.0, "lo": 0.0, "hi": 0.0},
    "overlaps": [],
    "drift_correction": "loop_closure+plane_anchor"
  },
  "surfaces": [{"id": "R1-W1", "type": "wall|floor|ceiling", "room": "R1",
                "net_area": {"value": 0.0, "lo": 0.0, "hi": 0.0}}],
  "damage": [{"id": "D1", "surface_id": "R1-W3", "class": "water_stain",
              "polygon_surface": [[0.0, 0.0]],
              "area": {"value": 0.0, "lo": 0.0, "hi": 0.0},
              "width": {"value": 0.0, "lo": 0.0, "hi": 0.0},
              "height": {"value": 0.0, "lo": 0.0, "hi": 0.0},
              "bottom_above_floor": {"value": 0.0, "lo": 0.0, "hi": 0.0},
              "score": 0.0}],
  "concealed_flags": [{"id": "F1", "rule_id": "CD-01", "rule": "<rule text>",
                       "triggered_by": ["D1"], "surfaces": ["R1-W3"], "rationale": "<why>"}],
  "scope": [{"id": "S1", "surface_id": "R1-W3", "code": "PAINT-WALL", "description": "<text>",
             "unit": "m2", "quantity": {"value": 0.0, "lo": 0.0, "hi": 0.0}, "because": ["D1", "F1"]}]
}
```

### 5.8 Damage, rules, scope

- **Detect and segment** damage in RGB: an open-vocabulary detector plus SAM-family masks, prompted per class. Our staged classes are `water_stain` and `crack`. Cache outputs.
- **Project** mask pixels through the camera onto the surface plane → polygon in surface coordinates (u along the wall from its start corner, v up from the floor) → area, width, height, position. Merge detections across frames by overlap on the surface. Interval from pose/plane σ plus mask-boundary jitter.
- **Concealed-damage rules** in `scanplan/rules/concealed.yaml`, evaluated deterministically. Seed rules:
  - CD-01: water stain on a wall with its bottom edge < 0.3 m above the floor → possible moisture wicking behind the wall finish.
  - CD-02: water stain on a ceiling → possible leak from above.
  - CD-03: water stain on a wall shared with a wet room (kitchen/bathroom, via adjacency and room label) → possible concealed plumbing leak. Fires only when labels are available.
  - CD-04: mold → hidden growth likely beyond the visible extent (add a 0.3 m margin).
  - CD-05: crack running diagonally from an opening corner → possible settlement; recommend structural inspection.
- **Scope** in `scanplan/rules/scope.yaml`: (damage class, surface type) → line items with quantity formulas from geometry. Examples: stain-block prime and repaint the whole wall (quantity = net wall area minus openings); patch (damage area plus margin); moisture inspection (1 per flagged surface). Quantities carry intervals.

### 5.9 Intervals and calibration

- Error budget per measurement type: scale, depth noise and bias, plane-fit residual, edge localisation, pose and drift. Combine (root sum of squares) → σ_raw.
- Calibrate per tier × measurement type: a multiplier k so that `value ± 1.645 · k · σ_raw` covers about 90% of ground truth, estimated leave-one-room-out on the benchmark. Store in `configs/calibration.json`, regenerated by the eval command.
- Minimum relative widths for thin tiers, set from calibration.
- Report coverage and mean interval width per tier, and label ceiling-height error as bias or variance.

### 5.10 Rendering

matplotlib or SVG. Per-room plan with wall dimension labels (value ± half-width), doors as arcs, windows as double lines, damage hatched, room labels. Stitched plan with adjacency. PNG + SVG.

### 5.11 CLI

- `scanplan run <capture_path> --out out/<capture_id> [--tier auto|photo|video|lidar] [--drift on|off] [--replay]` — one command per capture; auto-detect tier from the folder contents.
- `python -m eval.run --runs out/ --gt data/ground_truth/ --report docs/BENCHMARK_REPORT.md`
- `scanplan bench` — run every capture in `data/manifest.csv`, then eval.
- `fixloop/run.sh` — regenerate before and after (section 10).

### 5.12 Hard surfaces (R39)

- **Mirrors:** LiDAR and SfM see a reflected room behind the wall. Detect geometry behind a wall plane inside a framed region with no floor-level doorway evidence (or RGB mirror segmentation); exclude it from geometry; never report it as an opening; flag it.
- **Glass:** LiDAR returns little or passes through. Treat as window/opening evidence only with frame support; widen intervals.
- **Wet-look / glossy floors:** specular noise and holes in depth. Confidence filtering; fit the floor from wall–floor junctions if needed.
- **Low light:** noise, blur, tracking loss. Protocol says lights on; detect low exposure and blur; widen intervals and warn.
- All four go into "known failure modes" in the technical report, with what we observed.

---

## 6. Target repo layout

```
scanplan/             pipeline (Builder)
  frontends/          lidar.py, video.py, photo.py
  geometry/  stitching/  damage/  rules/  render/  schema/
eval/                 GT loader, matching, metrics, gates, calibration, report (Tester)
data/manifest.csv     capture list + URLs + sha256 (raw data NOT in git)
data/ground_truth/    tape measurements per room (YAML) + sketch photos
configs/              calibration.json, pinned model versions
scripts/              fetch_weights.py, fetch_data.py, clean_machine_check.sh
docs/                 Applied_AI_Case_Study.pdf, ASSESSMENT_BRIEF.md, GAP_REPORT.md, CAPTURE_PROTOCOL.md,
                      DEVICE_MATRIX.md, COMPLIANCE_MATRIX.md, BENCHMARK_REPORT.md, DECISIONS.md,
                      TECHNICAL_REPORT.md
fixloop/              DECLARATION.md, run.sh, before/, after/, diff.patch
```

---

## 7. Ground truth (tape): method and format

Method, identical for every room:

- **Sketch** each room. Walls in order: W1 = the wall containing the entry door; then go around the room clockwise as seen from above (standing in the doorway facing in, the next wall is the one on your left, then the far wall, and so on). Each wall starts at the corner it shares with the previous wall. Photograph the sketch; it goes into the raw data.
- **Wall length:** corner to corner at about 1.0 m height (above skirting and most furniture), tape level and taut, two readings. If blocked, measure at another clear height and note it.
- **Ceiling height:** at least 2 spots on bare floor (not a rug), floor to the main ceiling (not a loft or false-ceiling cove). Note which.
- **Openings:** clear width between the inside faces of the frame at about 1.0 m height; height to the underside of the head; window sill height; offset from the wall's start corner to the near frame.
- **Wall thickness:** jamb depth at every doorway between benchmark rooms.
- **Damage:** class, surface (room + wall or ceiling), bounding width × height, offset from the wall's start corner, height of the bottom edge above the floor.
- Metres, to the millimetre.

`data/ground_truth/<room_id>.yaml` — **format example only; every value below is a placeholder, not a measurement:**

```yaml
room_id: B1
label: bedroom
entry_door: O1
ceiling_heights_m: [0.000, 0.000]
ceiling_note: "main slab; loft over door excluded"
walls:                       # W1 = entry-door wall, then clockwise from above
  - {id: W1, length_m: [0.000, 0.000], measured_at_height_m: 1.0}
  - {id: W2, length_m: [0.000, 0.000]}
openings:
  - {id: O1, wall: W1, type: door,   offset_m: 0.000, width_m: 0.000, height_m: 0.000, connects_to: H}
  - {id: O2, wall: W3, type: window, offset_m: 0.000, width_m: 0.000, height_m: 0.000, sill_m: 0.000}
wall_thickness_at_openings_m: {O1: 0.000}
damage:
  - {id: DM1, class: water_stain, surface: W2, width_m: 0.000, height_m: 0.000, offset_m: 0.000, bottom_above_floor_m: 0.000}
  - {id: DM2, class: crack,       surface: W4, width_m: 0.000, height_m: 0.000, offset_m: 0.000, bottom_above_floor_m: 0.000}
notes: "fans off; rug in centre"
```

Matching (eval): predicted walls ↔ GT walls by cyclic alignment of the wall sequence anchored at the entry door, trying both directions; openings by wall + offset; damage by surface + bounding-box overlap.

---

## 8. Capture protocol (draft; becomes `docs/CAPTURE_PROTOCOL.md`, one page, after the pilot)

**Before any capture:** Stray Scanner installed (its App Store listing currently needs iOS 18.6+); at least 10 GB free; all interior doors fully open; curtains open; all lights on; **ceiling fans off**; personal items out of frame.

**LiDAR — Stray Scanner, Pro iPhone.** Set a modest frame rate in the record view so files stay small. One continuous recording. Start in the connector at a marked spot facing a fixed view. Walk slowly (about half normal pace), phone at chest height. In each room: go around about 1 m from the walls, sweep each wall floor to ceiling, show every corner and both sides of every doorway and window, look up at the ceiling once from the centre. Pass doorways slowly. Finish back at the start spot facing the same view for 3–5 s (loop closure). About 1 minute per room. Export through the share menu or Files.

**Video — native Camera, any iPhone 15+.** Video mode, 1×, 1080p 30 fps, landscape, Action mode off (if present). Same path and pace as LiDAR. Keep floor–wall and ceiling–wall junctions in view; pass doorways slowly; end at the start view. Hand off the **original file** (AirDrop, Files or Drive), never via WhatsApp (it recompresses and strips metadata).

**Photos — native Camera, Photo mode (not Portrait), any iPhone 15+.** One folder per room named `NN_roomname`. 4–8 photos per room, landscape, chest height: one from each corner aimed at the opposite corner so two walls plus the floor and ceiling edges are visible, plus one per doorway from inside the room showing the full frame and a bit of the next space. Lens (0.5× or 1×) decided in the pilot and recorded. Originals only (HEIC is fine).

**Hand-off:** zip each capture, upload it to the shared Drive folder, add a row to `data/manifest.csv`:
`capture_id, tier, device, ios_version, app_and_version, rooms, date_time, url, sha256, notes`.

**Our benchmark plan:**

- Multi-room set M = hallway (connector) + the three rooms that open off it. All three tiers.
- Damage room = bedroom B1 (inside M): a water stain low on one wall near the floor, and a crack running diagonally from a door or window corner.
- Repeat room = B1 at the LiDAR tier, two separate single-room recordings (the pilot is rep 1).
- Head-to-head rooms = B1 and B2, scanned with one consumer app (app name and version recorded, export saved).
- Ground truth for every room in M, plus damage items and wall thickness at each doorway.
- Capture IDs: `lidar_B1_rep1`, `lidar_B1_rep2`, `lidar_M`, `video_B1`, `video_M`, `photos_B1_1x/`, `photos_B1_05x/`, `photos_M/` (subfolders `01_hallway`, `02_B1`, ...), `app_<name>_B1`, `app_<name>_B2`.

---

## 9. Build order (time-boxed)

| Milestone | Target | Owner |
|---|---|---|
| M0 Gap report + contracts committed (schema v0, CaptureFrames, GT format) | first ~1 h | both |
| M1 LiDAR single room end-to-end on pilot data → JSON + render + eval vs GT | Sat afternoon | Builder; Tester for eval |
| M2 LiDAR multi-room: room segmentation, stitching, drift on/off ablation | Sat afternoon/evening | Builder |
| M3 Photo tier end-to-end including stitching (crude and wide is fine) | Sat evening | Builder |
| M4 Video tier end-to-end | Sat evening | Builder |
| M5 Damage + rules + scope on all tiers | Sat night | Builder |
| M6 Calibration + full benchmark + head-to-head → tag `fixloop-before` | ~midnight | Tester |
| M7 Fix declaration committed → fix → tag `fixloop-after` → regenerate | Sun ~04:00 | both |
| M8 Walk-in hardening (bad input, timing) + clean-machine install test | Sun early | both |
| M9 README, protocol, device matrix, compliance matrix, benchmark report, technical report (≤ 6 pages) | Sun 09:00 | Tester, Builder reviews |

**Breadth before depth:** every tier emits every field (even crude, with wide intervals) before any tier gets polished.

**Cut list if behind** (cut from the top first): mirror detection (document as a known failure) → RGB edge refinement of openings → cross-folder feature verification in photo stitching → loop closure in video (keep plane-anchored correction) → rendering polish.
**Never cut:** photo stitching, drift ablation, intervals and calibration, the fix loop, reproducibility, the compliance matrix.

---

## 10. Fix-loop procedure

1. Run the full benchmark. `git tag fixloop-before`.
2. Pick the single worst-performing gate (largest normalised miss). Write `fixloop/DECLARATION.md` (one page): gate and failing number; root-cause hypothesis and evidence (plots, ablations); the fix; the predicted number with a range. **Commit the declaration before writing any fix code**, so the history shows the prediction came first.
3. Implement a focused fix with a small, readable diff. `git tag fixloop-after`.
4. `fixloop/run.sh` checks out each tag (git worktree), runs the benchmark with `--replay`, and writes `fixloop/before/`, `fixloop/after/` and `fixloop/diff.patch`.
5. Post-mortem: did the gate pass? If not, why not? Was the prediction right? Scoring rewards an honest post-mortem even when the prediction misses; analysis without a shipped fix scores zero.

---

## 11. First agent session: audit (read-only)

Read this brief and the PDF; explore the entire repo (started by the Builder with Cursor, in phases). Do not modify existing files. Write `docs/GAP_REPORT.md`, max 2 pages:

1. Table: every requirement ID → existing file paths → status (done / partial / missing / wrong) → what's wrong.
2. How the Builder's phase plan maps onto section 9: what to keep, change or drop, and why.
3. Run existing entry points on whatever data exists; report what runs and the exact errors.
4. Red flags: hardcoded or fabricated numbers; synthetic data presented as real; outputs without intervals; the pipeline reading ground truth; network calls to private infrastructure; committed weights or large files; non-determinism.
5. Top 10 tasks in priority order to reach a thin end-to-end path through all three tiers, each with the requirement IDs it closes and an owner.

Cite file paths for every claim; say where you're unsure. Then stop for human review.

---

## 12. Submission checklist

- [ ] README quick start verified on a clean machine in under 15 minutes; one command per capture
- [ ] All three tiers run on our benchmark and on the company's sample data
- [ ] `BENCHMARK_REPORT.md`: gates × tiers, repeatability table, head-to-head table, timing — all generated by script
- [ ] `COMPLIANCE_MATRIX.md`: every R-ID with file path, artifact, status, assumptions
- [ ] `CAPTURE_PROTOCOL.md` (one page) + `DEVICE_MATRIX.md` (honest accuracy per tier and device, deviations disclosed)
- [ ] `fixloop/` bundle regenerable from tags
- [ ] `TECHNICAL_REPORT` ≤ 6 pages
- [ ] `data/manifest.csv` complete; raw data, ground truth and app exports downloadable by script
- [ ] `DECISIONS.md` current; README has a "Team & contributions" section
