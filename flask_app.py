from flask import Flask, jsonify
from flask_cors import CORS
from fuzzywuzzy import process
import json
import os
import re
import requests

app = Flask(__name__)
CORS(app)

@app.route('/elo/<player_query>', methods=['GET'])
def get_elo_rating(player_query):
    """
    Existing ELO endpoint (unchanged).
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    men_path = os.path.join(current_dir, 'men_players.json')
    women_path = os.path.join(current_dir, 'women_players.json')

    try:
        with open(men_path, 'r', encoding='utf-8') as f:
            men_data = json.load(f)
        with open(women_path, 'r', encoding='utf-8') as f:
            women_data = json.load(f)

        all_players = men_data + women_data

        # Check if numeric
        try:
            requested_id = int(player_query)
            is_id_lookup = True
        except ValueError:
            requested_id = None
            is_id_lookup = False

        if is_id_lookup:
            matched_players = [p for p in all_players if p['player_id'] == requested_id]
            if not matched_players:
                return jsonify({'error': f'No player found with ID {requested_id}'}), 404
            
            # If both divisions share the same ID, default to Women
            women_match = next((p for p in matched_players if p['division'].lower() == 'women'), None)
            if women_match:
                matched_player = women_match
            else:
                matched_player = matched_players[0]

            # Build response
            response_data = {
                'name': matched_player['name'],
                'player_id': matched_player['player_id'],
                'rank': matched_player['rank'],
                'club': matched_player['club'],
                'city': matched_player['city'],
                'games': matched_player['games'],
                'elo_rating': matched_player['elo_rating'],
                'division': matched_player['division'],
                'trend_90_days': matched_player['trend_90_days'],
                'pro_status': matched_player['pro_status'],
                'exists_in_both_divisions': matched_player.get('exists_in_both_divisions', False),
                'match_score': None,
                'exact_match': True
            }
            return jsonify(response_data)

        else:
            wants_open = False
            sanitized_name = player_query.strip()

            # If user appended '(o)' or '(1)', remove it => look for Open
            if sanitized_name.endswith('(o)') or sanitized_name.endswith('(1)'):
                wants_open = True
                sanitized_name = sanitized_name[:-4].strip()

            all_names = [p['name'] for p in all_players]
            best_match, score = process.extractOne(sanitized_name, all_names)
            if not best_match:
                return jsonify({'error': f'No player found matching {sanitized_name}'}), 404

            matched_records = [p for p in all_players if p['name'] == best_match]
            if not matched_records:
                return jsonify({'error': f'No player found matching {sanitized_name}'}), 404

            if len(matched_records) > 1:
                women_match = next((p for p in matched_records if p['division'].lower() == 'women'), None)
                open_match = next((p for p in matched_records if p['division'].lower() == 'open'), None)
                if wants_open and open_match:
                    matched_player = open_match
                elif women_match:
                    matched_player = women_match
                else:
                    matched_player = matched_records[0]
            else:
                matched_player = matched_records[0]

            response_data = {
                'name': matched_player['name'],
                'player_id': matched_player['player_id'],
                'rank': matched_player['rank'],
                'club': matched_player['club'],
                'city': matched_player['city'],
                'games': matched_player['games'],
                'elo_rating': matched_player['elo_rating'],
                'division': matched_player['division'],
                'trend_90_days': matched_player['trend_90_days'],
                'pro_status': matched_player['pro_status'],
                'exists_in_both_divisions': matched_player.get('exists_in_both_divisions', False),
                'match_score': score,
                'exact_match': (score == 100)
            }
            return jsonify(response_data)

    except FileNotFoundError as e:
        return jsonify({'error': f'Players data file not found: {str(e)}'}), 500
    except json.JSONDecodeError:
        return jsonify({'error': 'Error reading players data'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/history/<player_query>', methods=['GET'])
def get_elo_history(player_query):
    """
    Return the basic ELO history for the given player (by ID or name),
    using a simple regex approach to parse 'labels: [ ... ]' and 'data: [ ... ]'.

    This will produce a list of (date, rating) pairs -- i.e. you get:
    [
      { "date": "2021-07-31", "points": 1371 },
      { "date": "2021-08-08", "points": 1429 },
      ...
    ]
    
    The same division rules apply:
      - If player is found in both divisions, default to Women unless '(o)' or '(1)' is specified in the name.
      - If using numeric /history/265, default to Women if both exist.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    men_path = os.path.join(current_dir, 'men_players.json')
    women_path = os.path.join(current_dir, 'women_players.json')

    try:
        with open(men_path, 'r', encoding='utf-8') as f:
            men_data = json.load(f)
        with open(women_path, 'r', encoding='utf-8') as f:
            women_data = json.load(f)

        all_players = men_data + women_data

        # Determine if numeric or name
        try:
            requested_id = int(player_query)
            is_id_lookup = True
        except ValueError:
            requested_id = None
            is_id_lookup = False

        matched_player = None

        if is_id_lookup:
            # ID-based
            matched_players = [p for p in all_players if p['player_id'] == requested_id]
            if not matched_players:
                return jsonify({'error': f'No player found with ID {requested_id}'}), 404

            # If found in both divisions => default to women
            women_match = next((p for p in matched_players if p['division'].lower() == 'women'), None)
            if women_match:
                matched_player = women_match
            else:
                matched_player = matched_players[0]
        else:
            # Name-based (fuzzy)
            wants_open = False
            sanitized_name = player_query.strip()

            if sanitized_name.endswith('(o)') or sanitized_name.endswith('(1)'):
                wants_open = True
                sanitized_name = sanitized_name[:-4].strip()

            all_names = [p['name'] for p in all_players]
            best_match, score = process.extractOne(sanitized_name, all_names)
            if not best_match:
                return jsonify({'error': f'No player found matching {sanitized_name}'}), 404

            matched_records = [p for p in all_players if p['name'] == best_match]
            if not matched_records:
                return jsonify({'error': f'No player found matching {sanitized_name}'}), 404

            if len(matched_records) > 1:
                women_match = next((p for p in matched_records if p['division'].lower() == 'women'), None)
                open_match = next((p for p in matched_records if p['division'].lower() == 'open'), None)
                if wants_open and open_match:
                    matched_player = open_match
                elif women_match:
                    matched_player = women_match
                else:
                    matched_player = matched_records[0]
            else:
                matched_player = matched_records[0]

        if not matched_player:
            return jsonify({'error': 'No matched player found'}), 404

        # Now matched_player is the correct record with 'player_id' and 'division'
        division = matched_player['division'].lower()
        ranking_id = 1 if division == 'open' else 2
        player_id = matched_player['player_id']

        # Build the URL
        url = f"https://playerzone.roundnetgermany.de/ranking/rg-rating/history?player_id={player_id}&ranking_id={ranking_id}"
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        }

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return jsonify({'error': f'Failed to load page. HTTP {response.status_code}'}), 500

        # Simple regex to capture `labels: [ ... ] ... data: [ ... ]`
        # (DOTALL so that it can span multiple lines)
        match = re.search(r'labels:\s*\[(.*?)\].*?data:\s*\[(.*?)\]', response.text, re.DOTALL)
        if not match:
            return jsonify({'error': 'Failed to parse chart arrays with the simple regex'}), 500

        labels_raw = match.group(1).strip()
        data_raw = match.group(2).strip()

        # Convert them to lists
        # Since the snippet looks like: '2021-07-31', '2021-08-08', ...
        # We'll split on commas, strip quotes, etc.
        # For ratings, we do int(rating.strip()).
        dates = [date.strip().strip("'").strip('"') for date in labels_raw.split(',')]
        ratings = []
        for rating_str in data_raw.split(','):
            rating_str = rating_str.strip()
            # If there's any leftover quotes, strip them
            rating_str = rating_str.strip("'").strip('"')
            try:
                rating_val = int(rating_str)
                ratings.append(rating_val)
            except ValueError:
                # if it fails, skip or set to None
                ratings.append(None)

        # Now we pair them up
        history_list = []
        for d, r in zip(dates, ratings):
            history_list.append({
                'date': d,
                'points': r
            })

        return jsonify({
            'name': matched_player['name'],
            'player_id': matched_player['player_id'],
            'division': matched_player['division'],
            'history': history_list
        })

    except FileNotFoundError as e:
        return jsonify({'error': f'Players data file not found: {str(e)}'}), 500
    except json.JSONDecodeError:
        return jsonify({'error': 'Error reading players data'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/players', methods=['GET'])
def get_all_players():
    """
    Returns ALL players from men_players.json + women_players.json
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    men_path = os.path.join(current_dir, 'men_players.json')
    women_path = os.path.join(current_dir, 'women_players.json')

    try:
        with open(men_path, 'r', encoding='utf-8') as f:
            men_data = json.load(f)
        with open(women_path, 'r', encoding='utf-8') as f:
            women_data = json.load(f)

        all_players = men_data + women_data
        return jsonify(all_players)

    except FileNotFoundError as e:
        return jsonify({'error': f'Players data file not found: {str(e)}'}), 500
    except json.JSONDecodeError:
        return jsonify({'error': 'Error reading players data'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
