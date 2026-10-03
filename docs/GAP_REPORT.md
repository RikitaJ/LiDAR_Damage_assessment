# Gap report: `main` @ `0c1c406` (3 Oct 2026)

Read-only audit (brief §11) on a scratch copy of HEAD, fresh venvs, Win 11, Py 3.12/3.14; nothing generated is committed. `.py` paths are under `pipeline/`; `lidar.py`, `stitch.py`, `gates.py` = `tiers/`, `stitch/`, `benchmark/`. "Probe" = one of 29 scripted edge cases (all reproduce; uncommitted). **(?)** = unsure.

## 1. Requirements (none done)

| ID | Files | Status | What's wrong |
|---|---|---|---|
| R1 | none | missing | No protocol; `docs/CASE_STUDY_CHECKLIST.md:12-14` still plans Route 1 (`ios/`, absent) |
| R2 | `lidar.py`, `run.py:17` | wrong | "LiDAR" = RoomPlan-style JSON, not depth/poses/intrinsics; no photo/video tier |
| R3, R30 | `docs/DEVICE_MATRIX.md` | partial | Template; no 13 Pro (A5) or iOS 18.6+ (Stray Scanner); protocol missing (R1) |
| R4 | `lidar.py` | wrong | Column-major transforms read row-major (`:88`): all walls start at the origin; area from min×max-length or bbox fallbacks (`:62`; 3×3 room → 36 m²); 2.5 m ceiling default (`:135`) |
| R5 | `stitch.py` | wrong | `_separate_overlapping` (`:172`) discards door alignment (probe: wrong side, doors 7.45 m apart); edge invented without doors (`:65`); width-only match links all rooms |
| R9 | `config.py:25-29` | wrong | σ = tier constant, no `lo/hi`; 2.5 m / 2.0 m / 0.01 m² defaults get the same tight σ |
| R10 | `io/session.py:28` | partial | Hand-written `manifest.json` required; no `--tier`; no stock capture accepted |
| R11 | `schemas/` | partial | Validated on write (keep); not schema v0: σ not `{value,lo,hi}`, no surfaces/offset/sill |
| R12 | `export/output.py:17` | wrong | Walls + lengths only; the sample renders as two "+" crosses |
| R18, R24 | `gates.py:33,241` | partial | Walls ±2 % (8.4 cm at 4.2 m) vs A1's ±2 cm; sorted matching passes swapped walls and hides missing ones (4 of 6 → 100 %) |
| R19 | `gates.py:167-191` | wrong | One phantom fails it (`:48`); inaccurate opening = miss + phantom; width-only match |
| R20, R21 | `gates.py:80-143` | partial | Skipped spread = pass (`:42,50`); bias from capture deltas, not GT; sorted-length matching; hash-seed order; tests compare a plan to itself |
| R22 | `benchmark/ablation.py` | wrong | Nudge overwritten (`stitch.py:172`): on = off = 85.26 m²; no GT or global poses ("as-is") |
| R28 | git log | partial | Phase 1–2 = one commit (`684d8cf`, 63 files); author `sshahi807` (work email) ≠ owner (A6) |
| R29 | `compliance/` | wrong | `COMPLIANCE_MATRIX.md` has no R-IDs; "Partial" rows cite nonexistent files (`:11,12,14`) |
| R31 | `README.md:11` | partial | Personal path; clean install OK (18 s); flaky tests (§3) |
| R33 | `benchmark/report.py` | partial | One capture's gate JSON; no tier, repeatability or h2h tables |
| R37 | `.env.example` | partial | No network calls; planned Azure OpenAI may count as our infrastructure (?) |
| R38 | commit `0c1c406` | wrong | 41.7 MB `rgb.mp4` pushed; no fetch scripts |
| R40, R41 | `*.zip` (ignored) | missing | No tier ingests a stock capture; all 3 company zips rejected (§3) |
| R6–8, 13–17, 23, 25–27, 32, 34–36, 39 | `run.py:50-52` | missing | Damage/flags/scope hard-coded `[]`; `benchmark/raw/` empty, sample = 2 synthetic rooms; no photo stitch, h2h, fix loop, repro bundle, reports or hard-surface handling |

## 2. Phase plan → build order (§9)

`docs/PHASES.md` runs depth-first (LiDAR/RoomPlan → gates → video → photo + Azure VLM → damage → benchmark) and blocks Phase 3 on real Apple JSON (`docs/PHASE1_PHASE2_COMPLETE.md:15`). §9 is breadth-first, and ~21 h remain.

- **Keep:** CLI skeleton, validate-on-write, input errors (`io/session.py`), overlap QA (`geometry/overlap.py`), `GateResult`, error-path tests.
- **Change P1 → M1–M2:** Stray Scanner → `CaptureFrames` → point geometry in one global frame, real `--drift on|off`; park RoomPlan/`import-apple` unless the h2h app exports RoomPlan JSON (?). **P2:** gates move to `eval/` (Tester) with R18–R24 fixes and GT from `data/ground_truth/*.yaml`.
- **Reorder:** photo (M3) before video (M4), since photo stitching is never-cut and riskiest.
- **Drop:** the Azure VLM (cold walk-in, rule 6, R37 (?)) for the §5.6 solver; the Apple-JSON gate (Route 2 never produces it).
- **Split P6:** tag `fixloop-before` ~midnight and commit the declaration first (§10).

## 3. What runs, what fails

- `pip install -e ".[dev]"` OK (18 s). `pytest tests -q`: 8 of 13 runs (3 Python builds) lose 1–2 random tests to `_tkinter.TclError: Can't find a usable tk.tcl` (or `init.tcl`); 20/20 with `MPLBACKEND=Agg`, as `export/output.py:6` renders via pyplot's GUI backend (CLI unaffected in 20 runs).
- `housefloor run --capture examples/benchmark_sample`: exit 0, 0.24 s; footprint 85.26 m² vs GT 17.4 (bbox fallback, `geometry/floor_polygon.py:18`). `score`: footprint gate fails (`"footprint_error_pct": 3.9`, a fraction = 390 %), rest pass; the suite stays green as no test checks footprint (`tests/test_phase2_complete.py:13-21`). `ablate-drift`: `"delta_m2": 0.0`.
- Company sample `run --capture "single_room sample data_given/c00a170fe1"`: exit 1 `FileNotFoundError: Missing …\c00a170fe1\manifest.json`; `import-apple`: exit 1 `FileNotFoundError: No RoomPlan JSON under …`; `--tier photos`: exit 2 `unrecognized arguments`.
- Bad input crashes (rule 5): unknown room in `adjacency` → `KeyError: 'ghost'`; no `tier` → `KeyError: 'tier'`; NaN dimension → `GEOSException: Edge direction cannot be determined because endpoints are equal`. Negative wall lengths pass silently.
- Company zips = Stray Scanner (depth 256×192 in mm, HEVC 1920×1440, per-frame intrinsics in `odometry.csv`, unlike §5.2); assumed A4 sample (?).

## 4. Red flags

- **Hard-coded/fabricated:** R9 defaults; 4 m offsets and a 0.55/0.45 push (`stitch.py:154,163,195`); 0.25 m door match (`io/adjacency_infer.py:30`); `"iPhone 15 Pro"` stamped on imports (`io/apple_import.py:46`); 85 %/1 mm/5 mm thresholds (`gates.py:52,121-123`); `drift_handling` describes a correction the code doesn't do (`run.py:53-58`).
- **Synthetic as real:** the images say "synthetic", but `examples/benchmark_sample/manifest.json:4` claims an iPhone 15 Pro and the GT copies the input, so the Phase 2 ticks are circular.
- **No intervals** on anything (no `lo/hi`; anchors, polylines, poses lack σ). **GT:** the run path never reads it, but gates live in `pipeline/benchmark/` and GT sits in capture folders (`benchmark/report.py:26`). **Private infra:** none.
- **Large files:** fix `rgb.mp4` (R38) with `git rm --cached` + a fetch script, not a history rewrite (rule 8); that commit lacks `depth/`/`confidence/` (unusable); the PDF is committed twice. The repo is private (anonymous GET → 404).
- **Non-determinism:** set order (`gates.py:88-93,134`), unsorted glob (`lidar.py:96-99`), timing and absolute paths in `plan.json` (`run.py:60-61`), unpinned deps.
- **Also:** `import-apple --out <existing dir>` deletes it recursively (`io/apple_import.py:14-15`); the calibration gate compares σ with itself (`gates.py:152-164`).

## 5. Top 10 tasks (thin path, all tiers; then damage/rules/scope, h2h, fix loop, R39)

| # | Task | Closes | Owner |
|---|---|---|---|
| 1 | Schema v0 (§5.7; JSON Schema + pydantic) + `CaptureFrames` | R9, R11 | Builder |
| 2 | Stray Scanner loader (verify StrayRobots `docs/format.md`) + single-room geometry v0 | R2, R4, R41 | Builder |
| 3 | `housefloor run <dir>`: auto tier, no manifest, warn not crash, Agg, render v0 | R10, R12, R40 | Builder |
| 4 | `data/manifest.csv` + `scripts/fetch_data.py` (sha256); untrack `rgb.mp4`; company outputs | R38, R41, R32 | Tester |
| 5 | `eval/` v0: YAML GT, cyclic walls, spec opening rule, cm tolerances, skipped ≠ pass; probes → tests | R18–22, R24, R33 | Tester |
| 6 | Pilot B1: LiDAR ×2, photos, video + tape GT (§7–8) | R13–17, R1 | Tester |
| 7 | Photo tier v0: EXIF K → cached multi-view model → polygons → layout solver (§5.6) | R2, R5, R15, R23 | Builder |
| 8 | Video tier v0: keyframes → SfM/feed-forward → `CaptureFrames` + scale σ | R2, R24 | Builder |
| 9 | Multi-room LiDAR: segmentation, plane-anchored `--drift on\|off`, ablation vs GT | R5, R22, R13 | Builder |
| 10 | `docs/COMPLIANCE_MATRIX.md`, `CAPTURE_PROTOCOL.md`, device matrix, README, `DECISIONS.md` | R29, R30, R1, R3, R31 | Tester |
