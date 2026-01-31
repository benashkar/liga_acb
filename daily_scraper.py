"""
=============================================================================
LIGA ACB DAILY SCRAPER
=============================================================================

PURPOSE:
    This script collects basketball data from TheSportsDB API for Liga ACB.
    It's designed to track American players in the Spanish Liga ACB for
    local news sites that want to cover hometown players.

WHAT IT DOES:
    1. Fetches all clubs (teams) in Liga ACB
    2. Fetches all players with their nationality information
    3. Identifies American players (nationality 'United States')
    4. Fetches game schedules and scores
    5. Saves everything to JSON files for further processing

NOTE ON BOX SCORES:
    TheSportsDB free tier does not include detailed box scores with player
    game statistics. The dashboard will show player rosters and game results
    but not individual player game logs.

HOW TO USE:
    python daily_scraper.py              # Full scrape

OUTPUT FILES (saved to output/json/):
    - clubs_TIMESTAMP.json: All Liga ACB teams
    - players_TIMESTAMP.json: All players in the league
    - american_players_TIMESTAMP.json: Just American players
    - schedule_TIMESTAMP.json: Game schedule with scores

API DOCUMENTATION:
    TheSportsDB API: https://www.thesportsdb.com/api.php
    Liga ACB League ID: 4408
    Key endpoints used:
    - /lookup_all_teams.php?id=4408 - Get all teams
    - /lookup_all_players.php?id={team_id} - Get players for a team
    - /eventsseason.php?id=4408&s=YYYY-YYYY - Get schedule
"""

# =============================================================================
# IMPORTS
# =============================================================================
import argparse
import json
import os
import requests
from datetime import datetime, timedelta
import logging
import time

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

    if american_players:
        logger.info("\nAmerican players found:")
        for p in american_players[:10]:  # Show first 10
            logger.info(f"  {p['name']} - {p['team_name']} ({p['position']})")


if __name__ == '__main__':
    main()
