# Phase 4 — Photo tier

| Item | Status |
|------|--------|
| Manifest `tier: photos` **or** auto `rooms/<id>/photos/` | **Done** |
| EXIF intrinsics → sparse OpenCV MVS cue (§5.4 offline path) | **Done** (`photo_mvs.py`) |
| Scale σ: still count + MVS + metric cue spread | **Done** (`photo_scale.py`) |
| Prior metric rescale (door height / image fraction) | **Done** (`photo_metric.py`) |
| VLM consistency (rectangle refine, reject outliers) | **Done** |
| Dual-batch VLM median merge (≥6 stills) | **Done** |
| Vanishing-line aspect hint (offline + VLM refine) | **Done** (`photo_aspect.py`) |
| Offline prior + optional Azure VLM (≤8 stills, L-shape walls, windows) | **Done** |
| Multi-room layout §5.6 + **hub** multi-door inference | **Done** |
| Doorway ORB verification warning | **Done** (`photo_door_verify.py`) |
| Sparse MVS horizontal rescale (+ VLM median fuse) | **Done** (`photo_scale.py`) |
| Door pairing width **and** height (§5.6) | **Done** (`photo_layout.py`) |
| Drop weak inferred edges (ORB) before stitch | **Done** (`filter_inferred_photo_edges`) |
| Camera-height + EXIF focal sanity cues | **Done** (`photo_metric.py`, `photo_exif.py`) |
| Same JSON/PNG contract | **Done** |

**Still Tester-owned (not pipeline GT):** ±8% wall / stitch footprint gates vs `data/ground_truth/`.

**Not in repo (disclosed):** full metric dense MVS weights (MapAnything-class); sparse SfM + VLM is the v0 front-end.

```powershell
$env:MPLBACKEND='Agg'
python -m pytest tests/test_photo_tier.py tests/test_photo_vlm_offline.py tests/test_photo_multi_stitch.py tests/test_photo_layout.py tests/test_photo_capture_auto.py -q
python scripts/phase4_signoff.py
housefloor run --capture <dir> --tier auto --out out/
```

Azure: `docs/AZURE_WHEN_NEEDED.md`, `.env.example`. Sign-off: `docs/PHASE4_SIGNOFF_REPORT.json`.
