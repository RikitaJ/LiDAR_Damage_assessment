# LiDAR_Damage_assessment

Multi-tier floor plans: **RoomPlan LiDAR**, **Stray Scanner** depth, and **video v0** → stitch, QA gates, intervals.  
Phases 1–3 run **offline** (no API keys). Azure is for **Phase 4+** only — see [docs/AZURE_WHEN_NEEDED.md](docs/AZURE_WHEN_NEEDED.md).

Brief: [docs/ASSESSMENT_BRIEF.md](docs/ASSESSMENT_BRIEF.md) · Phases: [docs/PHASES.md](docs/PHASES.md)

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

Optional Azure (after `az login`):

```powershell
python scripts/_write_env_from_consolidated.py
```

## Capture data

Real scans live under **`data/captures/<capture_id>/`** (not in git). See [data/README.md](data/README.md) and `data/manifest.csv` for downloads.

```powershell
housefloor run --capture data\captures\<your_capture_id>
housefloor run --capture data\captures\<your_capture_id> --tier auto
```

## Import Apple exports

```powershell
housefloor import-apple --input C:\path\to\json_folder --out data\captures\my_house
housefloor run --capture data\captures\my_house
```

## Gates (Phase 2)

Requires a local capture plus optional `ground_truth.json` next to the capture or passed to `score`.

```powershell
housefloor score --capture data\captures\<id>
housefloor ablate-drift --capture data\captures\<id>
```

## Tests

Uses **pytest fixtures only** (no bundled demo house in the repo):

```powershell
$env:MPLBACKEND='Agg'; pytest tests -q
```

## Scoring (ground truth)

Fill `data/ground_truth/<capture_id>.json` with **measured** values, then:

```powershell
python -m eval.cli score --capture single_room\c00a170fe1 --plan single_room\c00a170fe1\out_stray_v3\plan.json --tier lidar
```

Pipeline never reads GT; calibration multipliers live in `configs/calibration.json`.
