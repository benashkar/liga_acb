"""
=============================================================================
ACB.COM SCRAPER - LIGA ACB PLAYER STATISTICS
=============================================================================

PURPOSE:
    Scrape player statistics directly from the official ACB website.
    Gets accurate box scores and season stats for all players.

DATA SOURCE:
    https://www.acb.com - Official Liga ACB website

OUTPUT FILES:
    - acb_rosters_TIMESTAMP.json: All teams with player rosters
    - acb_american_players_TIMESTAMP.json: American players with stats
    - acb_boxscores_TIMESTAMP.json: Game-by-game box scores
"""

import json
import os
import re
import requests
from datetime import datetime
import logging
import time
from bs4 import BeautifulSoup

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================
ACB_BASE_URL = 'https://www.acb.com'
SEASON_ID = '2025'  # ACB uses single year for season ID

# Known American players from TheSportsDB (name variations for matching)
KNOWN_AMERICAN_PLAYERS = [
    'David Kravish', 'James Webb', 'Tyler Kalinoski', 'D.J. Stephens', 'DJ Stephens',
    'Jahlil Okafor', 'Chris Chiozza', 'Trent Forrest', 'Grant Golden', 'Ben Lammers',
    'Clevin Hannah', 'Spencer Butterfield', 'John Shurna', 'Thad McFadden',
    'Troy Caupain', 'Alex Renfroe', 'Ethan Happ', 'Obi Enechionyia', 'Kevin Punter',
    'Miles Norris', 'Myles Cale', 'Matt Thomas', 'Devon Dotson', 'Chuma Okeke',
    'Braxton Key', 'Darius Thompson', 'Kameron Taylor', 'Nathan Reuvers', 'Omari Moore',
    # Additional variations
    'Will Clyburn', 'Sergio Llull',  # Just in case
]

# ACB Team IDs (from ACB website)
ACB_TEAMS = {
    1: 'Unicaja',
    2: 'Valencia Basket',
    3: 'Joventut Badalona',
    4: 'Baskonia',
    5: 'Dreamland Gran Canaria',
    6: 'CB Breogan',
    7: 'BAXI Manresa',
    8: 'Surne Bilbao',
    9: 'Real Madrid',
    10: 'Barça',
    11: 'MoraBanc Andorra',
    12: 'UCAM Murcia',
    13: 'Coviran Granada',
    14: 'La Laguna Tenerife',
    15: 'Casademont Zaragoza',
    16: 'Basquet Girona',
    17: 'Hiopos Lleida',
    18: 'Rio Breogan',
}


def normalize_name(name):
    """Normalize player name for matching."""
    if not name:
        return ''
    # Remove accents and special chars, lowercase
    import unicodedata
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    return name.lower().strip()


def is_known_american(name):
    """Check if player name matches a known American player."""
    name_norm = normalize_name(name)
    for american in KNOWN_AMERICAN_PLAYERS:
        american_norm = normalize_name(american)
        # Check for partial matches
        if american_norm in name_norm or name_norm in american_norm:
            return True
        # Check last name match
        american_parts = american_norm.split()
        name_parts = name_norm.split()
        if american_parts and name_parts:
            if american_parts[-1] == name_parts[-1] and len(american_parts[-1]) > 3:
                return True
    return False

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


def save_json(data, filename):
    """Save data to JSON file."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Saved: {filepath}")
    return filepath


def fetch_page(url, retries=3):
    """Fetch a page with retry logic."""
    for attempt in range(retries):
        try:
            if attempt > 0:
                time.sleep(2 ** attempt)

            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            time.sleep(0.5)  # Rate limiting
            return resp.text

        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}/{retries} failed for {url}: {e}")
            if attempt == retries - 1:
                logger.error(f"Failed to fetch {url}")
                return None

    return None


def fetch_team_roster(team_id):
    """
    Fetch roster for a team from ACB website.
    Returns list of player IDs and names.
    """
    url = f"{ACB_BASE_URL}/club/plantilla/id/{team_id}/temporada_id/{SEASON_ID}"
    html = fetch_page(url)

    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    players = []
    seen_ids = set()

    # Find player links
    for player_link in soup.find_all('a', href=re.compile(r'/jugador/ver/\d+')):
        try:
            href = player_link.get('href', '')
            player_id_match = re.search(r'/jugador/ver/(\d+)', href)
            if not player_id_match:
                continue

            player_id = player_id_match.group(1)
            if player_id in seen_ids:
                continue
            seen_ids.add(player_id)

            name = player_link.get_text(strip=True)
            if not name or len(name) < 2:
                continue

            players.append({
                'acb_id': player_id,
                'name': name,
                'team_id': team_id,
            })

        except Exception as e:
            logger.debug(f"Error parsing player: {e}")

    return players


def fetch_player_details(player_id):
    """
    Fetch detailed player info from individual player page.
    Returns dict with nationality, position, stats, etc.
    """
    url = f"{ACB_BASE_URL}/jugador/ver/{player_id}/temporada_id/{SEASON_ID}"
    html = fetch_page(url)

    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    details = {'acb_id': player_id}

    # Get full page text for parsing
    page_text = soup.get_text()

    # Extract nationality - look for country patterns
    nationality_patterns = [
        r'EE\.UU\.|USA|Estados Unidos|United States',
        r'Espa[ñn]a|Spain',
        r'Francia|France',
        r'Serbia',
        r'Croacia|Croatia',
        r'Argentina',
        r'Italia|Italy',
    ]

    for pattern in nationality_patterns:
        if re.search(pattern, page_text, re.IGNORECASE):
            if 'EE.UU' in page_text or 'USA' in page_text or 'Estados Unidos' in page_text:
                details['nationality'] = 'USA'
                break
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                details['nationality'] = match.group(0)
                break

    # Look for specific data patterns
    # Height
    height_match = re.search(r'(\d[,\.]\d{2})\s*m', page_text)
    if height_match:
        details['height'] = height_match.group(1).replace(',', '.')

    # Jersey
    jersey_match = re.search(r'Dorsal[:\s]*(\d+)', page_text, re.IGNORECASE)
    if jersey_match:
        details['jersey'] = jersey_match.group(1)

    # Position
    position_patterns = ['Base', 'Escolta', 'Alero', 'Ala-Pívot', 'Pívot', 'Guard', 'Forward', 'Center']
    for pos in position_patterns:
        if pos.lower() in page_text.lower():
            details['position'] = pos
            break

    # Stats - look for statistics table
    # Games, Points, Rebounds, Assists
    games_match = re.search(r'Partidos[:\s]*(\d+)', page_text, re.IGNORECASE)
    if games_match:
        details['games_played'] = int(games_match.group(1))

    # Look for average stats (format: X.X or X,X)
    stats_section = soup.find('div', class_=re.compile(r'stats|estadisticas'))
    if stats_section:
        stats_text = stats_section.get_text()
    else:
        stats_text = page_text

    # Extract PPG, RPG, APG from common patterns
    ppg_match = re.search(r'Puntos[^0-9]*(\d+[,\.]\d)', stats_text, re.IGNORECASE)
    if ppg_match:
        details['ppg'] = float(ppg_match.group(1).replace(',', '.'))

    rpg_match = re.search(r'Rebotes[^0-9]*(\d+[,\.]\d)', stats_text, re.IGNORECASE)
    if rpg_match:
        details['rpg'] = float(rpg_match.group(1).replace(',', '.'))

    apg_match = re.search(r'Asistencias[^0-9]*(\d+[,\.]\d)', stats_text, re.IGNORECASE)
    if apg_match:
        details['apg'] = float(apg_match.group(1).replace(',', '.'))

    return details


def fetch_player_stats(player_id):
    """
    Fetch season statistics for a player from ACB website.
    """
    url = f"{ACB_BASE_URL}/jugador/ver/{player_id}/temporada_id/{SEASON_ID}"
    html = fetch_page(url)

    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    stats = {'acb_id': player_id}

    # Extract player basic info
    name_elem = soup.find(['h1', 'h2'], class_=re.compile(r'nombre|name|titulo'))
    if name_elem:
        stats['name'] = name_elem.get_text(strip=True)

    # Find stats table
    stats_table = soup.find('table', class_=re.compile(r'estadisticas|stats'))
    if not stats_table:
        # Try finding any table with stats
        for table in soup.find_all('table'):
            text = table.get_text().lower()
            if 'puntos' in text or 'points' in text or 'min' in text:
                stats_table = table
                break

    if stats_table:
        rows = stats_table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[-1].get_text(strip=True)

                # Map Spanish labels to stats
                if 'partidos' in label or 'games' in label:
                    try:
                        stats['games_played'] = int(value)
                    except:
                        pass
                elif 'minutos' in label or 'min' in label:
                    stats['minutes'] = value
                elif 'puntos' in label or 'points' in label:
                    try:
                        stats['ppg'] = float(value.replace(',', '.'))
                    except:
                        pass
                elif 'rebotes' in label or 'rebounds' in label:
                    try:
                        stats['rpg'] = float(value.replace(',', '.'))
                    except:
                        pass
                elif 'asistencias' in label or 'assists' in label:
                    try:
                        stats['apg'] = float(value.replace(',', '.'))
                    except:
                        pass
                elif 'valoracion' in label or 'rating' in label:
                    try:
                        stats['rating'] = float(value.replace(',', '.'))
                    except:
                        pass

    return stats


def fetch_box_score(match_id):
    """
    Fetch box score for a single game from ACB website.
    """
    url = f"{ACB_BASE_URL}/partido/estadisticas/id/{match_id}"
    html = fetch_page(url)

    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    box_score = {
        'match_id': match_id,
        'players': []
    }

    # Find all player rows in stats tables
    tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')

        # Look for header row to get column indices
        header_row = None
        col_map = {}

        for row in rows:
            cells = row.find_all(['th', 'td'])
            cell_texts = [c.get_text(strip=True).upper() for c in cells]

            # Check if this is a header row
            if 'MIN' in cell_texts or 'PTS' in cell_texts:
                header_row = row
                for idx, text in enumerate(cell_texts):
                    if text == 'MIN':
                        col_map['minutes'] = idx
                    elif text in ['PTS', 'PT', 'P']:
                        col_map['points'] = idx
                    elif text in ['REB', 'RT', 'R']:
                        col_map['rebounds'] = idx
                    elif text in ['AST', 'AS', 'A']:
                        col_map['assists'] = idx
                    elif text in ['ROB', 'ST']:
                        col_map['steals'] = idx
                    elif text in ['TAP', 'BL']:
                        col_map['blocks'] = idx
                    elif text in ['VAL', 'PIR']:
                        col_map['rating'] = idx
                continue

            # Skip if we haven't found header yet
            if not col_map:
                continue

            # Parse player row
            cells = row.find_all(['td', 'th'])
            if len(cells) < 5:
                continue

            # Find player name/link
            player_link = row.find('a', href=re.compile(r'/jugador/'))
            if player_link:
                href = player_link.get('href', '')
                player_id_match = re.search(r'/jugador/ver/(\d+)', href)
                player_name = player_link.get_text(strip=True)

                if not player_name or 'total' in player_name.lower():
                    continue

                player_stats = {
                    'name': player_name,
                    'acb_id': player_id_match.group(1) if player_id_match else None,
                }

                # Extract stats based on column map
                for stat_name, col_idx in col_map.items():
                    if col_idx < len(cells):
                        cell_text = cells[col_idx].get_text(strip=True)
                        # Handle time format MM:SS
                        if stat_name == 'minutes' and ':' in cell_text:
                            player_stats['minutes'] = cell_text
                        else:
                            try:
                                player_stats[stat_name] = int(cell_text)
                            except:
                                try:
                                    player_stats[stat_name] = float(cell_text.replace(',', '.'))
                                except:
                                    pass

                box_score['players'].append(player_stats)

    return box_score


def fetch_season_matches():
    """
    Fetch list of all matches for the current season.
    Returns list of match IDs.
    """
    matches = []

    # Fetch calendar page
    for jornada in range(1, 35):  # 34 regular season rounds
        url = f"{ACB_BASE_URL}/calendario/index/temporada_id/{SEASON_ID}/competicion_id/1/jornada_numero/{jornada}"
        html = fetch_page(url)

        if not html:
            continue

        soup = BeautifulSoup(html, 'html.parser')

        # Find match links
        for link in soup.find_all('a', href=re.compile(r'/partido/estadisticas/id/\d+')):
            href = link.get('href', '')
            match_id_match = re.search(r'/partido/estadisticas/id/(\d+)', href)
            if match_id_match:
                match_id = match_id_match.group(1)
                if match_id not in [m['match_id'] for m in matches]:
                    matches.append({
                        'match_id': match_id,
                        'jornada': jornada,
                    })

        logger.info(f"  Jornada {jornada}: {len(matches)} total matches")
        time.sleep(0.3)

    return matches


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("ACB.COM SCRAPER")
    logger.info("=" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Skip roster scraping (doesn't work well) - we'll find Americans from box scores
    all_players = []
    american_players = []

    # =========================================================================
    # Step 1: Fetch Box Scores and Find Americans
    # =========================================================================
    logger.info("Fetching match list...")
    matches = fetch_season_matches()
    logger.info(f"Found {len(matches)} matches")

    # Fetch box scores for first 20 matches (to avoid rate limiting)
    logger.info("Fetching box scores...")
    box_scores = []
    american_performances = []

    # Get IDs from confirmed Americans AND match by name from box scores
    american_ids = set(p.get('acb_id') for p in american_players if p.get('acb_id'))

    for i, match in enumerate(matches[:50]):  # Get more games
        match_id = match['match_id']
        box_score = fetch_box_score(match_id)

        if box_score and box_score.get('players'):
            box_scores.append(box_score)

            # Extract American player performances by ID or name
            for player_stat in box_score['players']:
                player_name = player_stat.get('name', '')
                is_american = player_stat.get('acb_id') in american_ids or is_known_american(player_name)

                if is_american:
                    player_stat['match_id'] = match_id
                    player_stat['jornada'] = match.get('jornada')
                    american_performances.append(player_stat)

                    # Also add to american_players if not already there
                    acb_id = player_stat.get('acb_id')
                    if acb_id and acb_id not in american_ids:
                        american_ids.add(acb_id)
                        # Add to american_players list
                        american_players.append({
                            'acb_id': acb_id,
                            'name': player_name,
                            'nationality': 'USA (matched)',
                        })

        if (i + 1) % 10 == 0:
            logger.info(f"  Progress: {i+1}/{min(30, len(matches))}")

        time.sleep(0.5)

    # =========================================================================
    # Step 5: Aggregate Player Stats
    # =========================================================================
    player_game_logs = {}
    for perf in american_performances:
        acb_id = perf.get('acb_id')
        if acb_id:
            if acb_id not in player_game_logs:
                player_game_logs[acb_id] = []
            player_game_logs[acb_id].append(perf)

    # Update American players with game logs
    for player in american_players:
        acb_id = player.get('acb_id')
        if acb_id and acb_id in player_game_logs:
            player['game_log'] = player_game_logs[acb_id]
            player['games_tracked'] = len(player_game_logs[acb_id])

            # Calculate averages from game log
            games = player_game_logs[acb_id]
            if games:
                total_pts = sum(g.get('points', 0) or 0 for g in games)
                total_reb = sum(g.get('rebounds', 0) or 0 for g in games)
                total_ast = sum(g.get('assists', 0) or 0 for g in games)
                n = len(games)
                player['calculated_ppg'] = round(total_pts / n, 1)
                player['calculated_rpg'] = round(total_reb / n, 1)
                player['calculated_apg'] = round(total_ast / n, 1)

    # =========================================================================
    # Step 6: Save Results
    # =========================================================================
    save_json({
        'export_date': datetime.now().isoformat(),
        'season': '2025-2026',
        'league': 'Liga ACB',
        'player_count': len(all_players),
        'players': all_players
    }, f'acb_rosters_{timestamp}.json')

    save_json({
        'export_date': datetime.now().isoformat(),
        'season': '2025-2026',
        'league': 'Liga ACB',
        'player_count': len(american_players),
        'players': american_players
    }, f'acb_american_players_{timestamp}.json')

    save_json({
        'export_date': datetime.now().isoformat(),
        'season': '2025-2026',
        'league': 'Liga ACB',
        'match_count': len(box_scores),
        'box_scores': box_scores
    }, f'acb_boxscores_{timestamp}.json')

    # =========================================================================
    # Summary
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total players: {len(all_players)}")
    logger.info(f"American players: {len(american_players)}")
    logger.info(f"Matches scraped: {len(box_scores)}")
    logger.info(f"American performances: {len(american_performances)}")

    if american_players:
        logger.info("\nAmerican players:")
        for p in american_players[:15]:
            stats = f"PPG: {p.get('ppg', 'N/A')}, RPG: {p.get('rpg', 'N/A')}, APG: {p.get('apg', 'N/A')}"
            logger.info(f"  {p['name']} - Team {p.get('team_id')} | {stats}")


if __name__ == '__main__':
    main()
