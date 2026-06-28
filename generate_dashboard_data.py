#!/usr/bin/env python3
from __future__ import annotations
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.request import Request, urlopen
ROOT = Path('/Users/teranguyen/Documents/Next Games Framework/market-research-dashboard')
OUTPUT_PATH = ROOT / 'data' / 'dashboard-data.json'
SNAPSHOT_ROOT = Path('/Users/teranguyen/.local/share/market-research-bot/data/snapshots')
STEAM_PLAYERS_API = 'https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={appid}'
ROBLOX_ACTIVE_URL = 'https://game.roblox-jp.com/en/best/active/?genre=All'
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
NOW = datetime.now(timezone.utc)
SOURCE_ORDER = ['statbot', 'roblox', 'steam', 'twitch']
SOURCE_LABELS = {
    'steam': 'Steam',
    'roblox': 'Roblox',
    'twitch': 'Twitch',
    'statbot': 'AC Discord',
}
CARD_TITLES = {
    'steam': 'Top selling games',
    'statbot': 'AC players are playing',
}
TWITCH_SUMMARY_EXCLUDED = {
    'Just Chatting',
    'IRL',
    'Music',
    'Art',
    'ASMR',
    'Sports',
    'Talk Shows & Podcasts',
    'Special Events',
    'Pools, Hot Tubs, and Beaches',
}
YOUTUBE_WATCHLIST = [
    {'name': 'Flamingo', 'url': 'https://www.youtube.com/@flamingo', 'segment': 'Roblox discovery'},
    {'name': 'KreekCraft', 'url': 'https://www.youtube.com/@KreekCraft', 'segment': 'Roblox discovery'},
    {'name': 'ItsFunneh', 'url': 'https://www.youtube.com/@ItsFunneh', 'segment': 'Roblox discovery'},
    {'name': 'Markiplier', 'url': 'https://www.youtube.com/@markiplier', 'segment': 'Steam co-op survival'},
    {'name': 'jacksepticeye', 'url': 'https://www.youtube.com/@jacksepticeye', 'segment': 'Steam co-op survival'},
    {'name': 'caseoh_', 'url': 'https://www.youtube.com/@caseoh_', 'segment': 'Steam co-op survival'},
    {'name': 'VanossGaming', 'url': 'https://www.youtube.com/@VanossGaming', 'segment': 'Steam friendslop / party-chaos'},
    {'name': 'SMii7Y', 'url': 'https://www.youtube.com/@SMii7Y', 'segment': 'Steam friendslop / party-chaos'},
    {'name': 'H2ODelirious', 'url': 'https://www.youtube.com/@H2ODelirious', 'segment': 'Steam friendslop / party-chaos'},
    {'name': 'WILDCAT', 'url': 'https://www.youtube.com/@WILDCAT', 'segment': 'Steam friendslop / party-chaos'},
]
CUSTOM_GAME_ALIASES = {
    'R.E.P.O.': ['repo'],
    'PEAK': ['peak'],
    'Dead Rails': ['dead rails'],
    'Grow a Garden': ['grow a garden'],
    'Meccha Chameleon': ['meccha chameleon', 'meccha'],
    'Inferno Protocol': ['inferno protocol'],
    'ARC Raiders': ['arc raiders'],
    'We Gotta Go': ['we gotta go'],
    'CAIRN': ['cairn'],
}
CUSTOM_GAME_URLS = {
    'R.E.P.O.': 'https://store.steampowered.com/app/3241660/REPO/',
    'PEAK': 'https://store.steampowered.com/app/3527290/PEAK/',
    'Dead Rails': 'https://www.roblox.com/games/116495829188952/Dead-Rails-Alpha',
    'Grow a Garden': 'https://www.roblox.com/games/126884695634066/Grow-a-Garden',
    'Meccha Chameleon': 'https://store.steampowered.com/search/?term=Meccha%20Chameleon',
    'Inferno Protocol': 'https://store.steampowered.com/search/?term=Inferno%20Protocol',
    'ARC Raiders': 'https://store.steampowered.com/app/1808500/ARC_Raiders/',
    'We Gotta Go': 'https://store.steampowered.com/search/?term=We%20Gotta%20Go',
    'CAIRN': 'https://store.steampowered.com/app/1588550/CAIRN/',
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
    value = re.sub(r'\([^)]*\)', ' ', value)
    value = re.sub(r'[^a-zA-Z0-9#@]+', ' ', value)
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

def build_summary_cards(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    by_platform: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_platform[row['platform']].append(row)

    steam_rows = by_platform.get('steam', [])
    if steam_rows:
        top_entry = steam_rows[0]
        cards.append({
            'id': 'steam',
            'title': 'Top selling games',
            'game': top_entry['title'],
            'platformLabel': top_entry['platformLabel'],
            'currentMetric': top_entry['currentMetric'],
            'delta': top_entry['delta'],
            'url': top_entry['url'],
        })

    twitch_rows = by_platform.get('twitch', [])
    if twitch_rows:
        filtered = [row for row in twitch_rows if row['title'] not in TWITCH_SUMMARY_EXCLUDED]
        new_filtered = [row for row in filtered if row.get('isNew')]
        if new_filtered:
            twitch_entry = new_filtered[0]
            twitch_delta = f"Rank #{twitch_entry['rank']}"
        elif filtered:
            twitch_entry = filtered[0]
            twitch_delta = 'No new Twitch game this week'
        else:
            twitch_entry = twitch_rows[0]
            twitch_delta = 'No new Twitch game this week'
        cards.append({
            'id': 'twitch',
            'title': 'New Game from Twitch Streamers',
            'game': twitch_entry['title'],
            'platformLabel': twitch_entry['platformLabel'],
            'currentMetric': twitch_entry['currentMetric'],
            'delta': twitch_delta,
            'url': twitch_entry['url'],
        })

    statbot_rows = by_platform.get('statbot', [])
    if statbot_rows:
        top_entry = statbot_rows[0]
        cards.append({
            'id': 'statbot',
            'title': 'AC players are playing',
            'game': top_entry['title'],
            'platformLabel': top_entry['platformLabel'],
            'currentMetric': top_entry['currentMetric'],
            'delta': top_entry['delta'],
            'url': top_entry['url'],
        })
    return cards

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
    latest_rows.sort(key=lambda row: (SOURCE_ORDER.index(row['platform']), row['rank']))
    cards = build_summary_cards(latest_rows)
    return {'rows': latest_rows, 'histories': histories, 'cards': cards}
def compact_number(value: Optional[float]) -> str:
    if value is None:
        return 'n/a'
    value = float(value)
    if value >= 1_000_000_000:
        return f'{value / 1_000_000_000:.1f}B'
    if value >= 1_000_000:
        return f'{value / 1_000_000:.1f}M'
    if value >= 1_000:
        return f'{value / 1_000:.1f}K'
    return f'{int(round(value))}'
def compact_subscriber_label(label: str) -> str:
    text = label.lower().replace(' subscribers', '').replace(' subscriber', '').strip()
    text = text.replace(' million', 'M').replace(' thousand', 'K').replace(' billion', 'B')
    return text.replace(' ', '')
def relative_time(value: datetime) -> str:
    delta_days = max(0, int((NOW - value).total_seconds() // 86400))
    if delta_days == 0:
        return 'Today'
    if delta_days == 1:
        return '1 day ago'
    return f'{delta_days} days ago'
def extract_handle_from_url(url: str) -> str:
    match = re.search(r'/@([^/]+)/video/', url)
    return f"@{match.group(1)}" if match else url
def shorten_words(text: str, limit: int = 7) -> str:
    words = re.sub(r'\s+', ' ', text).strip().split(' ')
    if len(words) <= limit:
        return ' '.join(words)
    return ' '.join(words[:limit]) + '...'
def current_snapshot_date() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def latest_snapshot_entries_before(platform_snapshots: Dict[str, Dict[str, Any]], date_limit: str) -> List[Dict[str, Any]]:
    for date in sorted(platform_snapshots.keys(), reverse=True):
        if date >= date_limit:
            continue
        entries = platform_snapshots[date].get('entries', [])
        if entries:
            return entries
    return []


def save_snapshot(platform: str, entries: List[Dict[str, Any]], source_url: str) -> Path:
    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    target = SNAPSHOT_ROOT / f"{current_snapshot_date()}-{platform}.json"
    payload = {
        'generated_at': datetime.now().isoformat(),
        'source_url': source_url,
        'entries': entries,
    }
    target.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    return target
def build_game_catalog(rows: List[Dict[str, Any]], snapshots: Dict[str, Dict[str, Dict[str, Any]]]) -> List[Dict[str, str]]:
    blacklist = {'roblox', 'steam', 'twitch', 'ac discord', 'discord'}
    catalog: Dict[str, Dict[str, str]] = {}
    preferred_platforms = {'steam', 'roblox'}
    for row in rows:
        name = row.get('title') or ''
        if not name or normalize_title(name) in blacklist:
            continue
        existing = catalog.get(name)
        url = row.get('url') or ''
        should_replace = existing is None
        if existing is not None and not existing.get('url') and row.get('platform') in preferred_platforms:
            should_replace = True
        if existing is not None and row.get('platform') in preferred_platforms and existing.get('url', '').startswith('https://twitchtracker.com'):
            should_replace = True
        if should_replace:
            catalog[name] = {'title': name, 'url': url if row.get('platform') in preferred_platforms else existing.get('url', '') if existing else ''}
    for title, aliases in CUSTOM_GAME_ALIASES.items():
        catalog[title] = {'title': title, 'url': CUSTOM_GAME_URLS.get(title, catalog.get(title, {}).get('url', ''))}
    return [
        {
            'title': item['title'],
            'url': item['url'],
            'aliases': [normalize_title(item['title'])] + [normalize_title(alias) for alias in CUSTOM_GAME_ALIASES.get(item['title'], [])],
        }
        for item in catalog.values()
        if normalize_title(item['title']) not in blacklist
    ]
def match_game(text: str, catalog: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    haystack = normalize_title(text)
    best: Optional[Tuple[int, str, str]] = None
    for item in catalog:
        for alias in item['aliases']:
            if alias and alias in haystack:
                score = len(alias)
                if best is None or score > best[0]:
                    best = (score, item['title'], item['url'])
    if best is None:
        return None, None
    return best[1], best[2]
def latest_non_empty_snapshot(platform_snapshots: Dict[str, Dict[str, Any]]) -> Tuple[Optional[str], List[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
    dates = ordered_dates(platform_snapshots)
    latest_date = None
    latest_entries: List[Dict[str, Any]] = []
    previous_date = None
    previous_entries: List[Dict[str, Any]] = []
    for date in reversed(dates):
        entries = platform_snapshots[date].get('entries', [])
        if entries and latest_date is None:
            latest_date = date
            latest_entries = entries
        elif entries and latest_date is not None:
            previous_date = date
            previous_entries = entries
            break
    return latest_date, latest_entries, previous_date, previous_entries
def parse_channel_metadata(channel_url: str) -> Tuple[Optional[str], str]:
    html = fetch_text(channel_url)
    channel_id_match = re.search(r'externalId":"([^"]+)"', html) or re.search(r'channelId":"([^"]+)"', html)
    subscriber_match = re.search(r'accessibilityLabel":"([0-9.,]+\s+(?:million|thousand|billion)?\s*subscribers)"', html, flags=re.IGNORECASE)
    channel_id = channel_id_match.group(1) if channel_id_match else None
    subscribers = compact_subscriber_label(subscriber_match.group(1)) if subscriber_match else 'n/a'
    return channel_id, subscribers
def fetch_youtube_feed_entries(channel_id: str) -> List[Dict[str, Any]]:
    rss = fetch_text(f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}')
    root = ET.fromstring(rss)
    ns = {
        'atom': 'http://www.w3.org/2005/Atom',
        'media': 'http://search.yahoo.com/mrss/',
    }
    entries: List[Dict[str, Any]] = []
    for entry in root.findall('atom:entry', ns):
        title = entry.findtext('atom:title', default='', namespaces=ns)
        link_el = entry.find('atom:link', ns)
        link = link_el.attrib.get('href', '') if link_el is not None else ''
        published_text = entry.findtext('atom:published', default='', namespaces=ns)
        published = datetime.fromisoformat(published_text.replace('Z', '+00:00')) if published_text else NOW
        description = entry.findtext('.//media:description', default='', namespaces=ns)
        statistics = entry.find('.//media:statistics', ns)
        views = parse_metric_number(statistics.attrib.get('views')) if statistics is not None else None
        entries.append({
            'title': title,
            'url': link,
            'published': published,
            'description': description,
            'views': views,
        })
    return entries
def build_creator_momentum(snapshots: Dict[str, Dict[str, Dict[str, Any]]], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    previous_coverage_keys = {
        f"{item.get('creator')}|{item.get('game')}"
        for item in latest_snapshot_entries_before(snapshots.get('youtube_creators', {}), current_snapshot_date())
        if item.get('creator') and item.get('game')
    }
    catalog = build_game_catalog(rows, snapshots)
    coverage_rows: List[Dict[str, Any]] = []
    for creator in YOUTUBE_WATCHLIST:
        try:
            channel_id, subscribers = parse_channel_metadata(creator['url'])
            if not channel_id:
                continue
            feed_entries = fetch_youtube_feed_entries(channel_id)
        except Exception:
            continue

        matched_row = None
        fallback_entry = None
        for feed_entry in feed_entries:
            if (NOW - feed_entry['published']).days > 30:
                continue
            if fallback_entry is None:
                fallback_entry = feed_entry
            game, game_url = match_game(feed_entry['title'] + ' ' + feed_entry['description'], catalog)
            if not game:
                continue
            coverage_key = f"{creator['name']}|{game}"
            matched_row = {
                'creator': creator['name'],
                'creatorUrl': creator['url'],
                'segment': creator['segment'],
                'game': game,
                'gameUrl': game_url or '',
                'platform': 'YouTube',
                'video': feed_entry['title'],
                'videoUrl': feed_entry['url'],
                'subscribers': subscribers,
                'views': compact_number(feed_entry['views']),
                'viewsValue': feed_entry['views'] or 0,
                'posted': relative_time(feed_entry['published']),
                'postedAt': feed_entry['published'].isoformat(),
                'status': 'NEW' if coverage_key not in previous_coverage_keys and previous_coverage_keys else 'Repeat',
                'matched': True,
            }
            break

        if matched_row is not None:
            coverage_rows.append(matched_row)
            continue

        if fallback_entry is not None:
            coverage_rows.append({
                'creator': creator['name'],
                'creatorUrl': creator['url'],
                'segment': creator['segment'],
                'game': 'No tracked game yet',
                'gameUrl': '',
                'platform': 'YouTube',
                'video': fallback_entry['title'],
                'videoUrl': fallback_entry['url'],
                'subscribers': subscribers,
                'views': compact_number(fallback_entry['views']),
                'viewsValue': fallback_entry['views'] or 0,
                'posted': relative_time(fallback_entry['published']),
                'postedAt': fallback_entry['published'].isoformat(),
                'status': 'Watch',
                'matched': False,
            })

    coverage_rows.sort(key=lambda item: (item.get('matched', False), item['postedAt'], item['viewsValue']), reverse=True)
    trend_rows: List[Dict[str, Any]] = []
    for platform_name, label, limit in [
        ('tiktok_friendslop', '#friendslop', 5),
        ('tiktok_gaming', '#gaming', 5),
    ]:
        platform_snaps = snapshots.get(platform_name, {})
        latest_date, latest_entries, previous_date, previous_entries = latest_non_empty_snapshot(platform_snaps)
        if not latest_entries:
            continue
        previous_urls = {entry.get('url') for entry in previous_entries if entry.get('url')}
        for entry in latest_entries[:limit]:
            game, game_url = match_game(entry.get('title', ''), catalog)
            created_at = datetime.fromisoformat((entry.get('created_at') or latest_date + 'T00:00:00+00:00').replace('Z', '+00:00'))
            url = entry.get('url', '')
            if (NOW - created_at).days > 14:
                continue
            trend_rows.append({
                'bucket': label,
                'game': game or 'Unclassified',
                'gameUrl': game_url or '',
                'caption': shorten_words(entry.get('title', ''), 7),
                'url': url,
                'creator': extract_handle_from_url(url),
                'views': compact_number(parse_metric_number(entry.get('views'))),
                'viewsValue': parse_metric_number(entry.get('views')) or 0,
                'posted': relative_time(created_at),
                'postedAt': created_at.isoformat(),
                'status': 'NEW' if bool(entry.get('is_new')) or url not in previous_urls else 'Repeat',
            })
    trend_rows.sort(key=lambda item: (item['postedAt'], item['viewsValue']), reverse=True)
    all_game_counts = Counter(row['game'] for row in coverage_rows if row.get('game'))
    most_covered_game, most_covered_count = ('No creator match yet', 0)
    if all_game_counts:
        most_covered_game, most_covered_count = all_game_counts.most_common(1)[0]
    breakout_candidates = coverage_rows + trend_rows
    breakout = max(breakout_candidates, key=lambda item: item.get('viewsValue', 0), default=None)
    theme_counter = Counter()
    for row in coverage_rows:
        theme_counter[row['segment']] += 1
    for row in trend_rows:
        theme_counter[row['bucket']] += 1
    theme_label, theme_count = ('No trend yet', 0)
    if theme_counter:
        theme_label, theme_count = theme_counter.most_common(1)[0]
    cards = [
        {
            'title': 'Most Covered New Game',
            'primary': most_covered_game,
            'meta': 'Tracked creator coverage',
            'detail': f'{most_covered_count} creator matches this week' if most_covered_count else 'No creator matches yet',
        },
        {
            'title': 'Biggest Breakout Video',
            'primary': (f"{breakout.get('creator', '')} • {breakout.get('game', '')}".strip(' •') if breakout else 'No breakout yet'),
            'meta': breakout.get('platform', breakout.get('bucket', '')) if breakout else '',
            'detail': f"{breakout.get('views')} views • {breakout.get('posted')}" if breakout else 'Waiting for source data',
        },
        {
            'title': 'Most Repeated Theme',
            'primary': theme_label,
            'meta': 'Recurring across creator sources',
            'detail': f'{theme_count} rows this week' if theme_count else 'No repeated theme yet',
        },
    ]
    signals = [f'{game} • {count} creators' for game, count in all_game_counts.most_common(6)]
    return {
        'cards': cards,
        'coverage': coverage_rows,
        'trends': trend_rows[:10],
        'signals': signals,
    }
def build_dashboard_payload() -> Dict[str, Any]:
    snapshots = load_snapshots()
    built = build_rows_and_history(snapshots)
    creator_momentum = build_creator_momentum(snapshots, built['rows'])
    save_snapshot('youtube_creators', creator_momentum['coverage'], 'dashboard-generator-youtube-rss-watchlist')
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
        'creatorMomentum': creator_momentum,
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
    print(f"Creator coverage rows: {len(payload['creatorMomentum']['coverage'])}")
    print(f"TikTok trend rows: {len(payload['creatorMomentum']['trends'])}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
