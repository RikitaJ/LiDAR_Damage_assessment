# Phase 1 + 2 completion criteria

We move to **Phase 3** only when every box below is **Done** on sample **and** on at least one **real Apple import** (when available).

## Phase 1 (LiDAR pipeline)

- [x] RoomPlan JSON → walls, openings, ceiling, area
- [x] L-shape / snapped polygon area (not bbox-only)
- [x] Opening anchors from transform when present
- [x] Orphan opening QA warnings
- [x] Multi-room stitch + loop closure
- [x] Overlap QA after stitch
- [x] `import-apple` + **auto adjacency** from doors
- [x] Clear errors: bad manifest, tier, transform, no walls, duplicate room_id
- [ ] Real-device scan regression (needs your Apple JSON) — **required before Phase 3**
- [ ] magicplan-grade PNG (doors/windows labeled) — nice-to-have before Phase 3

## Phase 2 (gates & report)

- [x] `housefloor score` — openings, phantom/missed, ceiling, walls, footprint
- [x] Opening match by room + kind
- [x] Overlap gate from plan meta
- [x] Calibration / QA sanity gate
- [x] `score --repeat-plan` ceiling spread ≤1 cm
- [x] `score-repeat` + biased vs unrepeatable note
- [x] `ablate-drift`
- [x] `benchmark-report`
- [ ] All gates **pass** on real benchmark (needs tape/laser GT) — **required before Phase 3**
- [x] Repeat: `score --repeat-plan` + `score-repeat` + bias note
- [ ] Double-scan folder on real device (e.g. `repeat/plan.json` from 2nd run)

## Explicitly Phase 3+ (not required before Phase 3 starts)

Photo/video tiers, damage, head-to-head, fix loop bundle, raw sensor logs, TestFlight.
