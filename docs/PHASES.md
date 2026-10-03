# Build phases

| Phase | Scope | Azure? |
|-------|--------|--------|
| **1** | LiDAR ingest, stitch, JSON + dimensioned PNG, `import-apple` | **No** |
| **1b** | Opening anchors, orphan QA, overlap check | **No** |
| **2 (now)** | `score`, `score-repeat`, `ablate-drift` | No |
| 3 | Video tier + COLMAP | No |
| **4** | Photo tier, layout solver §5.6, optional VLM | **Optional Azure OpenAI** |
| **5 (now)** | Surfaces, detect, concealed rules, scope, plan hatch | Optional Azure Vision |
| 6 | Benchmark bundle, head-to-head, fix loop, reports | No |

Phase 1 runs **fully offline** with no API keys.
