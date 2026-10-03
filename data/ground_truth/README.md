# Ground truth (Tester / eval only)

The **pipeline never reads this folder.** Score with:

```powershell
python -m eval.cli score --capture data\captures\<id> --plan <path\to\plan.json> --tier lidar
```

Copy a template `{capture_id}.json`, replace `TODO` with **measured** values (tape / plan). Set `"_meta": {"status": "complete"}` when ready.

Required for footprint gate: `footprint_area_m2`. Optional: `wall_lengths_cm`, `ceiling_height_cm`, `openings_cm` (same shape as `ground_truth.json` in gate tests).
