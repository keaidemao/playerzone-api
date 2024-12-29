import requests
from bs4 import BeautifulSoup
import json
import re
import os

def scrape_players(url, division_label):
    """
    Scrape player data from the given URL (Open or Women) and return a list of dicts.
    Each dict includes:
        - name
        - player_id
        - rank
        - club
        - games
        - elo_rating
        - division
        - trend_90_days
        - pro_status
    """
    headers = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/91.0.4472.124 Safari/537.36')
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find the main table
    table = soup.find('table', {'id': 'rgx-main-table'})
    tbody = table.find('tbody')
    rows = tbody.find_all('tr')
    
    players = []
    for row in rows:
        # ----- Rank -----
        # e.g. <td class="bebas bold pos-col">1.</td>
        rank_td = row.find('td', class_='bebas bold pos-col')
        rank_text = rank_td.get_text(strip=True) if rank_td else ""
        # Remove trailing '.' if present (e.g. '1.' -> '1')
        rank_str = rank_text.replace('.', '')
        
        # ----- Name & ID -----
        # <a href="#elo-history" class="modal-trigger bebas" onclick="show_history(265, 1)">Paul Siemer</a>
        name_div = row.find('div', class_='player-name')
        if not name_div or not name_div.a:
            # If there's no <a>, skip this row
            continue
        name = name_div.a.get_text(strip=True)
        
        # Extract the player ID from the onclick attribute
        # e.g. show_history(265, 1) -> we want '265'
        onclick_val = name_div.a.get('onclick', '')
        # A quick regex to match show_history(265, or show_history(190,
        match = re.search(r'show_history\((\d+),', onclick_val)
        player_id = int(match.group(1)) if match else None
        
        # ----- Club -----
        # <span class="player-club hide-on-med-and-down">1. Roundnet Club Köln</span>
        club_span = row.find('span', class_='player-club hide-on-med-and-down')
        club = club_span.get_text(strip=True) if club_span else ""

        # ----- City -----
        city_span = row.find('span', class_='player-club hide-on-large-only')
        city = city_span.get_text(strip=True) if city_span else ""
        
        # ----- Number of Games -----
        # <td class="bebas games-col hide-on-small-only"> 267 </td>
        games_td = row.find('td', class_='bebas games-col hide-on-small-only')
        games_text = games_td.get_text(strip=True) if games_td else "0"
        try:
            games = int(games_text)
        except ValueError:
            games = 0
        
        # ----- ELO Rating & Trend -----
        rgx_badge_div = row.find('div', class_='rgx-badge')
        pro_status = 'pro-div' in rgx_badge_div.get('class', [])

        rgx_value_span = rgx_badge_div.find('span', class_='rgx-value')
        elo_text = rgx_value_span.get_text(strip=True) if rgx_value_span else "0"

        # Extract just the number from something like "1972"
        elo_match = re.search(r'\d+', elo_text)
        elo_rating = int(elo_match.group(0)) if elo_match else 0

        # Trend is stored in the nested <span class="hint" data-content="+26 Punkte in den letzten 90 Tagen">
        hint_span = rgx_value_span.find('span', class_='hint') if rgx_value_span else None
        trend_text = hint_span.get('data-content', '') if hint_span else ""

        # Check for "Keine Veränderung" to set trend to 0
        if "Keine Veränderung" in trend_text or "No change" in trend_text:
            trend_90_days = 0
        else:
            # Extract numerical trend: +26, -10, or 0
            trend_match = re.search(r'([+-]?\d+)', trend_text)
            trend_90_days = int(trend_match.group(1)) if trend_match else 0

        
        # ----- Append data -----
        # Store all your relevant data
        players.append({
            "name": name,
            "player_id": player_id,
            "rank": int(rank_str) if rank_str.isdigit() else None,
            "club": club,
            "city": city,
            "games": games,
            "elo_rating": elo_rating,
            "division": division_label,  # "Open" or "Women"
            "trend_90_days": trend_90_days,
            "pro_status": pro_status,
        })
    
    return players

def main():
    # URLs for men's (Open) and women's rankings
    men_url = "https://playerzone.roundnetgermany.de/ranking/rg-index/1"
    women_url = "https://playerzone.roundnetgermany.de/ranking/rg-index/2"
    
    try:
        print("Scraping Open (Men's) rankings...")
        men_players = scrape_players(men_url, "Open")
        
        print("Scraping Women rankings...")
        women_players = scrape_players(women_url, "Women")

        # Detect players that exist in both divisions
        # We'll do this by matching player_id (or name). If either ID or name matches, we consider them "in both".
        # A robust approach is to check by ID, since it's unique on the site.
        men_ids = set(p["player_id"] for p in men_players if p["player_id"])
        women_ids = set(p["player_id"] for p in women_players if p["player_id"])
        both_ids = men_ids.intersection(women_ids)
        
        # Mark them as "exists_in_both_divisions"
        for p in men_players:
            p["exists_in_both_divisions"] = (p["player_id"] in both_ids)
        for p in women_players:
            p["exists_in_both_divisions"] = (p["player_id"] in both_ids)

        # Save to JSON files
        current_dir = os.path.dirname(os.path.abspath(__file__))
        men_path = os.path.join(current_dir, 'men_players.json')
        women_path = os.path.join(current_dir, 'women_players.json')
        
        with open(men_path, 'w', encoding='utf-8') as f:
            json.dump(men_players, f, ensure_ascii=False, indent=4)
        
        with open(women_path, 'w', encoding='utf-8') as f:
            json.dump(women_players, f, ensure_ascii=False, indent=4)
        
        print(f"Successfully scraped {len(men_players)} Open players and {len(women_players)} Women players.")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
