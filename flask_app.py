from flask import Flask, jsonify
from flask_cors import CORS
from fuzzywuzzy import process
import json
import os

app = Flask(__name__)
CORS(app)

@app.route('/elo/<player_query>', methods=['GET'])
def get_elo_rating(player_query):
    """
    API endpoint that returns ELO info for a given player.
    The <player_query> can be either a numeric ID or a name.
    
    1) If it's numeric (e.g., /elo/265), we do an ID-based lookup.
       - If a player with that ID is found in both divisions,
         we default to the Women division.
    2) If it's a name, we fuzzy-match the name.
       - If the user appends "(o)" or "(1)" to the name (e.g. "John Doe (o)"),
         we interpret that as requesting the Open division data.
       - Otherwise, if the same player is found in both divisions,
         we default to Women by default.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    men_path = os.path.join(current_dir, 'men_players.json')
    women_path = os.path.join(current_dir, 'women_players.json')

    try:
        # Load both JSON files
        with open(men_path, 'r', encoding='utf-8') as f:
            men_data = json.load(f)
        with open(women_path, 'r', encoding='utf-8') as f:
            women_data = json.load(f)

        all_players = men_data + women_data

        # Try to parse the player_query as an integer (player_id)
        try:
            requested_id = int(player_query)
            is_id_lookup = True
        except ValueError:
            requested_id = None
            is_id_lookup = False

        # --------------------------
        # 1) If it's an ID
        # --------------------------
        if is_id_lookup:
            # Filter by ID
            matched_players = [p for p in all_players if p['player_id'] == requested_id]
            if not matched_players:
                return jsonify({'error': f'No player found with ID {requested_id}'}), 404
            
            # If in both divisions, default to Women
            women_match = next((p for p in matched_players if p['division'].lower() == 'women'), None)
            if women_match:
                matched_player = women_match
            else:
                # Otherwise, just pick the first match
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
                # ID-based lookup doesn't use fuzzy score
                'match_score': None,
                'exact_match': True
            }
            return jsonify(response_data)

        # --------------------------
        # 2) If it's a Name
        # --------------------------
        else:
            # Detect if user wants Open (i.e., ends with (o) or (1))
            wants_open = False
            sanitized_name = player_query.strip()

            # If user appended "(o)" or "(1)", remove it and note that they want Open
            if sanitized_name.endswith('(o)') or sanitized_name.endswith('(1)'):
                wants_open = True
                # Remove the trailing 4 chars => " (o)" or " (1)"
                sanitized_name = sanitized_name[:-4].strip()

            # Fuzzy-match the sanitized name
            all_names = [p['name'] for p in all_players]
            best_match, score = process.extractOne(sanitized_name, all_names)

            if not best_match:
                return jsonify({'error': f'No player found matching {sanitized_name}'}), 404

            # Find all records with that best_match name
            matched_records = [p for p in all_players if p['name'] == best_match]
            if not matched_records:
                return jsonify({'error': f'No player found matching {sanitized_name}'}), 404

            # If multiple records have the same name (Open + Women):
            if len(matched_records) > 1:
                # Try to find a Women record and an Open record
                women_match = next((p for p in matched_records if p['division'].lower() == 'women'), None)
                open_match = next((p for p in matched_records if p['division'].lower() == 'open'), None)

                if wants_open and open_match:
                    matched_player = open_match
                elif women_match:
                    matched_player = women_match
                else:
                    # fallback if neither is found
                    matched_player = matched_records[0]
            else:
                # Only one record found
                matched_player = matched_records[0]

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


@app.route('/players', methods=['GET'])
def get_all_players():
    """
    Returns ALL players from men_players.json (Open) and women_players.json,
    combined into one list.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    men_path = os.path.join(current_dir, 'men_players.json')
    women_path = os.path.join(current_dir, 'women_players.json')

    try:
        with open(men_path, 'r', encoding='utf-8') as f:
            men_data = json.load(f)
        with open(women_path, 'r', encoding='utf-8') as f:
            women_data = json.load(f)

        # Combine them
        all_players = men_data + women_data
        return jsonify(all_players)

    except FileNotFoundError as e:
        return jsonify({'error': f'Players data file not found: {str(e)}'}), 500
    except json.JSONDecodeError:
        return jsonify({'error': 'Error reading players data'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # For production, set debug=False
    app.run(debug=True)
