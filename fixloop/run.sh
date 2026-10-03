#!/usr/bin/env bash
# Regenerate the fix-loop runs from the tags (brief section 10).
# Needs the B1 capture in data/captures/lidar_B1_rep1 (see data/manifest.csv, scripts/fetch_data.py).
set -euo pipefail
cd "$(dirname "$0")/.."

python -m eval.run --rerun --ref fixloop-before --ref fixloop-after --skip-current \
  --runs fixloop/runs --report fixloop/REPORT.md

for side in before after; do
  rm -rf "fixloop/$side"
  mkdir -p "fixloop/$side"
  cp "fixloop/runs/lidar_B1_rep1@$(git rev-parse --short "fixloop-$side^{commit}")"/{plan.json,floorplan.png} "fixloop/$side/"
done

git diff fixloop-after~1 fixloop-after -- pipeline > fixloop/diff.patch
