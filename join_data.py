"""
=============================================================================
JOIN DATA - LIGA ACB
=============================================================================

PURPOSE:
    Combines data from multiple JSON sources into unified player records.
    This creates the final "database" that the dashboard reads from.

DATA SOURCES COMBINED:
    - american_players_*.json: Basic player info from TheSportsDB
    - american_hometowns_found_*.json: Wikipedia hometown/college data
    - schedule_*.json: Game schedule for upcoming/past games
    - acb_american_players_latest.json: Box score stats from ACB.com

OUTPUT:
    - unified_american_players_*.json: Complete player records with stats
    - american_players_summary_*.json: Lightweight version for dashboard list
"""

import json
import os
from glob import glob
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_latest_json(pattern):
    """Load the most recent JSON file matching the pattern."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    files = sorted(glob(os.path.join(output_dir, pattern)))

    if not files:
        logger.warning(f"No files found matching: {pattern}")
        return None

    filepath = files[-1]
    logger.info(f"Loading: {os.path.basename(filepath)}")

    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_best_schedule():
    """Load the schedule file with the most games (handles rate limiting fallback)."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    files = sorted(glob(os.path.join(output_dir, 'schedule_*.json')))

    if not files:
        logger.warning("No schedule files found")
        return None

    # Find the file with the most games
    best_file = None
    best_count = 0

    for filepath in files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                game_count = len(data.get('games', []))
                if game_count > best_count:
                    best_count = game_count
                    best_file = filepath
        except Exception as e:
            logger.warning(f"Error reading {filepath}: {e}")

    if best_file:
        logger.info(f"Loading schedule: {os.path.basename(best_file)} ({best_count} games)")
        with open(best_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    return None


def save_json(data, filename):
    """Save data to a JSON file."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Saved: {filepath}")


def load_acb_stats():
    """Load ACB.com box score stats for American players."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    filepath = os.path.join(output_dir, 'acb_american_players_latest.json')

    if not os.path.exists(filepath):
        logger.warning("No ACB stats file found. Run acb_scraper.py first.")
        return {}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            players = data.get('players', [])
            logger.info(f"Loaded ACB stats for {len(players)} players")

            # Build lookup by normalized name
            lookup = {}
            for p in players:
                name = p.get('name', '').lower().strip()
                # Handle abbreviated names like "T. Kalinoski" -> "kalinoski"
                if '. ' in name:
                    name = name.split('. ')[-1]
                lookup[name] = p
            return lookup
    except Exception as e:
        logger.warning(f"Error loading ACB stats: {e}")
        return {}


def normalize_name(name):
    """Normalize player name for matching."""
    if not name:
        return ''
    import unicodedata
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    return name.lower().strip()


def match_acb_player(player_name, acb_lookup):
    """Find matching ACB player by name."""
    name_norm = normalize_name(player_name)

    # Try exact match on last name
    parts = name_norm.split()
    if parts:
        last_name = parts[-1]
        if last_name in acb_lookup:
            return acb_lookup[last_name]

    # Try full name match
    for acb_name, acb_data in acb_lookup.items():
        if acb_name in name_norm or name_norm in acb_name:
            return acb_data

    return None


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("LIGA ACB - JOIN DATA")
    logger.info("=" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # =========================================================================
    # Load All Data Sources
    # =========================================================================
    players_data = load_latest_json('american_players_2*.json')  # Excludes summary files
    hometowns_data = load_latest_json('american_hometowns_found_*.json')
    schedule_data = load_best_schedule()  # Uses file with most games (handles rate limit fallback)
    acb_stats = load_acb_stats()  # Box score stats from ACB.com

    if not players_data:
        logger.error("No player data found. Run daily_scraper.py first.")
        return

    players = players_data.get('players', [])
    logger.info(f"Loaded {len(players)} American players")

    # Build hometown lookup dictionary
    hometown_lookup = {}
    if hometowns_data:
        for p in hometowns_data.get('players', []):
            code = p.get('code')
            if code:
                hometown_lookup[code] = p
        logger.info(f"Loaded {len(hometown_lookup)} hometown records")

    # Build all games by team (both past and upcoming)
    past_by_team = {}
    upcoming_by_team = {}
    if schedule_data:
        for game in schedule_data.get('games', []):
            home_team = game.get('home_team')
            away_team = game.get('away_team')
            played = game.get('played', False)

            game_info = {
                'date': game.get('date'),
                'round': game.get('round'),
                'venue': game.get('venue'),
                'home_team': home_team,
                'away_team': away_team,
                'home_score': game.get('home_score'),
                'away_score': game.get('away_score'),
                'played': played,
            }

            # Determine which dict to use based on played status
            target_dict = past_by_team if played else upcoming_by_team

            # Add to home team's schedule
            if home_team:
                if home_team not in target_dict:
                    target_dict[home_team] = []
                target_dict[home_team].append({
                    **game_info,
                    'opponent': away_team,
                    'home_away': 'Home',
                    'team_score': game.get('home_score'),
                    'opponent_score': game.get('away_score'),
                    'result': 'W' if played and game.get('home_score', 0) > game.get('away_score', 0) else ('L' if played else None),
                })

            # Add to away team's schedule
            if away_team:
                if away_team not in target_dict:
                    target_dict[away_team] = []
                target_dict[away_team].append({
                    **game_info,
                    'opponent': home_team,
                    'home_away': 'Away',
                    'team_score': game.get('away_score'),
                    'opponent_score': game.get('home_score'),
                    'result': 'W' if played and game.get('away_score', 0) > game.get('home_score', 0) else ('L' if played else None),
                })

        # Sort each team's games by date
        for team in past_by_team:
            past_by_team[team].sort(key=lambda x: x.get('date', ''), reverse=True)  # Most recent first
        for team in upcoming_by_team:
            upcoming_by_team[team].sort(key=lambda x: x.get('date', ''))

        logger.info(f"Built past games for {len(past_by_team)} teams")
        logger.info(f"Built upcoming games for {len(upcoming_by_team)} teams")

    # =========================================================================
    # Build Unified Player Records
    # =========================================================================
    unified_players = []

    for player in players:
        code = player.get('code')
        player_name = player.get('name', '')

        # Get hometown data if available
        hometown = hometown_lookup.get(code, {})

        # Get games for player's team
        team_name = player.get('team_name')
        past_games = past_by_team.get(team_name, [])  # All past games
        upcoming_games = upcoming_by_team.get(team_name, [])  # All upcoming games

        # Get ACB box score stats if available
        acb_player = match_acb_player(player_name, acb_stats)
        game_log = []
        games_played = 0
        ppg = 0.0
        rpg = 0.0
        apg = 0.0

        if acb_player:
            game_log = acb_player.get('game_log', [])
            games_played = acb_player.get('games_tracked', 0)
            ppg = acb_player.get('calculated_ppg', 0.0)
            rpg = acb_player.get('calculated_rpg', 0.0)
            apg = acb_player.get('calculated_apg', 0.0)
            logger.debug(f"  Matched ACB stats for {player_name}: {games_played} games, {ppg} PPG")

        # Build unified record
        unified = {
            # Basic info
            'code': code,
            'name': player_name,
            'team': team_name,
            'team_code': player.get('team_code'),
            'position': player.get('position'),
            'jersey': player.get('jersey'),

            # Physical attributes
            'height_cm': player.get('height_cm'),
            'height_feet': player.get('height_feet'),
            'height_inches': player.get('height_inches'),
            'weight': player.get('weight'),

            # Personal info
            'birth_date': player.get('birth_date'),
            'nationality': player.get('nationality'),
            'birth_location': player.get('birth_location'),

            # Hometown data from Wikipedia
            'hometown_city': hometown.get('hometown_city'),
            'hometown_state': hometown.get('hometown_state'),
            'hometown': f"{hometown.get('hometown_city')}, {hometown.get('hometown_state')}" if hometown.get('hometown_city') and hometown.get('hometown_state') else None,
            'college': hometown.get('college'),
            'high_school': hometown.get('high_school'),

            # Media
            'headshot_url': player.get('headshot_url'),

            # Social
            'instagram': player.get('instagram'),
            'twitter': player.get('twitter'),

            # Stats from ACB.com box scores
            'games_played': games_played,
            'ppg': ppg,
            'rpg': rpg,
            'apg': apg,
            'game_log': game_log,  # Individual game performances

            # Team schedule
            'past_games': past_games,
            'upcoming_games': upcoming_games,

            # Season info
            'season': '2025-26',
            'league': 'Liga ACB',
        }

        unified_players.append(unified)

    # Sort by name
    unified_players.sort(key=lambda x: x.get('name', ''))

    logger.info(f"Created {len(unified_players)} unified player records")

    # =========================================================================
    # Save Full Unified Data
    # =========================================================================
    unified_data = {
        'export_date': datetime.now().isoformat(),
        'season': '2025-26',
        'league': 'Liga ACB',
        'player_count': len(unified_players),
        'players': unified_players
    }

    save_json(unified_data, f'unified_american_players_{timestamp}.json')
    save_json(unified_data, 'unified_american_players_latest.json')  # For dashboard

    # =========================================================================
    # Save Summary Version (lighter weight for dashboard list)
    # =========================================================================
    summary_players = []
    for p in unified_players:
        summary_players.append({
            'code': p['code'],
            'name': p['name'],
            'team': p['team'],
            'team_code': p['team_code'],
            'position': p['position'],
            'jersey': p['jersey'],
            'height_feet': p['height_feet'],
            'height_inches': p['height_inches'],
            'birth_date': p['birth_date'],
            'hometown': p['hometown'],
            'hometown_state': p['hometown_state'],
            'college': p['college'],
            'high_school': p['high_school'],
            'headshot_url': p['headshot_url'],
            'games_played': p['games_played'],
            'ppg': p['ppg'],
            'rpg': p['rpg'],
            'apg': p['apg'],
        })

    summary_data = {
        'export_date': datetime.now().isoformat(),
        'season': '2025-26',
        'league': 'Liga ACB',
        'player_count': len(summary_players),
        'players': summary_players
    }

    save_json(summary_data, f'american_players_summary_{timestamp}.json')
    save_json(summary_data, 'american_players_summary_latest.json')  # For dashboard

    # =========================================================================
    # Summary
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total players: {len(unified_players)}")

    with_hometown = sum(1 for p in unified_players if p.get('hometown'))
    with_college = sum(1 for p in unified_players if p.get('college'))

    logger.info(f"With hometown: {with_hometown}")
    logger.info(f"With college: {with_college}")

    if unified_players:
        logger.info("\nPlayers:")
        for p in unified_players[:15]:
            ht = f"{p['hometown']}" if p.get('hometown') else "Unknown"
            logger.info(f"  {p['name']} - {p['team']} | {ht}")


if __name__ == '__main__':
    main()
