# Capture data (local only)

Put real evaluation captures here, one folder per `capture_id` (see `manifest.csv`).

```text
data/captures/<capture_id>/
  manifest.json          # RoomPlan / multi-room LiDAR
  — or —
  odometry.csv, depth/, confidence/   # Stray Scanner
  — or —
  walkthrough.mp4 (+ optional poses)  # Video tier
```

Download archives when URLs are set:

```powershell
python scripts/fetch_data.py
```

Nothing under `data/captures/` is committed (except this README and `.gitkeep`).
