# Phase 3 — Video tier status

| Item | Status | Notes |
|------|--------|--------|
| Keyframes + optical-flow poses | **Done** | `pipeline/frontends/video.py` |
| Flow path + loop closure | **Done** | `apply_loop_closure_to_poses` before footprint |
| **Metric path (rgb + odometry)** | **Done** | Stray co-located exports |
| **Depth fusion on metric path** | **Done** | Same depth stack as Stray when ≥120 pts |
| Odometry scale on flow-only | **Done** | `align_video_room_to_odometry` |
| Shared stitch / render / JSON | **Done** | `--tier video` |
| Video drift ablation | **Done** | `video_drift_ablation()`, CLI `ablate-video-drift` |
| Sign-off | **Done** | `python scripts/phase3_signoff.py` |
| **COLMAP / metric SLAM** | **Deferred** | Optional per `docs/PHASES.md`; not required for offline sign-off |
| Video gates (±3%) vs GT | **When GT ready** | `python -m eval.cli score --tier video` |

## Phase 3 — **complete (offline scope, 2026-10-03)**

1. `pytest tests/` — **51 passed** (`MPLBACKEND=Agg`).
2. `python scripts/phase3_signoff.py` — **exit 0** → `docs/PHASE3_SIGNOFF_REPORT.json`.

```powershell
$env:MPLBACKEND='Agg'
pytest tests/test_video_tier.py tests/test_phase3_video.py -q
python scripts/phase3_signoff.py
```

**Not Phase 3:** Azure photo VLM, damage/rules (Phase 4–5).
