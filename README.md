# Market Research Dashboard

Local browser dashboard for weekly game-trend tracking.

## What it shows

- 3 summary cards:
  - Top selling games
  - Streamers are playing
  - AC players are playing
- Searchable and sortable latest snapshot table for:
  - AC Discord / Statbot
  - Roblox
  - Steam
  - Twitch
- Trend explorer for rank and metric movement over time

## Data sources

This dashboard reads the installed market-research snapshot history from:

- `/Users/teranguyen/.local/share/market-research-bot/data/snapshots`

It also enriches the latest snapshot with live current metrics from:

- Steam current players via Steam Web API
- Roblox current CCU via the active ranking page

## Run

```bash
cd '/Users/teranguyen/Documents/Next Games Framework/market-research-dashboard'
./run_dashboard.sh
```

Then open:

- `http://localhost:8123`

You can also choose another port:

```bash
./run_dashboard.sh 9000
```

## Refresh data only

```bash
cd '/Users/teranguyen/Documents/Next Games Framework/market-research-dashboard'
./generate_dashboard_data.py
```
