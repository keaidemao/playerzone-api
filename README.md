# Playerzone API

An API for roundnet player data from the playerzone. The web interface is a sample app to showcase the API in practical use.

## API Endpoints

- `/elo/<player>`: Get player's RGX rating and info
- `/history/<player>`: Get player's RGX history
- `/match`: Calculate match RGX gains/losses between two teams
- `/players`: Get all player data

## Setup

1. Install dependencies:
```bash
pip install flask flask-cors fuzzywuzzy requests beautifulsoup4
```

2. Scrape data

Run `scraper.py` to fetch fresh player data from the playerzone website:
```bash
python scraper.py
```

3. Run the Flask backend to start the API:
```bash
python flask_app.py
```

## Details

- Player matching supports IDs, exact names, and fuzzy search
- Special handling for players in both Open/Women divisions
- Match calculations use the RGX rating system

The API is reachable at: roundnet.kadelfilm.de/rgx-api
<br>sample request: roundnet.kadelfilm.de/rgx-api/elo/paul_siemer

more soon

