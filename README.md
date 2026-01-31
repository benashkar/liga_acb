# Liga ACB American Players Dashboard

A web dashboard to track American basketball players in the Spanish Liga ACB.

## Features

- View all American players in Liga ACB
- Player details including hometown, college, high school
- Filter by team or home state
- Search by player name
- Upcoming game schedules

## Data Source

This project uses [TheSportsDB](https://www.thesportsdb.com/) free API for:
- Team rosters and player information
- Game schedules and results

**Note:** The free tier of TheSportsDB does not include box score data, so individual player game statistics are not available.

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the scraper to fetch data
python daily_scraper.py

# Look up player hometowns (optional)
python hometown_lookup_fixed.py

# Combine data sources
python join_data.py

# Start the dashboard
python dashboard.py
```

Then open http://localhost:5000 in your browser.

### Docker

```bash
# Build the image (includes data scraping)
docker build -t liga-acb-dashboard .

# Run the dashboard
docker run -p 5000:5000 liga-acb-dashboard
```

## Deployment

This project is configured for deployment on [Render.com](https://render.com):

1. Create a new Web Service
2. Connect your GitHub repository
3. Environment: Docker
4. The Dockerfile will scrape data during build

## Project Structure

```
liga_acb/
├── daily_scraper.py          # Fetches data from TheSportsDB API
├── hometown_lookup_fixed.py  # Wikipedia lookup for player backgrounds
├── join_data.py              # Combines data into unified records
├── dashboard.py              # Flask web application
├── start.sh                  # Startup script for deployment
├── Dockerfile                # Container configuration
├── requirements.txt          # Python dependencies
└── output/
    └── json/                 # JSON data files
```

## API Limitations

TheSportsDB free tier provides:
- Team information and logos
- Player rosters with biographical data
- Game schedules and final scores

It does NOT provide:
- Box scores with player statistics
- Play-by-play data
- Live game updates

For full box score data, consider upgrading to TheSportsDB Patreon tier or using API-Basketball.

## License

MIT
