# Multi-room Stray Scanner workflow

1. Place one Stray export under `data/captures/<capture_id>/` (`odometry.csv`, `depth/`, `confidence/`, optional `rgb.mp4`).

2. Add `manifest.json` at the capture root:

```json
{
  "capture_id": "<capture_id>",
  "tier": "lidar",
  "capture_format": "stray",
  "rooms": [
    { "room_id": "R1", "name": "Room 1", "segment": 0 },
    { "room_id": "R2", "name": "Room 2", "segment": 1 }
  ],
  "adjacency": [
    { "room_a": "R1", "room_b": "R2", "via_opening_id": "door_1" }
  ]
}
```

3. Run:

```powershell
housefloor run --capture data\captures\<capture_id> --tier auto --drift on
```

Each `segment` index splits the odometry timeline into equal parts (`pipeline/tiers/stray_segment.py`). Tune room count to match your walk (one loop per room).

Example template: `data/examples/stray_multi_manifest.json`.
