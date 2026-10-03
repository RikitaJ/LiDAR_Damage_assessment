# Phase 3 — Video tier status

| Item | Status | Notes |
|------|--------|--------|
| Keyframes + optical-flow poses | **Done** | `pipeline/frontends/video.py` |
| Shared stitch / render / JSON contract | **Done** | `--tier video` |
| Relaxed blur fallback + flow scale | **Done** | real `rgb.mp4` runs |
| Scale to odometry when co-located | **Done** | `video_scale.py` |
| Drift ablation on video | **Partial** | `video_drift.py` nudge only |
| **COLMAP / metric SLAM** | **Not built** | Listed in `docs/PHASES.md`; cut only if schedule forces |
| Video gates (±3% walls) vs GT | **Blocked** | Needs `data/ground_truth/*.json` complete |

## Test Phase 3 locally

```powershell
$env:MPLBACKEND='Agg'; pytest tests/test_video_tier.py tests/test_phase3_video.py -q
housefloor run --capture single_room\c00a170fe1 --tier video --out single_room\c00a170fe1\out_video_v3
```

**Phase 3 fully executed (offline scope):**

| When | What |
|------|------|
| **Now** | `scripts/run_phase3_all.ps1` or `pytest tests/test_phase3_video.py` — video on all three sample `rgb.mp4` folders |
| **After GT** | `python -m eval.cli score --tier video` when `data/ground_truth/*.json` is complete (±3% wall gate) |
| **Later (optional)** | COLMAP / metric SLAM in `docs/PHASES.md` — not required for “v0 Phase 3 done” |

**Not Phase 3:** Azure photo VLM, damage/rules, multi-room Stray manifest, `eval/calibrate.py` → Phases **4–5 + Tester eval** (see `docs/PHASES.md`).
