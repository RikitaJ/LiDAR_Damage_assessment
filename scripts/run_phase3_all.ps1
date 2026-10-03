# Phase 3: run video tier on all local Stray samples with rgb.mp4
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$samples = @(
    "single_room\c00a170fe1",
    "single_scan_floor_only\1a8384c3f6",
    "single_scan_with_ceiling\c7d28f72c6"
)

foreach ($rel in $samples) {
    $cap = Join-Path (Get-Location) $rel
    if (-not (Test-Path (Join-Path $cap "rgb.mp4"))) {
        Write-Host "[skip] $rel (no rgb.mp4)"
        continue
    }
    $out = Join-Path $cap "out_phase3_video"
    Write-Host "[run] video -> $out"
    .\.venv\Scripts\housefloor.exe run --capture $cap --out $out --tier video --drift on
}

$env:MPLBACKEND = "Agg"
.\.venv\Scripts\python.exe -m pytest tests/test_phase3_video.py tests/test_video_tier.py -q
Write-Host "Phase 3 script finished."
