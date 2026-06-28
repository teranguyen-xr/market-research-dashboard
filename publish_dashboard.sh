#!/bin/zsh
set -euo pipefail

cd '/Users/teranguyen/Documents/Next Games Framework/market-research-dashboard'

git pull --rebase origin main

./generate_dashboard_data.py

if git diff --quiet -- data/dashboard-data.json; then
  echo 'Dashboard data unchanged; nothing to publish.'
  exit 0
fi

git add data/dashboard-data.json
git commit -m "Update dashboard data $(date +%F)"
git push origin main

echo 'Dashboard published to GitHub Pages source branch.'
