#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.request import Request, urlopen

ROOT = Path('/Users/teranguyen/Documents/Next Games Framework/market-research-dashboard')
OUTPUT_PATH = ROOT / 'data' / 'dashboard-data.json'
SNAPSHOT_ROOT = Path('/Users/teranguyen/.local/share/market-research-bot/data/snapshots')
STEAM_PLAYERS_API = 'https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={appid}'
ROBLOX_ACTIVE_URL = 'https://game.roblox-jp.com/en/best/active/?genre=All'
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

SOURCE_ORDER = ['statbot', 'roblox', 'steam', 'twitch']
SOURCE_LABELS = {
    'steam': 'Steam',
    'roblox': 'Roblox',
    'twitch': 'Twitch',
    'statbot': 'AC Discord',
}
CARD_TITLES = {
    'steam': 'Top selling games',
    'twitch': 'Streamers are playing',
    'statbot': 'AC players are playing',
}


def fetch_text(url: str) -> str:
    request = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(request, timeout=30) as response:
        encoding = response.headers.get_content_charset() or 'utf-8'
        return response.read().decode(encoding, errors='replace')


def fetch_json(url: str) -> Dict[str, Any]:
    return json.loads(fetch_text(url))


def normalize_title(value: str) -> str:
    value = value or ''
    value = value.replace('™', '').replace('®', '')
    value = re.sub(r'\([^)]*\)', '', value)
    value = re.sub(r'[^a-zA-Z0-9]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip().lower()


def parse_metric_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(',', '').strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_number(value: Optional[float], metric_label: str) -> str:
    if value is None:
        return 'n/a'
    if metric_label == 'hours':
        return f'{value:,.1f} hours'
    if metric_label == 'viewers':
        return f'{int(round(value)):,.0f} viewers'
    if metric_label == 'ccu':
        return f'{int(round(value)):,.0f} CCU'
    if metric_label == 'players':
        return f'{int(round(value)):,.0f} players'
    return f'{value:,.0f}'


def format_delta(current: Optional[float], previous: Optional[float], metric_label: str) -> Tuple[str, Optional[float]]:
    if current is None or previous is None:
        return 'n/a', None
    delta = current - previous
    if metric_label == 'hours':
        return f"{delta:+,.1f}", delta
    return f"{delta:+,.0f}", delta


def load_snapshots() -> Dict[str, Dict[str, Dict[str, Any]]]:
    snapshots: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for path in sorted(SNAPSHOT_ROOT.glob('*.json')):
        stem = path.stem
        match = re.match(r'(?P<date>\d{4}-\d{2}-\d{2})-(?P<platform>.+)', stem)
        if not match:
            continue
        date_part = match.group('date')
        platform = match.group('platform')
        payload = json.loads(path.read_text(encoding='utf-8'))
        snapshots[platform][date_part] = payload
    return snapshots


def ordered_dates(platform_data: Dict[str, Dict[str, Any]]) -> List[str]:
    return sorted(platform_data.keys())


def fetch_steam_current_players(app_ids: Iterable[str]) -> Dict[str, float]:
    results: Dict[str, float] = {}
    for app_id in app_ids:
        try:
            payload = fetch_json(STEAM_PLAYERS_API.format(appid=app_id))
            count = payload.get('response', {}).get('player_count')
            if count is not None:
                results[str(app_id)] = float(count)
        except Exception:
            continue
    return results


def fetch_roblox_current_ccu() -> Dict[str, float]:
    html = fetch_text(ROBLOX_ACTIVE_URL)
    matches = re.findall(
        r"<tr><td>(?P<rank>\d+)</td><td><a href='https://www\.roblox\.com/games/(?P<game_id>\d+)/[^']*'>(?P<title>.*?)</a></td><td>(?P<ccu>[\d,]+)</td></tr>",
        html,
        flags=re.IGNORECASE,
    )
    result: Dict[str, float] = {}
    for game_id, _title, ccu in [(m[1], m[2], m[3]) for m in matches]:
        result[game_id] = float(ccu.replace(',', ''))
    return result


def build_rows_and_history(snapshots: Dict[str, Dict[str, Dict[str, Any]]]) -> Dict[str, Any]:
    steam_live = {}
    roblox_live = {}
    if 'steam' in snapshots:
        latest_steam_date = ordered_dates(snapshots['steam'])[-1]
        latest_steam_entries = snapshots['steam'][latest_steam_date].get('entries', [])
        steam_live = fetch_steam_current_players([entry['game_id'] for entry in latest_steam_entries])
    if 'roblox' in snapshots:
        roblox_live = fetch_roblox_current_ccu()

    latest_rows: List[Dict[str, Any]] = []
    histories: Dict[str, List[Dict[str, Any]]] = {}
    cards: List[Dict[str, Any]] = []

    for platform in SOURCE_ORDER:
        platform_snaps = snapshots.get(platform, {})
        if not platform_snaps:
            continue
        dates = ordered_dates(platform_snaps)
        latest_date = dates[-1]
        previous_date = dates[-2] if len(dates) > 1 else None
        latest_entries = platform_snaps[latest_date].get('entries', [])
        previous_entries = {
            str(entry.get('game_id')): entry
            for entry in (platform_snaps.get(previous_date, {}).get('entries', []) if previous_date else [])
        }

        for entry in latest_entries:
            game_id = str(entry.get('game_id'))
            source = platform
            row_key = f'{source}:{game_id}'
            metric_label = entry.get('metric_label') or {
                'steam': 'players',
                'roblox': 'ccu',
                'twitch': 'viewers',
                'statbot': 'hours',
            }[source]
            current_metric = parse_metric_number(entry.get('views'))
            if source == 'steam':
                current_metric = steam_live.get(game_id)
            elif source == 'roblox':
                current_metric = roblox_live.get(game_id)

            previous_entry = previous_entries.get(game_id)
            previous_metric = parse_metric_number(previous_entry.get('views')) if previous_entry else None
            previous_rank = int(previous_entry.get('rank')) if previous_entry else None
            current_rank = int(entry.get('rank'))
            if source in {'steam', 'roblox'}:
                delta_text = 'n/a'
                delta_value = None
                if previous_rank is not None:
                    rank_delta = previous_rank - current_rank
                    if rank_delta > 0:
                        delta_text = f'Rank ▲{rank_delta}'
                    elif rank_delta < 0:
                        delta_text = f'Rank ▼{abs(rank_delta)}'
                    else:
                        delta_text = 'Rank ='
                    delta_value = float(rank_delta)
            else:
                delta_text, delta_value = format_delta(current_metric, previous_metric, metric_label)

            latest_rows.append({
                'key': row_key,
                'title': entry.get('title', ''),
                'platform': source,
                'platformLabel': SOURCE_LABELS[source],
                'rank': current_rank,
                'url': entry.get('url', ''),
                'gameId': game_id,
                'currentMetric': format_number(current_metric, metric_label),
                'currentMetricValue': current_metric,
                'metricLabel': metric_label,
                'delta': delta_text,
                'deltaValue': delta_value,
                'isNew': bool(entry.get('is_new')),
                'snapshotDate': latest_date,
            })

            history: List[Dict[str, Any]] = []
            for date in dates:
                snap_entries = platform_snaps[date].get('entries', [])
                match = next((item for item in snap_entries if str(item.get('game_id')) == game_id), None)
                if not match:
                    continue
                hist_metric = parse_metric_number(match.get('views'))
                if source == 'steam' and date == latest_date:
                    hist_metric = steam_live.get(game_id)
                elif source == 'roblox' and date == latest_date:
                    hist_metric = roblox_live.get(game_id)
                history.append({
                    'date': date,
                    'rank': int(match.get('rank')),
                    'metric': hist_metric,
                    'metricLabel': metric_label,
                    'isNew': bool(match.get('is_new')),
                })
            histories[row_key] = history

        if platform in CARD_TITLES and latest_entries:
            top_entry = latest_rows[-len(latest_entries)]
            cards.append({
                'id': platform,
                'title': CARD_TITLES[platform],
                'game': top_entry['title'],
                'platformLabel': top_entry['platformLabel'],
                'currentMetric': top_entry['currentMetric'],
                'delta': top_entry['delta'],
                'url': top_entry['url'],
            })

    latest_rows.sort(key=lambda row: (SOURCE_ORDER.index(row['platform']), row['rank']))
    return {'rows': latest_rows, 'histories': histories, 'cards': cards}


def build_dashboard_payload() -> Dict[str, Any]:
    snapshots = load_snapshots()
    built = build_rows_and_history(snapshots)
    latest_snapshot_date = max(
        date
        for platform_data in snapshots.values()
        for date in platform_data.keys()
    )
    card_order = ['steam', 'twitch', 'statbot']
    ordered_cards = sorted(built['cards'], key=lambda card: card_order.index(card['id']) if card['id'] in card_order else 99)
    return {
        'generatedAt': datetime.now().isoformat(),
        'latestSnapshotDate': latest_snapshot_date,
        'cards': ordered_cards,
        'rows': built['rows'],
        'histories': built['histories'],
        'sources': [{
            'id': source,
            'label': SOURCE_LABELS[source],
        } for source in SOURCE_ORDER],
    }


def main() -> int:
    payload = build_dashboard_payload()
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {OUTPUT_PATH}')
    print(f"Rows: {len(payload['rows'])}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
