# Ground truth (Tester / eval only)

The **pipeline never reads this folder.** Only `eval/` and `housefloor score` (local `ground_truth.json`) consume measurements.

## Workflow

1. **Capture** on disk (e.g. `data/captures/photos_M/` or `single_room/my_run/`).
2. **Run pipeline** (Builder path — no GT):

   ```powershell
   housefloor run --capture data\captures\photos_M --tier photos --out data\captures\photos_M\out
   ```

3. **Template** (structure only — no invented numbers):

   ```powershell
   python -m eval.cli gt-template --capture data\captures\photos_M
   ```

   Creates `data/ground_truth/<capture_id>.json` with `TODO` fields from `manifest.json` or `rooms/*`.

4. **Tester measures** (tape, brief §7): sketch, wall lengths (cm), ceiling (cm), openings (cm), **stitched footprint** (m²).

5. Set `"_meta": {"status": "complete", ...}` and replace every `TODO` with measured numbers.

6. **Score** (photo tier ±8% walls / footprint):

   ```powershell
   python -m eval.cli score --capture data\captures\photos_M --tier photos
   ```

   Writes `out/eval_report.json` with gate pass/fail.

7. **Calibration** (after at least one trusted LiDAR fixture + GT):

   ```powershell
   python -m eval.cli calibrate
   ```

   Updates `configs/calibration.json` multipliers — pipeline reads multipliers only, not GT.

## JSON shape

Same as the synthetic fixture `lidar_two_room_fixture.json`:

| Field | Required for gates | Notes |
|-------|-------------------|--------|
| `footprint_area_m2` | **Yes** | Whole-property stitched area for multi-room |
| `wall_lengths_cm` | For wall gate | Per `room_id`, list clockwise from W1 |
| `ceiling_height_cm` | Optional | Per room; strict gate mainly LiDAR |
| `openings_cm` | Optional | `{room_id, kind, width_cm}` |

`capture_id` in GT filename must match `manifest.json` `capture_id` or folder name (`eval/capture_id.py`).

## Legacy: GT next to capture

```powershell
housefloor score --capture <dir> --tier photos
```

Expects `<capture>/ground_truth.json`. You may copy from `data/ground_truth/<id>.json` after Tester sign-off.

## Phase 4 photo benchmark

Use the **same rooms** as LiDAR/video when possible (R15). GT is **one truth per physical space** — score each tier’s `plan.json` with the same `data/ground_truth/<capture_id>.json` and `--tier photos`.

Do not commit captures with real customer data unless policy allows; GT numbers must come from measurement scripts/records listed in `data/manifest.csv`.
