# Phase 1 sign-off (audit notes)

## In scope (Phase 1)

- LiDAR / RoomPlan JSON → per-room plan + multi-room stitch + JSON + PNG
- `housefloor import-apple` → `housefloor run`
- Offline, no Azure

## Verified (12 automated tests)

- Happy path sample (2 rooms + adjacency)
- Wall lengths from Apple dimensions (4.2 m, 3.5 m)
- Floor area ~14.7 m² living room (rectangle from wall lengths)
- Single-room capture
- Missing manifest / empty rooms / wrong tier → clear errors
- No walls / bad transform → clear errors
- import-apple + run
- Loop closure off
- 3-room stitch chain placement

## Known limits (not bugs for Phase 1; address in Phase 2+)

| Limit | Impact |
|-------|--------|
| Door position on wall = wall midpoint, not opening transform | Stitch offset on complex rooms until opening transforms parsed |
| Non-rectangular rooms (L-shape) | Area uses rect heuristic first; may need polygon trace |
| `import-apple` does not infer adjacency | Add doors in manifest or rely on auto door-width matching |
| Empty damage / scope arrays | Phase 5 |
| Photo / video tier | Phase 3–4 |
| Raw LiDAR binary logs | Future iOS export + ingest |
| Dimensioned PNG is wall lengths only | Doors/windows labels in Phase 2 render |

## Not claimed

Phase 1 does **not** pass challenge benchmark gates yet — that is Phase 2.
