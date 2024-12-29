from flask import Flask, request, jsonify
from flask_cors import CORS
from fuzzywuzzy import process
import json
import os

app = Flask(__name__)
CORS(app)

@app.route('/elo/<name>', methods=['GET'])
def get_elo_rating(name):
    """
    API endpoint that returns ELO info for a given name.
    Searches through both (Open) and (Women) players.
    Uses fuzzy matching to find the closest name match.
    Returns all stored fields plus:
        - match_score (int)
        - exact_match (bool)
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

        # Combine all players
        all_players = men_data + women_data

        # Get all names
        all_names = [p['name'] for p in all_players]

        # Use fuzzy search to find best match
        best_match, score = process.extractOne(name, all_names)

        # Find the corresponding player data
        matched_player = next(p for p in all_players if p['name'] == best_match)

        # Return that player's data + fuzzy match info
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
    API endpoint that returns ALL players (Open + Women),
    as stored in men_players.json and women_players.json.
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
    # For production, you might want debug=False
    app.run(debug=True)
