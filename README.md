# LiDAR_Damage_assessment

**Phase 1 + 1b + 2 (current):** LiDAR → stitched plan + QA (orphan openings, overlap) + gate scoring.  
**Offline.** No Azure. No API keys.

Phases: [docs/PHASES.md](docs/PHASES.md) · Azure (later): [docs/AZURE_WHEN_NEEDED.md](docs/AZURE_WHEN_NEEDED.md)

## Setup

```powershell
cd D:\Rikita\123\AI_Challenge
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

## Run

```powershell
housefloor run --capture examples\benchmark_sample
```

Output: `examples\benchmark_sample\out\plan.json` and `floorplan.png`.

## Import Apple exports (when you have scans)

```powershell
housefloor import-apple --input C:\path\to\json_folder --out benchmark\raw\my_house
housefloor run --capture benchmark\raw\my_house
```

## Gates (Phase 2)

```powershell
housefloor run --capture examples\benchmark_sample
housefloor score --capture examples\benchmark_sample
housefloor ablate-drift --capture examples\benchmark_sample
```

## Tests

```powershell
pytest tests -q
```
