# Phase 3 — Video tier status



| Item | Status | Notes |

|------|--------|--------|

| Keyframes + optical-flow poses | **Done** | `pipeline/frontends/video.py` (fallback when no odometry) |

| **Metric path (rgb + odometry)** | **Done** | `video_room_v0.py` — Stray co-located exports |

| Shared stitch / render / JSON contract | **Done** | `--tier video` |

| Drift on odometry before footprint | **Done** | `stray_poses.apply_loop_closure_to_poses` |

| Video drift ablation | **Done** | `video_drift_ablation()` in `benchmark/ablation.py` |

| Sign-off script | **Done** | `python scripts/phase3_signoff.py` → `docs/PHASE3_SIGNOFF_REPORT.json` |

| **COLMAP / metric SLAM** | **Not built** | Optional per `docs/PHASES.md` |

| Video gates (±3% walls) vs GT | **After GT** | `python -m eval.cli score --tier video` |



## Phase 3 v0 — **executed** (2026-10-03)

1. `pytest tests/` — **45 passed** (includes `test_video_tier.py`, `test_phase3_video.py` on local `rgb.mp4` samples).
2. `python scripts/phase3_signoff.py` — **exit 0**; see `docs/PHASE3_SIGNOFF_REPORT.json` (all three captures `ok`, `video_odometry_metric`).



```powershell

$env:MPLBACKEND='Agg'

pytest tests/test_video_tier.py tests/test_phase3_video.py -q

python scripts/phase3_signoff.py

```



**Not Phase 3:** Azure photo VLM, damage/rules (Phase 4–5), multi-room Stray manifest docs only.


