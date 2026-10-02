# Compliance matrix

**Source of truth for rows:** [docs/CASE_STUDY_CHECKLIST.md](../docs/CASE_STUDY_CHECKLIST.md)

| Requirement | File path | Artifact | Status |
|-------------|-----------|----------|--------|
| One command per capture | `pipeline/cli.py` | `housefloor run` | Phase 1 LiDAR |
| JSON schema output | `schemas/floorplan_output.schema.json` | `out/plan.json` | Partial |
| Rendered dimensioned plan | `pipeline/export/render_plan.py` | `out/floorplan.png` | Missing (not dimensioned yet) |
| LiDAR tier + raw sensors | `pipeline/tiers/lidar.py`, iOS logs | sensor_logs + JSON | Partial |
| Video tier ±3% gate | `pipeline/tiers/video.py` | plan + score | Partial |
| Photo tier whole-house ±8% | `pipeline/tiers/photos.py`, stitch | plan + score | Partial |
| Device matrix | `docs/DEVICE_MATRIX.md` | PDF/table | Missing |
| Stock capture protocol | `capture/STOCK_CAPTURE_PROTOCOL.md` | 1-page | Partial |
| TestFlight route | `ios/HouseFloorCapture/` | build + install doc | Missing |
| Benchmark composition B.1–B.6 | `benchmark/raw/` | raw + GT | Missing |
| Gates G.1–G.7 | `pipeline/benchmark/gates.py` | `gate_report.json` | Partial |
| Drift ablation | TBD `housefloor ablate-drift` | before/after footprint | Missing |
| Head-to-head | `benchmark/head_to_head/` | table + exports | Missing |
| Fix loop 25% | `benchmark/fix_loop/` | before/after/diff | Missing |
| Reproduction bundle | `scripts/reproduce_all` | regenerates all numbers | Missing |
| Benchmark report + timing | `benchmark/reports/` | REPORT.md | Missing |
| Technical report ≤6 pp | `docs/TECHNICAL_REPORT.md` | PDF | Missing |
| Model/API disclosure | `DISCLOSURE.md` | list | Missing |
| Mirrors/glass/low light | benchmark scenes + report | section in report | Missing |

Update **Status** to Done only when artifact exists and is reproducible.
