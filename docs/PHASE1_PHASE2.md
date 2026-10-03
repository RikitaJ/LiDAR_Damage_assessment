# Phase 1–2 status

## Phase 1–2 v0 — **executed** (2026-10-03)

| Check | Result |
|-------|--------|
| `pytest tests/` | **51 passed** (`MPLBACKEND=Agg`) |
| `python scripts/phase12_signoff.py` | **exit 0** → `docs/PHASE12_SIGNOFF_REPORT.json` |
| LiDAR fixture gates | All pass (footprint union fix for multi-room) |
| Stray mini capture | E2E plan + PNG |

## Phase 1 (LiDAR / stitch / plan)

| Item | Status |
|------|--------|
| Stray Scanner → room geometry | **Done** |
| RoomPlan JSON (column-major) | **Done** |
| Multi-room door stitch + footprint union | **Done** |
| `--tier auto`, Stray without manifest | **Done** |
| Dimensioned render (walls, doors, footprint title) | **Done** (v0) |

## Phase 2 (score / drift / eval)

| Item | Status |
|------|--------|
| `housefloor score`, `ablate-drift` | **Done** |
| `python -m eval.cli score` + manifest `capture_id` | **Done** |
| Cyclic wall gates | **Done** |
| Fixture GT | **Done** |
| Real capture GT (c00 tape) | **TODO** — do not guess numbers |

```powershell
$env:MPLBACKEND='Agg'
pytest tests/test_phase2_complete.py tests/test_phase12_e2e.py tests/test_stray_depth_geometry.py -q
python scripts/phase12_signoff.py
```
