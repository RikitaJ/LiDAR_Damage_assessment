# Device matrix (template — fill with measured numbers after benchmark)

| Device | iOS | Tier: Photos | Tier: Video | Tier: LiDAR | Honest notes |
|--------|-----|--------------|-------------|-------------|--------------|
| iPhone 15 | 17+ | ✓ 2–8 stills/room | ✓ walkthrough | ✗ no LiDAR | Widest σ on openings/footprint |
| iPhone 15 Pro / Pro Max | 17+ | ✓ | ✓ | ✓ depth+poses | Primary accuracy target |
| iPhone 16 / 16 Pro | 17+ | ✓ | ✓ | ✓ (Pro only) | Update after walk-in rehearsal |

**Accuracy columns to fill after `benchmark/reports/` (not guesses):**

- Typical opening width error (cm, 85% band)  
- Ceiling height error (cm)  
- Footprint error (%) per tier  
- Repeatability max wall delta (cm)  

| Stray Scanner export (iPhone LiDAR app) | varies | ✗ | ✓ (same mp4) | ✓ depth+poses | Footprint **unverified** until `data/ground_truth/` filled; v2 run ~29–78 m² on sample scans (2026-04-03). |

Until Apple benchmark data exists, numeric error columns stay **TODO** — use `python -m eval.cli score` after GT is complete.
