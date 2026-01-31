"""
=============================================================================
LIGA ACB - AMERICAN PLAYERS DASHBOARD
=============================================================================

PURPOSE:
    A web interface to view American player data in the Spanish Liga ACB.

HOW TO USE:
    1. Run this script: python dashboard.py
    2. Open your browser to: http://localhost:5000

FEATURES:
    - View all American players with details
    - Filter by team, hometown state
    - Search by player name
    - View player detail pages
    - See upcoming games schedule
"""

import json
import os
from glob import glob
from flask import Flask, render_template_string, request

# =============================================================================
# FLASK APP SETUP
# =============================================================================
app = Flask(__name__)

# =============================================================================
# DATA LOADING
# =============================================================================

def load_latest_data():
    """Load the most recent unified player data."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    files = sorted(glob(os.path.join(output_dir, 'american_players_summary_*.json')))

    if not files:
        return {'players': [], 'export_date': 'No data'}

    with open(files[-1], 'r', encoding='utf-8') as f:
        return json.load(f)


def load_player_detail(player_code):
    """Load full player data including all details."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    files = sorted(glob(os.path.join(output_dir, 'unified_american_players_*.json')))

    if not files:
        return None

    with open(files[-1], 'r', encoding='utf-8') as f:
        data = json.load(f)

    for player in data.get('players', []):
        if player.get('code') == player_code:
            return player

    return None


# =============================================================================
# HTML TEMPLATES
# =============================================================================

BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Liga ACB American Players</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 { color: #c8102e; }
        .filters {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .filters select, .filters input {
            padding: 8px;
            margin-right: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        table {
            width: 100%;
            background: white;
            border-collapse: collapse;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th {
            background: #c8102e;
            color: white;
            padding: 12px 8px;
            text-align: left;
        }
        th a { color: white; text-decoration: none; }
        td {
            padding: 10px 8px;
            border-bottom: 1px solid #eee;
        }
        tr:hover { background: #f9f9f9; }
        a { color: #c8102e; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .stats { font-weight: bold; }
        .hometown { color: #666; font-size: 0.9em; }
        .last-updated {
            color: #666;
            font-size: 0.85em;
            margin-bottom: 10px;
        }
        .player-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .game-log { font-size: 0.9em; }
        .player-header {
            display: flex;
            gap: 20px;
            align-items: flex-start;
        }
        .player-headshot {
            width: 150px;
            height: auto;
            border-radius: 8px;
            object-fit: cover;
        }
        .player-info {
            flex: 1;
        }
        .player-info h2 {
            margin-top: 0;
            color: #c8102e;
        }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            background: #c8102e;
            color: white;
        }
        .badge.win {
            background: #28a745;
        }
        .badge.loss {
            background: #dc3545;
        }
        .note-box {
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <h1>Liga ACB American Players Dashboard</h1>
    {% block content %}{% endblock %}
</body>
</html>
"""

HOME_TEMPLATE = """
{% extends "base" %}
{% block content %}
<p class="last-updated">Last updated: {{ export_date }}</p>

<div class="note-box">
    <strong>Note:</strong> Player statistics (PPG, RPG, APG) are not available in this version.
    TheSportsDB free tier does not include box score data.
</div>

<div class="filters">
    <form method="GET">
        <input type="text" name="search" placeholder="Search by name..."
               value="{{ search }}">

        <select name="team">
            <option value="">All Teams</option>
            {% for team in teams %}
            <option value="{{ team }}" {% if team == selected_team %}selected{% endif %}>
                {{ team }}
            </option>
            {% endfor %}
        </select>

        <select name="state">
            <option value="">All States</option>
            {% for state in states %}
            <option value="{{ state }}" {% if state == selected_state %}selected{% endif %}>
                {{ state }}
            </option>
            {% endfor %}
        </select>

        <button type="submit">Filter</button>
        <a href="/">Reset</a>
    </form>
</div>

<table>
    <thead>
        <tr>
            <th><a href="?sort=name&{{ query_string }}">Player</a></th>
            <th><a href="?sort=team&{{ query_string }}">Team</a></th>
            <th>Position</th>
            <th>Height</th>
            <th>Hometown</th>
            <th>High School</th>
            <th>College</th>
        </tr>
    </thead>
    <tbody>
        {% for player in players %}
        <tr>
            <td><a href="/player/{{ player.code }}">{{ player.name }}</a></td>
            <td>{{ player.team or 'N/A' }}</td>
            <td>{{ player.position or 'N/A' }}</td>
            <td>{% if player.height_feet %}{{ player.height_feet }}'{{ player.height_inches }}"{% else %}N/A{% endif %}</td>
            <td class="hometown">{{ player.hometown or 'Unknown' }}</td>
            <td>{{ player.high_school or 'N/A' }}</td>
            <td>{{ player.college or 'N/A' }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>

<p>Showing {{ players|length }} players</p>
{% endblock %}
"""

PLAYER_TEMPLATE = """
{% extends "base" %}
{% block content %}
<a href="/">&larr; Back to all players</a>

<div class="player-card player-header">
    {% if player.headshot_url %}
    <img src="{{ player.headshot_url }}" alt="{{ player.name }}" class="player-headshot">
    {% endif %}
    <div class="player-info">
        <h2>{{ player.name }}</h2>
        <p>
            <strong>Team:</strong> {{ player.team or 'N/A' }}<br>
            <strong>Position:</strong> {{ player.position or 'N/A' }}<br>
            <strong>Jersey:</strong> #{{ player.jersey or 'N/A' }}<br>
            <strong>Height:</strong> {% if player.height_feet %}{{ player.height_feet }}'{{ player.height_inches }}"{% else %}N/A{% endif %}<br>
            <strong>Birth Date:</strong> {{ player.birth_date or 'N/A' }}
        </p>
        <p>
            <strong>Hometown:</strong> {{ player.hometown or 'Unknown' }}<br>
            <strong>College:</strong> {{ player.college or 'N/A' }}<br>
            <strong>High School:</strong> {{ player.high_school or 'N/A' }}
        </p>
        {% if player.instagram or player.twitter %}
        <p>
            {% if player.instagram %}<a href="https://instagram.com/{{ player.instagram }}" target="_blank">Instagram</a>{% endif %}
            {% if player.twitter %}<a href="https://twitter.com/{{ player.twitter }}" target="_blank">Twitter</a>{% endif %}
        </p>
        {% endif %}
    </div>
</div>

{% if player.upcoming_games %}
<div class="player-card">
    <h3>Upcoming Games</h3>
    <table class="game-log">
        <thead>
            <tr>
                <th>Date</th>
                <th>Opponent</th>
                <th>H/A</th>
                <th>Round</th>
                <th>Venue</th>
            </tr>
        </thead>
        <tbody>
            {% for game in player.upcoming_games %}
            <tr>
                <td>{{ game.date }}</td>
                <td>{{ game.opponent }}</td>
                <td>{{ game.home_away }}</td>
                <td>{{ game.round or 'N/A' }}</td>
                <td>{{ game.venue or 'N/A' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endif %}

{% if player.past_games %}
<div class="player-card">
    <h3>Past Games</h3>
    <table class="game-log">
        <thead>
            <tr>
                <th>Date</th>
                <th>Opponent</th>
                <th>H/A</th>
                <th>Result</th>
                <th>Score</th>
                <th>Venue</th>
            </tr>
        </thead>
        <tbody>
            {% for game in player.past_games %}
            <tr>
                <td>{{ game.date }}</td>
                <td>{{ game.opponent }}</td>
                <td>{{ game.home_away }}</td>
                <td><span class="badge {% if game.result == 'W' %}win{% else %}loss{% endif %}">{{ game.result }}</span></td>
                <td>{{ game.team_score }} - {{ game.opponent_score }}</td>
                <td>{{ game.venue or 'N/A' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endif %}

<div class="player-card">
    <h3>About</h3>
    <p class="note-box">
        <strong>Note:</strong> Game statistics are not available in this version.
        TheSportsDB free API tier does not include box score data.
    </p>
</div>
{% endblock %}
"""


# =============================================================================
# ROUTES
# =============================================================================

@app.route('/')
def home():
    """Main page showing all players with filtering options."""
    data = load_latest_data()
    players = data.get('players', [])
    export_date = data.get('export_date', 'Unknown')

    # Get filter parameters
    search = request.args.get('search', '').lower()
    selected_team = request.args.get('team', '')
    selected_state = request.args.get('state', '')
    sort_by = request.args.get('sort', 'name')

    # Apply filters
    if search:
        players = [p for p in players if search in p.get('name', '').lower()]

    if selected_team:
        players = [p for p in players if p.get('team') == selected_team]

    if selected_state:
        players = [p for p in players if p.get('hometown_state') == selected_state]

    # Sort
    sort_key = sort_by if sort_by in ['name', 'team'] else 'name'
    players = sorted(players, key=lambda p: p.get(sort_key) or '')

    # Get unique teams and states for filter dropdowns
    all_data = load_latest_data()
    all_players = all_data.get('players', [])
    teams = sorted(set(p.get('team') for p in all_players if p.get('team')))
    states = sorted(set(p.get('hometown_state') for p in all_players if p.get('hometown_state')))

    # Build query string for sort links
    query_parts = []
    if search:
        query_parts.append(f"search={search}")
    if selected_team:
        query_parts.append(f"team={selected_team}")
    if selected_state:
        query_parts.append(f"state={selected_state}")
    query_string = '&'.join(query_parts)

    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}',
                              HOME_TEMPLATE.replace('{% extends "base" %}', '')),
        players=players,
        export_date=export_date,
        teams=teams,
        states=states,
        search=search,
        selected_team=selected_team,
        selected_state=selected_state,
        query_string=query_string
    )


@app.route('/player/<code>')
def player_detail(code):
    """Player detail page."""
    player = load_player_detail(code)

    if not player:
        return "Player not found", 404

    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}',
                              PLAYER_TEMPLATE.replace('{% extends "base" %}', '')),
        player=player
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("LIGA ACB AMERICAN PLAYERS DASHBOARD")
    print("=" * 60)
    print("\nStarting web server...")
    print("Open your browser to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
