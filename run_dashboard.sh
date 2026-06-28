#!/bin/zsh
set -euo pipefail
cd '/Users/teranguyen/Documents/Next Games Framework/market-research-dashboard'
./generate_dashboard_data.py
PORT="${1:-8123}"
echo "Dashboard ready at http://localhost:${PORT}"
exec python3 -m http.server "$PORT"
