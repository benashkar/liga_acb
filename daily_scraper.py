"""
=============================================================================
LIGA ACB DAILY SCRAPER
=============================================================================

PURPOSE:
    This script collects basketball data for Liga ACB from multiple sources:
    - TheSportsDB API: Teams, players, schedule
    - Eurobasket.com: Box scores with player statistics

WHAT IT DOES:
    1. Fetches all clubs (teams) in Liga ACB
    2. Fetches all players with their nationality information
    3. Identifies American players (nationality 'United States')
    4. Fetches game schedules and scores
    5. Fetches box scores from eurobasket.com for player stats
    6. Saves everything to JSON files for further processing

HOW TO USE:
    python daily_scraper.py              # Full scrape
    python daily_scraper.py --no-boxscores  # Skip box score fetching

OUTPUT FILES (saved to output/json/):
    - clubs_TIMESTAMP.json: All Liga ACB teams
    - players_TIMESTAMP.json: All players in the league
    - american_players_TIMESTAMP.json: Just American players
    - schedule_TIMESTAMP.json: Game schedule with scores
    - american_performances_TIMESTAMP.json: Box score stats for Americans
    - american_player_stats_TIMESTAMP.json: Season averages

DATA SOURCES:
    TheSportsDB API: https://www.thesportsdb.com/api.php
    Eurobasket.com: https://www.eurobasket.com/Spain/basketball.aspx
"""

# =============================================================================
# IMPORTS
# =============================================================================
import argparse
import json
import os
import re
import requests
from datetime import datetime, timedelta
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
# CONFIGURATION CONSTANTS
# =============================================================================
# TheSportsDB API base URL (free tier uses key '3')
BASE_URL = 'https://www.thesportsdb.com/api/v1/json/3'

# Liga ACB League ID in TheSportsDB
LEAGUE_ID = '4408'

# Current season (format: YYYY-YYYY)
SEASON = '2025-2026'

# American nationality identifier
AMERICAN_NATIONALITY = 'United States'

# Eurobasket.com configuration
EUROBASKET_BASE = 'https://www.eurobasket.com'
EUROBASKET_BOXSCORE_URL = 'https://www.eurobasket.com/boxScores/Spain/{year}/{date}_{team1}_{team2}.aspx'
EUROBASKET_SCHEDULE_URL = 'https://www.eurobasket.com/Spain/games-schedule.aspx'

# Team ID mapping for eurobasket.com URLs
# These are the numeric IDs used in eurobasket.com box score URLs
EUROBASKET_TEAM_IDS = {
    'FC Barcelona Basquet': '100',
    'Barcelona': '100',
    'Real Madrid Baloncesto': '101',
    'Real Madrid': '101',
    'Valencia Basket': '145',
    'Valencia': '145',
    'Baskonia': '108',
    'Saski Baskonia': '108',
    'Joventut Badalona': '95',
    'Joventut': '95',
    'Unicaja': '102',
    'Baloncesto Malaga': '102',
    'CB Gran Canaria': '215',
    'Gran Canaria': '215',
    'Bilbao Basket': '1324',
    'Bilbao': '1324',
    'Basket Zaragoza': '1998',
    'Zaragoza': '1998',
    'CB Murcia': '3016',
    'Murcia': '3016',
    'Basquet Manresa': '216',
    'Manresa': '216',
    'CB Breogan': '259',
    'Breogan': '259',
    'Fundacion CB Granada': '403',
    'Granada': '403',
    'BC Andorra': '2861',
    'Andorra': '2861',
    'CB 1939 Canarias': '402',
    'Tenerife': '402',
    'Basquet Girona': '3269',
    'Girona': '3269',
    'Forca Lleida CE': '3343',
    'Lleida': '3343',
    'CB San Pablo Burgos': '3091',
    'Burgos': '3091',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_american(nationality):
    """
    Check if a player is American based on their nationality.

    PARAMETERS:
        nationality (str or None): The player's nationality string

    RETURNS:
        bool: True if American, False otherwise
    """
    if not nationality:
        return False
    return nationality.lower() in ['united states', 'usa', 'american']


def save_json(data, filename):
    """
    Save a Python dictionary to a JSON file.

    PARAMETERS:
        data (dict): The data to save
        filename (str): The name of the file

    RETURNS:
        str: The full file path where the data was saved
    """
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Saved: {filepath}")
    return filepath


def api_get(endpoint, params=None):
    """
    Make a GET request to TheSportsDB API.

    PARAMETERS:
        endpoint (str): The API endpoint (e.g., '/lookup_all_teams.php')
        params (dict, optional): Query parameters

    RETURNS:
        dict or None: The JSON response, or None if error
    """
    url = f"{BASE_URL}{endpoint}"

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"API error {endpoint}: {e}")
        return None


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

def fetch_clubs():
    """
    Fetch all clubs (teams) in Liga ACB.

    RETURNS:
        list: A list of club dictionaries
    """
    logger.info("Fetching clubs...")

    # First try to get teams from the league lookup
    data = api_get('/search_all_teams.php', {'l': 'Spanish Liga ACB'})

    if data and data.get('teams'):
        clubs = data.get('teams', [])
        logger.info(f"  Found {len(clubs)} clubs")
        return clubs

    # Fallback: search for known Liga ACB teams
    logger.info("  Trying fallback team search...")
    known_teams = [
        'Real Madrid Baloncesto', 'Barcelona Basquet', 'Valencia Basket',
        'Unicaja', 'Baskonia', 'Joventut Badalona', 'Bilbao Basket',
        'Gran Canaria', 'Zaragoza Basket', 'Manresa', 'Murcia',
        'Girona', 'Breogan', 'Granada', 'Andorra', 'Fuenlabrada'
    ]

    clubs = []
    for team_name in known_teams:
        data = api_get('/searchteams.php', {'t': team_name})
        if data and data.get('teams'):
            for team in data['teams']:
                if team.get('strSport') == 'Basketball' and team.get('strCountry') == 'Spain':
                    clubs.append(team)
                    break
        time.sleep(0.3)  # Rate limiting

    logger.info(f"  Found {len(clubs)} clubs via search")
    return clubs


def fetch_players_for_team(team_id, team_name):
    """
    Fetch all players for a specific team.

    PARAMETERS:
        team_id (str): The team's ID in TheSportsDB
        team_name (str): The team's name (for logging)

    RETURNS:
        list: A list of player dictionaries
    """
    data = api_get('/lookup_all_players.php', {'id': team_id})

    if data and data.get('player'):
        players = data.get('player', [])
        logger.info(f"    {team_name}: {len(players)} players")
        return players

    return []


def fetch_all_players(clubs):
    """
    Fetch all players from all teams.

    PARAMETERS:
        clubs (list): List of club dictionaries

    RETURNS:
        list: A list of all player dictionaries
    """
    logger.info("Fetching players from all teams...")

    all_players = []
    for club in clubs:
        team_id = club.get('idTeam')
        team_name = club.get('strTeam', 'Unknown')

        if team_id:
            players = fetch_players_for_team(team_id, team_name)
            # Add team info to each player
            for player in players:
                player['team_id'] = team_id
                player['team_name'] = team_name
            all_players.extend(players)
            time.sleep(0.3)  # Rate limiting

    logger.info(f"  Total players: {len(all_players)}")
    return all_players


def fetch_schedule():
    """
    Fetch the game schedule for the current season.

    RETURNS:
        list: A list of game dictionaries
    """
    logger.info("Fetching schedule...")

    data = api_get('/eventsseason.php', {'id': LEAGUE_ID, 's': SEASON})

    if data and data.get('events'):
        games = data.get('events', [])
        logger.info(f"  Found {len(games)} games")
        return games

    # Try previous season format if current fails
    alt_season = '2024-2025'
    data = api_get('/eventsseason.php', {'id': LEAGUE_ID, 's': alt_season})

    if data and data.get('events'):
        games = data.get('events', [])
        logger.info(f"  Found {len(games)} games (season {alt_season})")
        return games

    return []


# =============================================================================
# DATA PROCESSING FUNCTIONS
# =============================================================================

def process_clubs(clubs):
    """
    Process raw club data into a clean format.
    """
    processed = []
    for club in clubs:
        processed.append({
            'id': club.get('idTeam'),
            'name': club.get('strTeam'),
            'short_name': club.get('strTeamShort'),
            'founded': club.get('intFormedYear'),
            'stadium': club.get('strStadium'),
            'stadium_capacity': club.get('intStadiumCapacity'),
            'location': club.get('strLocation'),
            'country': club.get('strCountry'),
            'badge_url': club.get('strBadge'),
            'logo_url': club.get('strLogo'),
            'website': club.get('strWebsite'),
            'description': club.get('strDescriptionEN'),
        })
    return processed


def process_players(players):
    """
    Process raw player data into a clean format.
    """
    processed = []
    for player in players:
        # Parse height (format: "2.01 m" or "6 ft 7 in")
        height_str = player.get('strHeight', '')
        height_cm = None
        if height_str:
            try:
                if 'm' in height_str.lower():
                    # Metric format: "2.01 m"
                    height_m = float(height_str.lower().replace('m', '').strip())
                    height_cm = int(height_m * 100)
                elif 'ft' in height_str.lower():
                    # Imperial format: "6 ft 7 in"
                    parts = height_str.lower().replace('ft', '').replace('in', '').split()
                    if len(parts) >= 2:
                        feet = int(parts[0])
                        inches = int(parts[1])
                        height_cm = int((feet * 12 + inches) * 2.54)
            except:
                pass

        # Convert height to feet/inches
        height_feet = None
        height_inches = None
        if height_cm:
            total_inches = height_cm / 2.54
            height_feet = int(total_inches // 12)
            height_inches = int(round(total_inches % 12))
            if height_inches == 12:
                height_feet += 1
                height_inches = 0

        processed.append({
            'code': player.get('idPlayer'),
            'name': player.get('strPlayer'),
            'nationality': player.get('strNationality'),
            'birth_date': player.get('dateBorn', '')[:10] if player.get('dateBorn') else None,
            'birth_location': player.get('strBirthLocation'),
            'height_str': height_str,
            'height_cm': height_cm,
            'height_feet': height_feet,
            'height_inches': height_inches,
            'weight': player.get('strWeight'),
            'position': player.get('strPosition'),
            'team_code': player.get('team_id'),
            'team_name': player.get('team_name'),
            'jersey': player.get('strNumber'),
            'headshot_url': player.get('strThumb') or player.get('strCutout'),
            'description': player.get('strDescriptionEN'),
            'instagram': player.get('strInstagram'),
            'twitter': player.get('strTwitter'),
        })
    return processed


def process_schedule(games):
    """
    Process raw schedule data into a clean format.
    """
    processed = []
    for game in games:
        # Determine if game is played based on score
        home_score = game.get('intHomeScore')
        away_score = game.get('intAwayScore')
        played = home_score is not None and away_score is not None

        processed.append({
            'game_id': game.get('idEvent'),
            'date': game.get('dateEvent'),
            'time': game.get('strTime'),
            'round': game.get('intRound'),
            'home_team': game.get('strHomeTeam'),
            'away_team': game.get('strAwayTeam'),
            'home_score': int(home_score) if home_score else None,
            'away_score': int(away_score) if away_score else None,
            'played': played,
            'venue': game.get('strVenue'),
            'city': game.get('strCity'),
            'season': game.get('strSeason'),
            'status': game.get('strStatus'),
            'result': game.get('strResult'),  # Quarter breakdown
        })
    return processed


# =============================================================================
# EUROBASKET.COM BOX SCORE SCRAPING
# =============================================================================

def get_team_id(team_name):
    """Get eurobasket.com team ID from team name."""
    # Try exact match first
    if team_name in EUROBASKET_TEAM_IDS:
        return EUROBASKET_TEAM_IDS[team_name]

    # Try partial match
    team_lower = team_name.lower()
    for name, tid in EUROBASKET_TEAM_IDS.items():
        if name.lower() in team_lower or team_lower in name.lower():
            return tid

    return None


def fetch_eurobasket_schedule():
    """
    Fetch game schedule from eurobasket.com to get box score URLs.
    Returns list of games with their box score URLs.
    """
    logger.info("Fetching schedule from eurobasket.com...")

    params = {
        'SectionID': '2',
        'League': '1',  # Liga Endesa
        'Season': '2025-2026',
        'LName': 'Spain'
    }

    try:
        resp = requests.get(EUROBASKET_SCHEDULE_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        games = []
        # Find all box score links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '/boxScores/Spain/' in href:
                games.append({
                    'boxscore_url': EUROBASKET_BASE + href if href.startswith('/') else href
                })

        logger.info(f"  Found {len(games)} box score links")
        return games

    except Exception as e:
        logger.error(f"Error fetching eurobasket schedule: {e}")
        return []


def parse_boxscore_page(html, game_url):
    """
    Parse a eurobasket.com box score page.
    Returns list of player performances.

    Note: eurobasket.com obfuscates player names in the displayed text,
    but the real names are in the href URLs (e.g., /player/Miles-Norris/442259)
    """
    soup = BeautifulSoup(html, 'html.parser')
    performances = []

    # Find all tables
    tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')

        # Skip tables with too few rows
        if len(rows) < 4:
            continue

        # Look for header row with column names (usually row 1 or 2)
        col_map = {}
        header_row_idx = -1

        for row_idx, row in enumerate(rows[:3]):
            cells = row.find_all(['td', 'th'])
            for idx, cell in enumerate(cells):
                text = cell.get_text(strip=True).upper()
                if text == 'MIN':
                    col_map['minutes'] = idx
                    header_row_idx = row_idx
                elif text == 'PT' or text == 'PTS':
                    col_map['points'] = idx
                elif text == 'RB' or text == 'REB':
                    col_map['rebounds'] = idx
                elif text == 'AS' or text == 'AST':
                    col_map['assists'] = idx
                elif text == 'ST' or text == 'STL':
                    col_map['steals'] = idx
                elif text == 'TO':
                    col_map['turnovers'] = idx

        # Skip if no valid header found
        if not col_map or header_row_idx < 0:
            continue

        # Parse player rows (after header)
        for row in rows[header_row_idx + 1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 5:
                continue

            # Extract player name from href URL (real names are there)
            player_link = row.find('a', href=lambda x: x and '/player/' in str(x))
            if not player_link:
                continue

            href = player_link.get('href', '')
            name_match = re.search(r'/player/([^/]+)/', href)
            if not name_match:
                continue

            player_name = name_match.group(1).replace('-', ' ')

            # Skip totals row
            if 'total' in player_name.lower():
                continue

            perf = {
                'player_name': player_name,
                'game_url': game_url,
            }

            # Extract stats based on column positions
            try:
                for stat_name, col_idx in col_map.items():
                    if col_idx < len(cells):
                        cell_text = cells[col_idx].get_text(strip=True)
                        # Handle "XX (YY%)" format
                        cell_text = cell_text.split('(')[0].strip()
                        # Handle "X-Y" format (made-attempted) - we don't want this for stats
                        if '-' in cell_text:
                            continue  # Skip shooting stats format
                        if cell_text.isdigit():
                            perf[stat_name] = int(cell_text)
            except Exception as e:
                logger.debug(f"Error parsing stats: {e}")

            # Only add if we got some stats
            if perf.get('points') is not None or perf.get('minutes') is not None:
                performances.append(perf)

    return performances


def fetch_boxscore(url):
    """
    Fetch and parse a single box score from eurobasket.com.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return parse_boxscore_page(resp.text, url)
    except Exception as e:
        logger.debug(f"Error fetching boxscore {url}: {e}")
        return []


def fetch_all_boxscores(games, american_players):
    """
    Fetch box scores for all played games and extract American player performances.

    PARAMETERS:
        games: List of game dictionaries with date, home_team, away_team
        american_players: List of American player dictionaries

    RETURNS:
        List of performance dictionaries for American players
    """
    logger.info("Fetching box scores from eurobasket.com...")

    # Build set of American player names for matching
    american_names = set()
    for p in american_players:
        name = p.get('name', '')
        american_names.add(name.lower())
        # Also add variations
        parts = name.split()
        if len(parts) >= 2:
            american_names.add(f"{parts[-1]}, {parts[0]}".lower())  # Last, First
            american_names.add(parts[-1].lower())  # Just last name

    all_performances = []

    # Get box score URLs from eurobasket schedule
    eurobasket_games = fetch_eurobasket_schedule()

    # Fetch each box score
    for i, game in enumerate(eurobasket_games[:50]):  # Limit to 50 games
        url = game.get('boxscore_url')
        if not url:
            continue

        if (i + 1) % 10 == 0:
            logger.info(f"  Progress: {i+1}/{len(eurobasket_games[:50])}")

        performances = fetch_boxscore(url)

        # Filter to American players
        for perf in performances:
            player_name = perf.get('player_name', '').lower()

            # Check if this is an American player
            is_american = False
            for am_name in american_names:
                if am_name in player_name or player_name in am_name:
                    is_american = True
                    break

            if is_american:
                all_performances.append(perf)

        time.sleep(0.3)  # Rate limiting

    logger.info(f"  Found {len(all_performances)} American player performances")
    return all_performances


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """
    Main entry point for the scraper.
    """
    parser = argparse.ArgumentParser(description='Liga ACB Daily Scraper')
    parser.add_argument('--teams-only', action='store_true',
                       help='Only fetch teams')
    parser.add_argument('--players-only', action='store_true',
                       help='Only fetch players')
    parser.add_argument('--schedule-only', action='store_true',
                       help='Only fetch schedule')
    parser.add_argument('--no-boxscores', action='store_true',
                       help='Skip fetching box scores')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("LIGA ACB DAILY SCRAPER")
    logger.info("=" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # =========================================================================
    # Step 1: Fetch Clubs
    # =========================================================================
    clubs = fetch_clubs()
    processed_clubs = process_clubs(clubs)

    if clubs:
        save_json({
            'export_date': datetime.now().isoformat(),
            'season': SEASON,
            'league': 'Liga ACB',
            'league_id': LEAGUE_ID,
            'count': len(processed_clubs),
            'clubs': processed_clubs
        }, f'clubs_{timestamp}.json')

    if args.teams_only:
        return

    # =========================================================================
    # Step 2: Fetch Players
    # =========================================================================
    all_players_raw = fetch_all_players(clubs)
    all_players = process_players(all_players_raw)

    # Identify American players
    american_players = [p for p in all_players if is_american(p.get('nationality'))]

    logger.info(f"  American players: {len(american_players)}")

    # Save all players
    save_json({
        'export_date': datetime.now().isoformat(),
        'season': SEASON,
        'league': 'Liga ACB',
        'count': len(all_players),
        'players': all_players
    }, f'players_{timestamp}.json')

    # Save American players
    save_json({
        'export_date': datetime.now().isoformat(),
        'season': SEASON,
        'league': 'Liga ACB',
        'count': len(american_players),
        'players': american_players
    }, f'american_players_{timestamp}.json')

    if args.players_only:
        return

    # =========================================================================
    # Step 3: Fetch Schedule
    # =========================================================================
    games_raw = fetch_schedule()
    games = process_schedule(games_raw)

    played_games = [g for g in games if g.get('played')]
    upcoming_games = [g for g in games if not g.get('played')]

    logger.info(f"  Played: {len(played_games)}, Upcoming: {len(upcoming_games)}")

    save_json({
        'export_date': datetime.now().isoformat(),
        'season': SEASON,
        'league': 'Liga ACB',
        'total_games': len(games),
        'played': len(played_games),
        'upcoming': len(upcoming_games),
        'games': games
    }, f'schedule_{timestamp}.json')

    if args.schedule_only:
        return

    # =========================================================================
    # Step 4: Fetch Box Scores from eurobasket.com
    # =========================================================================
    all_american_performances = []

    if not args.no_boxscores and played_games:
        all_american_performances = fetch_all_boxscores(played_games, american_players)

        if all_american_performances:
            # Save raw performances
            save_json({
                'export_date': datetime.now().isoformat(),
                'season': SEASON,
                'league': 'Liga ACB',
                'performance_count': len(all_american_performances),
                'performances': all_american_performances
            }, f'american_performances_{timestamp}.json')

            # Calculate season averages
            player_stats = {}
            for perf in all_american_performances:
                name = perf.get('player_name', 'Unknown')

                if name not in player_stats:
                    player_stats[name] = {
                        'player_name': name,
                        'games_played': 0,
                        'total_points': 0,
                        'total_rebounds': 0,
                        'total_assists': 0,
                        'performances': []
                    }

                ps = player_stats[name]
                ps['games_played'] += 1
                ps['total_points'] += perf.get('points', 0) or 0
                ps['total_rebounds'] += perf.get('rebounds', 0) or 0
                ps['total_assists'] += perf.get('assists', 0) or 0
                ps['performances'].append(perf)

            # Calculate averages
            for ps in player_stats.values():
                gp = ps['games_played']
                if gp > 0:
                    ps['ppg'] = round(ps['total_points'] / gp, 1)
                    ps['rpg'] = round(ps['total_rebounds'] / gp, 1)
                    ps['apg'] = round(ps['total_assists'] / gp, 1)

            # Sort by PPG
            player_summary = sorted(player_stats.values(),
                                   key=lambda x: x.get('ppg', 0),
                                   reverse=True)

            save_json({
                'export_date': datetime.now().isoformat(),
                'season': SEASON,
                'league': 'Liga ACB',
                'player_count': len(player_summary),
                'players': player_summary
            }, f'american_player_stats_{timestamp}.json')

    # =========================================================================
    # Summary
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Clubs: {len(processed_clubs)}")
    logger.info(f"Total players: {len(all_players)}")
    logger.info(f"American players: {len(american_players)}")
    logger.info(f"Games: {len(games)} (played: {len(played_games)}, upcoming: {len(upcoming_games)})")
    logger.info(f"American performances: {len(all_american_performances)}")

    if american_players:
        logger.info("\nAmerican players found:")
        for p in american_players[:10]:  # Show first 10
            logger.info(f"  {p['name']} - {p['team_name']} ({p['position']})")


if __name__ == '__main__':
    main()
