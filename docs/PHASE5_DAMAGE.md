# Phase 5 — damage, concealed rules, scope

Offline-first damage pipeline wired from `pipeline/run.py` after geometry + stitch.

## Flow

1. **`surfaces.py`** — net wall/ceiling areas (openings subtracted) with intervals.
2. **`detect.py`** — up to 12 spaced stills + 3 video frames; `.cache/damage/` v3; mask bbox UV; ceiling stains; optional **Azure OpenAI damage VLM** (`.cache/damage_vlm/`); multi-view merge + score refine.
3. **`concealed.py`** — deterministic rules in `configs/concealed_rules.json` (CD-01…CD-05).
4. **`scope_engine.py`** — line items from `configs/scope_rules.json`.
5. **`phase5.py`** — orchestrates the above; merges QA geometry flags.

## Output fields (`plan.json`)

- `surfaces[]`
- `damage_regions[]` — class, `surface_id`, metric fields with intervals, `polygon_surface` in wall UV (m)
- `concealed_damage_flags[]` — `rule_id`, `triggered_by`, `surfaces`, `rationale`
- `scope_line_items[]` — `code`, `quantity` interval, `because`

## Render

`pipeline/export/plan_render.py` hatches damage segments along the matched wall on `floorplan.png`.

## Sign-off

```powershell
$env:MPLBACKEND='Agg'
python scripts/phase5_signoff.py
python -m pytest tests/test_damage_phase5.py tests/test_damage_rules.py -q
```

Azure Vision is optional; sign-off passes without API keys.

## Edge cases (rule 5)

- `pipeline/damage/sanitize.py` — invalid hits/regions dropped with warnings; R39 widens σ and caps score.
- `detect.py` — empty rooms, 0-byte/corrupt/tiny images, depth PNGs, rooms without walls, single-still warning, OpenCV missing.
- Tests: `tests/test_damage_edge_cases.py`

```powershell
python -m pytest tests/test_damage_edge_cases.py -q
```

## Limitations (v1 vs brief §5.8)

These are **implemented as behavior**, not only prose:

- Every `plan.json` includes `pipeline_meta.limitations[]` (static v1 gaps + run-specific flags such as missing RGB or R39 mirror/glass).
- Heuristic / Vision-tag regions get **widened intervals** (`heuristic_widen` in confidence notes).
- Empty `damage_regions[]` when there is no usable RGB — scope is not invented.

Not in v2 (documented, not hidden): SAM segmenter, true camera projection. Staged benchmark damage (R14) still needs real photos to score detection accuracy.
