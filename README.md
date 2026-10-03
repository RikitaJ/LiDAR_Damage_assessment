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

Copies keys from **rg-consolidated-plan-2026** into gitignored `.env` (Azure OpenAI + optional Vision hub).

## Run

```powershell
housefloor run --capture examples\benchmark_sample
housefloor run --capture "single_room sample data_given\c00a170fe1" --tier auto
housefloor run --capture "single_room sample data_given\c00a170fe1" --tier video
```

Output: `<capture>\out\plan.json` and `floorplan.png` (or `--out` path).

## Import Apple exports

```powershell
housefloor import-apple --input C:\path\to\json_folder --out benchmark\raw\my_house
housefloor run --capture benchmark\raw\my_house
```

## Gates (Phase 2)

```powershell
housefloor score --capture examples\benchmark_sample
housefloor ablate-drift --capture examples\benchmark_sample
```

## Tests

```powershell
$env:MPLBACKEND='Agg'; pytest tests -q
```
