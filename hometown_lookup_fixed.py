"""
=============================================================================
HOMETOWN LOOKUP - WIKIPEDIA VERSION (LIGA ACB)
=============================================================================

PURPOSE:
    This script finds the hometown and college information for American
    Liga ACB players by looking them up on Wikipedia.

HOW IT WORKS:
    1. Load the list of American players from the most recent JSON export
    2. For each player, search Wikipedia and parse the infobox
    3. Extract birth_place, college, high_school information
    4. Save results to JSON files
"""

import json
import os
import re
import requests
from datetime import datetime
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
# CONFIGURATION
# =============================================================================
WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {'User-Agent': 'LigaACBTracker/1.0 (basketball data collection)'}

# =============================================================================
# MANUAL OVERRIDES
# =============================================================================
MANUAL_OVERRIDES = {
    # Add players with common names that return wrong Wikipedia results
    # Example:
    # 'BOOKER, DEVIN': {
    #     'hometown_city': 'Union',
    #     'hometown_state': 'South Carolina',
    #     'college': 'Clemson',
    #     'high_school': 'Union County High School',
    # },
}

# =============================================================================
# US STATE DATA
# =============================================================================
US_STATES = {
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
    'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
    'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
    'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
    'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
    'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
    'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
    'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
    'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
    'West Virginia', 'Wisconsin', 'Wyoming', 'District of Columbia', 'D.C.'
}

STATE_ABBREVS = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia'
}


def clean_name(name):
    """Clean a player's name for Wikipedia search."""
    if ', ' in name:
        parts = name.split(', ', 1)
        name = f"{parts[1]} {parts[0]}"
    name = name.title()
    name = re.sub(r'\s+(Ii|Iii|Iv|Jr\.?|Sr\.?)$', '', name, flags=re.IGNORECASE)
    return name.strip()


def search_wikipedia(name):
    """Search Wikipedia for a basketball player's article."""
    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': f'{name} basketball player',
        'format': 'json',
        'srlimit': 5
    }

    try:
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=10)
        data = resp.json()
        results = data.get('query', {}).get('search', [])

        name_lower = name.lower()
        for result in results:
            title = result.get('title', '')
            if name_lower in title.lower():
                return title

        if results:
            return results[0].get('title')

    except Exception as e:
        logger.debug(f"Wikipedia search error: {e}")

    return None


def get_wiki_wikitext(title):
    """Get the raw wikitext content of a Wikipedia article."""
    params = {
        'action': 'query',
        'titles': title,
        'prop': 'revisions',
        'rvprop': 'content',
        'rvslots': 'main',
        'format': 'json'
    }

    try:
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=15)
        data = resp.json()
        pages = data.get('query', {}).get('pages', {})

        for page_id, page in pages.items():
            if page_id != '-1':
                revisions = page.get('revisions', [])
                if revisions:
                    return revisions[0].get('slots', {}).get('main', {}).get('*', '')

    except Exception as e:
        logger.debug(f"Wiki content error: {e}")

    return None


def parse_infobox(wikitext):
    """Parse a Wikipedia article's wikitext to extract player information."""
    result = {
        'hometown_city': None,
        'hometown_state': None,
        'high_school': None,
        'college': None,
        'lookup_successful': False
    }

    if not wikitext:
        return result

    # Parse birth_place
    birth_match = re.search(r'\|\s*birth_place\s*=\s*(.+?)(?=\n\||\n\}\})', wikitext, re.DOTALL)

    if birth_match:
        birth_text = birth_match.group(1).strip()
        birth_text = re.sub(r'\[\[([^\]|]+)\|[^\]]+\]\]', r'\1', birth_text)
        birth_text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', birth_text)
        birth_text = re.sub(r'\{\{[^}]+\}\}', '', birth_text)
        birth_text = birth_text.replace('U.S.', '').replace('USA', '').strip().rstrip(',')

        parts = [p.strip() for p in birth_text.split(',') if p.strip()]

        if len(parts) >= 2:
            city = parts[0]
            state = parts[1]

            if state in US_STATES:
                result['hometown_city'] = city
                result['hometown_state'] = state
            elif state in STATE_ABBREVS:
                result['hometown_city'] = city
                result['hometown_state'] = STATE_ABBREVS[state]

    # Parse college
    college_match = re.search(r'\|\s*college\s*=\s*(.+?)(?=\n\||\n\}\})', wikitext, re.DOTALL)

    if college_match:
        college_text = college_match.group(1).strip()
        college_link = re.search(r'\[\[([^\]|]+)\|([^\]]+)\]\]', college_text)
        if college_link:
            result['college'] = college_link.group(2).strip()
        else:
            college_link = re.search(r'\[\[([^\]]+)\]\]', college_text)
            if college_link:
                result['college'] = college_link.group(1).strip()
            else:
                college_text = re.sub(r'\{\{[^}]+\}\}', '', college_text).strip()
                if college_text and len(college_text) > 2:
                    result['college'] = college_text

    # Parse high_school
    hs_match = re.search(r'\|\s*high_school\s*=\s*(.+?)(?=\n\||\n\}\})', wikitext, re.DOTALL)

    if hs_match:
        hs_text = hs_match.group(1).strip()
        hs_link = re.search(r'\[\[([^\]|]+)\|([^\]]+)\]\]', hs_text)
        if hs_link:
            result['high_school'] = hs_link.group(2).strip()
        else:
            hs_link = re.search(r'\[\[([^\]]+)\]\]', hs_text)
            if hs_link:
                result['high_school'] = hs_link.group(1).strip()
            else:
                hs_text = re.sub(r'\{\{[^}]+\}\}', '', hs_text).strip()
                if hs_text and len(hs_text) > 2:
                    result['high_school'] = hs_text

    if result['hometown_state'] or result['college']:
        result['lookup_successful'] = True

    return result


def lookup_player(name):
    """Look up a player's hometown and college information."""
    clean = clean_name(name)
    title = search_wikipedia(clean)
    if not title:
        return None

    wikitext = get_wiki_wikitext(title)
    if not wikitext:
        return None

    result = parse_infobox(wikitext)
    result['wiki_title'] = title

    return result if result['lookup_successful'] else None


def load_american_players():
    """Load the list of American players from the most recent JSON export."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')

    if not os.path.exists(output_dir):
        return []

    files = []
    for f in os.listdir(output_dir):
        if (f.startswith('american_players_') and
            'hometown' not in f and
            'wiki' not in f and
            'summary' not in f and
            'unified' not in f):
            files.append(f)

    if not files:
        return []

    files = sorted(files)
    filepath = os.path.join(output_dir, files[-1])
    logger.info(f"Loading from: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get('players', [])


def save_json(data, filename):
    """Save data to a JSON file in the output directory."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Saved: {filepath}")


def main():
    """Main entry point for the hometown lookup script."""
    logger.info("=" * 60)
    logger.info("LIGA ACB - HOMETOWN LOOKUP")
    logger.info("=" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Load Players
    players = load_american_players()
    if not players:
        logger.error("No players found")
        return

    # Deduplicate
    seen = set()
    unique = []
    for p in players:
        code = p.get('code')
        if code and code not in seen:
            seen.add(code)
            unique.append(p)

    logger.info(f"Processing {len(unique)} unique players")

    # Look Up Each Player
    results = []
    success = 0
    failed = 0

    for i, player in enumerate(unique):
        name = player.get('name', '')
        team = player.get('team_name', 'Unknown')
        clean = clean_name(name)

        logger.info(f"[{i+1}/{len(unique)}] {clean} ({team})")

        player_result = {
            'code': player.get('code'),
            'name': name,
            'clean_name': clean,
            'team_code': player.get('team_code'),
            'team_name': team,
            'nationality': player.get('nationality'),
            'birth_date': player.get('birth_date'),
        }

        # Check for manual override first
        name_upper = name.upper()
        if name_upper in MANUAL_OVERRIDES:
            override = MANUAL_OVERRIDES[name_upper]
            player_result['hometown_city'] = override.get('hometown_city')
            player_result['hometown_state'] = override.get('hometown_state')
            player_result['college'] = override.get('college')
            player_result['high_school'] = override.get('high_school')
            player_result['lookup_successful'] = True
            player_result['source'] = 'manual_override'
            success += 1
            logger.info(f"  OVERRIDE: {override.get('hometown_city')}, {override.get('hometown_state')}")
        else:
            info = lookup_player(name)

            if info and info.get('lookup_successful'):
                player_result.update(info)
                success += 1
                logger.info(f"  FOUND: {info.get('hometown_city')}, {info.get('hometown_state')} | College: {info.get('college')}")
            else:
                player_result['lookup_successful'] = False
                failed += 1
                logger.info(f"  Not found")

            time.sleep(0.3)

        results.append(player_result)

    # Save Results
    save_json({
        'export_date': datetime.now().isoformat(),
        'league': 'Liga ACB',
        'total': len(unique),
        'found': success,
        'not_found': failed,
        'players': results
    }, f'american_hometowns_{timestamp}.json')

    found = [p for p in results if p.get('lookup_successful')]
    save_json({
        'export_date': datetime.now().isoformat(),
        'league': 'Liga ACB',
        'count': len(found),
        'players': found
    }, f'american_hometowns_found_{timestamp}.json')

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total: {len(unique)}")
    logger.info(f"Found: {success} ({success/len(unique)*100:.1f}%)" if unique else "Found: 0")
    logger.info(f"Not found: {failed}")


if __name__ == '__main__':
    main()
