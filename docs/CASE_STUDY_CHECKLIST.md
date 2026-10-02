# Case study checklist (nothing missing)

Use this as the **master requirements list**. Each row must end at **Done** before submission.  
Legend: **Plan** = in our build plan | **Partial** = started in repo | **Missing** = not built yet

---

## Part 1 — Capture (you own from phone sensors)

| # | Requirement | Plan | Build status | Where it will live |
|---|-------------|------|--------------|-------------------|
| 1.1 | **Route 1** OR **Route 2** (both OK) | ✓ | Partial | `ios/` + `capture/STOCK_CAPTURE_PROTOCOL.md` |
| 1.2 | Route 1: own app — ARKit, RoomPlan, **LiDAR depth, camera, IMU**, SDK data | ✓ | Partial | iOS app + optional raw log export |
| 1.3 | Route 1: **TestFlight or dev build**, install in **&lt;10 min** on their device | ✓ | Missing | TestFlight doc + install video |
| 1.4 | Route 2: **one-page** stock protocol (install, walk, duration, avoid, handoff) — **non-engineer** | ✓ | Partial | Polish to literal defense script |
| 1.5 | **Tier 1 Photos**: 2–8 stills/room, **iPhone 15+**, no depth/poses, **per-room folders** | ✓ | Partial | `rooms/*/photos/` |
| 1.6 | Photo tier → **same whole-property stitched plan** as other tiers (widened intervals) | ✓ | Partial | `pipeline/stitch/` + photo tier |
| 1.7 | **Tier 2 Video**: handheld walkthrough, iPhone 15+ | ✓ | Partial | `rooms/*/video/` |
| 1.8 | **Tier 3 LiDAR**: depth, **poses, intrinsics**, Pro-class devices | ✓ | Partial | Raw logs + RoomPlan JSON, not JSON-only |
| 1.9 | **Device matrix**: tier × hardware × **honest accuracy** | ✓ | Missing | `docs/DEVICE_MATRIX.md` |

---

## Part 2 — Output contract (every capture, every tier)

| # | Requirement | Plan | Build status | Where it will live |
|---|-------------|------|--------------|-------------------|
| 2.1 | Per-room: **walls**, **ceiling height**, **floor area**, **openings** (dimensioned) | ✓ | Partial | `plan.json` rooms[] |
| 2.2 | **Stitched** multi-room plan, **correct adjacency** | ✓ | Partial | `stitched_plan.adjacency` |
| 2.3 | **Damage** per surface: **class** + **metric extent** | ✓ | Partial | `damage_regions[]` |
| 2.4 | **Concealed damage** flags + **rule that fired** | ✓ | Partial | `concealed_damage_flags[]` |
| 2.5 | **Scope line items** keyed to surfaces | ✓ | Partial | `scope_line_items[]` |
| 2.6 | **Confidence interval on every measurement** | ✓ | Partial | σ on each value |
| 2.7 | **One command** per capture | ✓ | Partial | `housefloor run` |
| 2.8 | **JSON** matching **published schema** | ✓ | Partial | Align with employer schema if provided |
| 2.9 | **Rendered plan** — homeowner recognizes it (poly.cam / magicplan style), **dimensioned**, all rooms connected | ✓ | Missing | Upgrade `render_plan.py` + labels |
| 2.10 | Same contract from **photos**, **video**, **LiDAR** | ✓ | Partial | Tier routers |

---

## Part 2 — Benchmark set (you build; composition fixed)

| # | Requirement | Plan | Build status | Where it will live |
|---|-------------|------|--------------|-------------------|
| B.1 | **≥3 rooms + connector** (e.g. hallway) one capture | ✓ | Missing | `benchmark/raw/multi_room/` |
| B.2 | **Furnished room**, **staged damage**, **≥2 damage classes** | ✓ | Missing | Benchmark + photos |
| B.3 | **Same rooms**, **all 3 tiers** (photo = per-room folders, **includes multi-room stitch**) | ✓ | Missing | Same session, three tier runs |
| B.4 | **≥1 room captured twice** at **same tier** (repeatability) | ✓ | Missing | e.g. `living_room_scan_a`, `_scan_b` |
| B.5 | **Laser/tape ground truth** on everything | ✓ | Partial | `ground_truth.json` per session |
| B.6 | Submit **raw sensor data** + measurements | ✓ | Missing | `benchmark/raw/.../sensor_logs/` |

---

## Part 2 — Gates (pass/fail)

| # | Gate | Plan | Build status | Tooling to add |
|---|------|------|--------------|----------------|
| G.1 | Openings ≤**2 cm** on ≥**85%**; **missed + phantom** openings = miss | ✓ | Partial | Opening matcher + phantom detector in `score` |
| G.2 | Ceiling ≤**1.5 cm**/room; multi-capture spread ≤**1 cm**; report **biased vs unrepeatable** | ✓ | Missing | Extended `gates.py` + report section |
| G.3 | **Repeatability**: 2 captures, same tier, walls within **1 cm or 0.5%** | ✓ | Missing | `housefloor score --repeatability` |
| G.4 | **Drift**: document loop closure / pose graph / plane correction + **ablation footprint on/off** | ✓ | Partial | `housefloor ablate-drift`; report figures |
| G.5 | **Photo whole-property stitch**: adjacency OK, **no overlaps**, footprint ±**8%** + calibrated intervals | ✓ | Partial | Overlap check + photo footprint gate |
| G.6 | Photo walls ±**8%**, video ±**3%** (with calibration scored) | ✓ | Missing | Tier-specific wall gate |
| G.7 | **No confident garbage** on thin input (calibration caps score) | ✓ | Partial | Input quality → inflate σ |

---

## Part 3 — Head-to-head

| # | Requirement | Plan | Build status | Where |
|---|-------------|------|--------------|-------|
| 3.1 | **2 benchmark rooms**, **your LiDAR** vs **one consumer app** (name + **version**) | ✓ | Missing | `benchmark/head_to_head/` |
| 3.2 | Submit **their export** + table **dimension vs dimension** | ✓ | Missing | CSV/Markdown report |
| 3.3 | **Beat or tie ≥70%** of shared dimensions | ✓ | Missing | Scoring script |

---

## Part 4 — Fix loop (25% of score)

| # | Requirement | Plan | Build status | Where |
|---|-------------|------|--------------|-------|
| 4.1 | **One-page declaration**: worst gate + **failing number** | ✓ | Missing | `benchmark/fix_loop/DECLARATION.md` |
| 4.2 | Root cause + **evidence** | ✓ | Missing | Same + logs/plots |
| 4.3 | Fix + **predicted number after** | ✓ | Missing | Same |
| 4.4 | **Ship fix** in code | ✓ | Missing | PR / commit |
| 4.5 | **Before** + **after** runs, **regenerable** by reviewer | ✓ | Missing | `fix_loop/before/`, `after/` + scripts |
| 4.6 | **Readable diff** of outputs | ✓ | Missing | `fix_loop/diff.md` or script |

---

## Part 5 — Process

| # | Requirement | Plan | Build status | Where |
|---|-------------|------|--------------|-------|
| 5.1 | **Commit as you work** — believable git history | ✓ | Ongoing | Git discipline |
| 5.2 | Defense: explain decisions **live**, **tools closed** | ✓ | Prep | Cheat sheet / architecture one-pager |

---

## Deliverables (submission bundle)

| # | Deliverable | Plan | Build status |
|---|-------------|------|--------------|
| D.1 | **Compliance matrix** (req → path → artifact → status) | ✓ | Missing file — use this doc + `compliance/COMPLIANCE_MATRIX.md` |
| D.2 | Capture route + **device matrix** | ✓ | Partial |
| D.3 | Repo + README: **&lt;15 min** clean machine, **one command** | ✓ | Partial |
| D.4 | **Reproduction bundle**: regenerate **every reported number** from raw; cache OK if deterministic + **live path works** | ✓ | Missing | `scripts/reproduce_all.sh` |
| D.5 | **Benchmark report**: all tiers, **repeatability**, head-to-head, **timing** | ✓ | Missing | `benchmark/reports/` |
| D.6 | **Fix loop bundle** | ✓ | Missing |
| D.7 | **Technical report ≤6 pages** (architecture, tiers, drift, error budget, calibration, fix story, failure modes) | ✓ | Missing |
| D.8 | **Raw benchmark data** (sensor logs, GT, app exports) | ✓ | Missing |

---

## Walk-in test (30% — defense day)

| # | Requirement | Plan | Build status |
|---|-------------|------|--------------|
| W.1 | **Unknown** space, **their** iPhone 15+, **their tier choice** | ✓ | All tiers must run cold |
| W.2 | They follow **your capture route literally** | ✓ | Protocol must be crystal clear |
| W.3 | **Live run** in front of them | ✓ | No cloud dependency |
| W.4 | They **laser** the room while it runs; score vs output | ✓ | Same gate logic as benchmark |

---

## Scoring weights (don’t optimize the wrong thing)

| Weight | What | Must not fail |
|--------|------|----------------|
| **30%** | Walk-in cold + laser | Author-only overfitting |
| **25%** | Fix loop | Analysis without code |
| **15%** | Benchmark all 3 tiers | Non-reproducible numbers |
| **10%** | Compliance matrix | Wrong product shape |
| **10%** | vs MagicPlan/Poly.cam | Skipping comparison |
| **5%** | Capture route UX | Engineer-only capture |
| **5%** | Git history | One-commit repo |

---

## Constraints (easy to forget)

| # | Constraint | Plan | Notes |
|---|------------|------|-------|
| C.1 | **Handheld consumer** only | ✓ | No rigs |
| C.2 | Pretrained / API **disclosed** | ✓ | Add `DISCLOSURE.md` |
| C.3 | **No your infrastructure** at run time | ✓ | Offline pipeline |
| C.4 | Weights/binaries via **script or volume** | ✓ | `download_models.py` |
| C.5 | **Mirrors, glass, wet floors, low light** covered in submission | ✓ | Benchmark scenes + report section |

---

## What we added to the plan (was under-specified before)

1. **Raw LiDAR + IMU + intrinsics logging** (not only RoomPlan JSON).  
2. **Dimensioned** render (magicplan-style), not line sketch only.  
3. **Phantom opening** penalty in metric gate.  
4. **Ceiling spread across repeat captures** + **biased vs unrepeatable** narrative.  
5. **Repeatability gate** as its own CLI/report.  
6. **Drift ablation** script (footprint loop on/off).  
7. **Photo overlap detection** for whole-property stitch gate.  
8. **Video ±3% wall gate** separate from photo ±8%.  
9. **Calibration scoring** / anti–confident-garbage on thin input.  
10. **Reproduction bundle** + timing in benchmark report.  
11. **DISCLOSURE.md** for models/APIs.  
12. **DEVICE_MATRIX.md** as required deliverable.  
13. **Benchmark composition B.1–B.6** as explicit build milestone before claiming gates.  
14. **Employer published JSON schema** — merge if they ship a different schema file.

---

## Simple kid version

We must: **(1)** get pictures/scans from a phone the right way, **(2)** draw the **whole house map** every time, **(3)** measure and say how sure we are, **(4)** find damage, **(5)** practice on a **hard homework set** we made ourselves, **(6)** beat another app on two rooms, **(7)** fix our **biggest mistake** and show before/after, **(8)** hand in folders so anyone can **rerun** our homework, **(9)** pass a **surprise house** test with a laser. This checklist is every page of their rulebook turned into a to-do list.
