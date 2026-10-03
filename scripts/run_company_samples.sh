#!/usr/bin/env bash
# Run the pipeline on the company's sample captures (R41) and keep the outputs.
# Needs the three Stray exports in data/captures/ (see data/manifest.csv, scripts/fetch_data.py).
set -euo pipefail
cd "$(dirname "$0")/.."

for id in c00a170fe1 1a8384c3f6 c7d28f72c6; do
  python -m pipeline.cli run --capture "data/captures/$id" --tier auto --out "outputs/company_samples/$id"
done
