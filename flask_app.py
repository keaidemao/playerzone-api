from flask import Flask, request, jsonify
from flask_cors import CORS
from fuzzywuzzy import process
import json
import os
import re
import requests

app = Flask(__name__)
CORS(app)

# ----------------------------------------------------------------------------
# Helper: get_matched_player - used by /elo and /history to resolve ID vs name
# ----------------------------------------------------------------------------
def get_matched_player(player_query, all_players):
    """
    Returns (matched_player_dict, fuzzy_score, exact_match_bool)
    or raises ValueError if no match is found.
    
    Logic:
      1) Try parse as int => interpret as a player ID
         - If found, default to Women if multiple divisions share that ID
         - (fuzzy_score=None, exact_match=True)
      2) If that fails => treat as a fuzzy name
         - If name ends with '(o)' or '(1)', prefer Open if found in both divisions
         - (fuzzy_score=some int, exact_match=(score==100))
    """
    # Attempt ID-based lookup
    try:
        requested_id = int(player_query)
        matched_players = [p for p in all_players if p['player_id'] == requested_id]
        if not matched_players:
            raise ValueError(f"No player found with ID {requested_id}")

        if len(matched_players) > 1:
            # Found in both divisions => default to Women
            women_match = next((p for p in matched_players if p['division'].lower() == 'women'), None)
            matched_player = women_match if women_match else matched_players[0]
        else:
            matched_player = matched_players[0]

        return matched_player, None, True  # (player_dict, fuzzy_score=None, exact_match=True)

    except ValueError:
        # Not numeric => fuzzy name
        wants_open = False
        sanitized_name = player_query.strip()

        if sanitized_name.endswith('(o)') or sanitized_name.endswith('(1)'):
            wants_open = True
            sanitized_name = sanitized_name[:-4].strip()

        all_names = [p['name'] for p in all_players]
        best_match_tuple = process.extractOne(sanitized_name, all_names)
        if not best_match_tuple:
            raise ValueError(f"No player found matching '{sanitized_name}'")
        best_match, score = best_match_tuple

        matched_records = [p for p in all_players if p['name'] == best_match]
        if not matched_records:
            raise ValueError(f"No player found matching '{sanitized_name}'")

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

        exact_match = (score == 100)
        return matched_player, score, exact_match


# ----------------------------------------------------------------------------
# Helper: resolve_player_info - used by /match to get (rating, display_name)
# ----------------------------------------------------------------------------
def resolve_player_info(identifier, all_players):
    """
    Resolve a single 'identifier' to (rating, name).
    
    'identifier' can be:
      - "(xxxx)" => direct RGX rating
      - numeric => check if it's a player_id, else direct rating
      - fuzzy name => if found, return that player's rating & name
      - name + '(o)' => prefer open division if found in both
    """
    # Step 1) check for (o)/(1) suffix
    wants_open = False
    sanitized = identifier.strip()
    if sanitized.endswith('(o)') or sanitized.endswith('(1)'):
        wants_open = True
        sanitized = sanitized[:-4].strip()

    # Step 2) If in parentheses => direct rating
    match_paren_rating = re.match(r'^\((\d+)\)$', sanitized)
    if match_paren_rating:
        rating_val = int(match_paren_rating.group(1))
        return rating_val, f"Direct RGX {rating_val}"

    # Step 3) Try interpret as int => could be player_id or direct rating
    try:
        as_int = int(sanitized)
        matched_players = [p for p in all_players if p['player_id'] == as_int]
        if matched_players:
            if len(matched_players) > 1:
                # found in both => default to Women, unless wants_open
                women_match = next((p for p in matched_players if p['division'].lower() == 'women'), None)
                open_match = next((p for p in matched_players if p['division'].lower() == 'open'), None)
                if wants_open and open_match:
                    mp = open_match
                elif women_match:
                    mp = women_match
                else:
                    mp = matched_players[0]
            else:
                mp = matched_players[0]
            return mp['elo_rating'], mp['name']
        else:
            # no ID match => treat as direct rating
            return as_int, f"Direct RGX {as_int}"
    except ValueError:
        # not numeric => fuzzy name
        pass

    # Step 4) fuzzy name
    all_names = [p['name'] for p in all_players]
    best_match_tuple = process.extractOne(sanitized, all_names)
    if not best_match_tuple:
        raise ValueError(f"No player found matching '{identifier}'")
    best_match, score = best_match_tuple

    matched_records = [p for p in all_players if p['name'] == best_match]
    if not matched_records:
        raise ValueError(f"No player found matching '{identifier}'")

    if len(matched_records) > 1:
        # found in both divisions
        women_match = next((p for p in matched_records if p['division'].lower() == 'women'), None)
        open_match = next((p for p in matched_records if p['division'].lower() == 'open'), None)
        if wants_open and open_match:
            mp = open_match
        elif women_match:
            mp = women_match
        else:
            mp = matched_records[0]
    else:
        mp = matched_records[0]

    return mp['elo_rating'], mp['name']


# ----------------------------------------------------------------------------
# /elo/<player_query>
# ----------------------------------------------------------------------------
@app.route('/elo/<player_query>', methods=['GET'])
def get_elo_rating(player_query):
    """
    GET /elo/<player_query>
    Returns ELO info for a player by ID or name, using get_matched_player logic.
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

        matched_player, fuzzy_score, exact_match = get_matched_player(player_query, all_players)

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
            'match_score': fuzzy_score,
            'exact_match': exact_match
        }
        return jsonify(response_data)

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except FileNotFoundError as e:
        return jsonify({'error': f'Players data file not found: {str(e)}'}), 500
    except json.JSONDecodeError:
        return jsonify({'error': 'Error reading players data'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------------------
# /history/<player_query>
# ----------------------------------------------------------------------------
@app.route('/history/<player_query>', methods=['GET'])
def get_elo_history(player_query):
    """
    GET /history/<player_query>
    Returns the basic ELO history for a player, using a simple regex to parse
    `labels: [ ... ]` and `data: [ ... ]` from the RGX site.
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

        matched_player, fuzzy_score, exact_match = get_matched_player(player_query, all_players)
        division = matched_player['division'].lower()
        ranking_id = 1 if division == 'open' else 2
        player_id = matched_player['player_id']

        url = f"https://playerzone.roundnetgermany.de/ranking/rg-rating/history?player_id={player_id}&ranking_id={ranking_id}"
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return jsonify({'error': f'Failed to load page. HTTP {resp.status_code}'}), 500

        # Simple regex to parse
        match_chart = re.search(r'labels:\s*\[(.*?)\].*?data:\s*\[(.*?)\]', resp.text, re.DOTALL)
        if not match_chart:
            return jsonify({'error': 'Failed to parse chart arrays with the simple regex'}), 500

        labels_raw = match_chart.group(1).strip()
        data_raw = match_chart.group(2).strip()

        # Convert them to lists
        dates = [date.strip().strip("'").strip('"') for date in labels_raw.split(',')]
        ratings = []
        for rating_str in data_raw.split(','):
            rating_str = rating_str.strip().strip("'").strip('"')
            try:
                rating_val = int(rating_str)
                ratings.append(rating_val)
            except ValueError:
                ratings.append(None)

        history_list = []
        for d, r in zip(dates, ratings):
            history_list.append({'date': d, 'points': r})

        return jsonify({
            'name': matched_player['name'],
            'player_id': matched_player['player_id'],
            'division': matched_player['division'],
            'history': history_list,
            'match_score': fuzzy_score,
            'exact_match': exact_match
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except FileNotFoundError as e:
        return jsonify({'error': f'Players data file not found: {str(e)}'}), 500
    except json.JSONDecodeError:
        return jsonify({'error': 'Error reading players data'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------------------
# /players
# ----------------------------------------------------------------------------
@app.route('/players', methods=['GET'])
def get_all_players():
    """
    GET /players
    Returns all players from men_players.json + women_players.json
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    men_path = os.path.join(current_dir, 'men_players.json')
    women_path = os.path.join(current_dir, 'women_players.json')

    try:
        with open(men_path, 'r', encoding='utf-8') as f:
            men_data = json.load(f)
        with open(women_path, 'r', encoding='utf-8') as f:
            women_data = json.load(f)

        return jsonify(men_data + women_data)

    except FileNotFoundError as e:
        return jsonify({'error': f'Players data file not found: {str(e)}'}), 500
    except json.JSONDecodeError:
        return jsonify({'error': 'Error reading players data'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------------------
# /match
# ----------------------------------------------------------------------------
@app.route('/match', methods=['GET', 'POST'])
def calculate_match_outcome():
    """
    /match endpoint calculates the outcome for two teams of two players each.

    Supports GET or POST:
      - GET ?players=player1,player2 vs player3,player4
      - POST { "team1": ["265","Jane Doe"], "team2": ["(1972)","190"] }

    Special Requirements:
      1) Return full names for each requested player.
      2) For a 1-Satzspiel: b=0.75 and only p in {0,1}.
      3) Provide descriptive text for each (b, p) combination.
      4) JSON structure includes team1_players, team2_players, sums, combos, etc.
    """
    # Constants for formula
    d = 550
    k = 50

    # We'll define the sets of (b, p) we actually use:
    # - b=1.0 => p in [0, 0.25, 0.33, 0.4, 0.5, 0.6, 0.67, 0.75, 1]
    # - b=0.75 => p in [0, 1]
    combos_b_p = [
        (1.0, 0), (1.0, 0.25), (1.0, 0.33), (1.0, 0.4), (1.0, 0.5),
        (1.0, 0.6), (1.0, 0.67), (1.0, 0.75), (1.0, 1),
        (0.75, 0), (0.75, 1)
    ]

    # Descriptive text for b
    desc_for_b = {
        0.75: "One-set match",
        1.0: "Best-of-3 or Best-of-5 match"
    }
    # Descriptive text for p in a 1-satzspiel
    desc_for_p_b_075 = {
        0: "Team1 lost 0:1 in a 1-set match",
        1: "Team1 won 1:0 in a 1-set match"
    }
    # Descriptive text for p in Best-of-3/5
    desc_for_p_b_1 = {
        0:    "Team1 lost 0:1, 0:2, or 0:3",
        0.25: "Team1 lost 1:3",
        0.33: "Team1 lost 1:2",
        0.4:  "-",
        0.5:  "1:1 or 2:2",
        0.6:  "Team1 won 3:2",
        0.67: "Team1 won 2:1",
        0.75: "Team1 won 3:1",
        1:    "Team1 won 1:0, 2:0, or 3:0"
    }

    # Load player data
    current_dir = os.path.dirname(os.path.abspath(__file__))
    men_path = os.path.join(current_dir, 'men_players.json')
    women_path = os.path.join(current_dir, 'women_players.json')

    try:
        with open(men_path, 'r', encoding='utf-8') as f:
            men_data = json.load(f)
        with open(women_path, 'r', encoding='utf-8') as f:
            women_data = json.load(f)
        all_players = men_data + women_data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return jsonify({"error": f"Failed to load player data: {str(e)}"}), 500

    # Distinguish GET vs POST
    if request.method == 'GET':
        players_param = request.args.get('players', '')
        if not players_param:
            return jsonify({"error": "No 'players' query parameter provided."}), 400

        split_vs = re.split(r'\s*vs\s*', players_param, flags=re.IGNORECASE)
        if len(split_vs) != 2:
            return jsonify({"error": "Invalid format for 'players'. Use 'player1,player2 vs player3,player4'."}), 400

        team1_str, team2_str = split_vs
        team1_identifiers = [p.strip() for p in team1_str.split(',') if p.strip()]
        team2_identifiers = [p.strip() for p in team2_str.split(',') if p.strip()]

        if len(team1_identifiers) != 2 or len(team2_identifiers) != 2:
            return jsonify({"error": "Each team must have exactly two player identifiers."}), 400

    else:  # POST
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON body provided."}), 400

        team1_identifiers = data.get("team1")
        team2_identifiers = data.get("team2")
        if not (isinstance(team1_identifiers, list) and len(team1_identifiers) == 2):
            return jsonify({"error": "team1 must be a list of two player identifiers."}), 400
        if not (isinstance(team2_identifiers, list) and len(team2_identifiers) == 2):
            return jsonify({"error": "team2 must be a list of two player identifiers."}), 400

    # Resolve each player: (rating, name)
    try:
        t1p1_rating, t1p1_name = resolve_player_info(team1_identifiers[0], all_players)
        t1p2_rating, t1p2_name = resolve_player_info(team1_identifiers[1], all_players)
        t2p1_rating, t2p1_name = resolve_player_info(team2_identifiers[0], all_players)
        t2p2_rating, t2p2_name = resolve_player_info(team2_identifiers[1], all_players)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    r1 = t1p1_rating + t1p2_rating
    r2 = t2p1_rating + t2p2_rating

    # Build combination results
    results = []
    for (b_val, p_val) in combos_b_p:
        e1 = 1.0 / (1 + 10 ** ((r2 - r1) / d))
        x1 = b_val * k * (p_val - e1)

        if b_val == 0.75:
            # 1-set
            match_type = desc_for_b[b_val]
            outcome_desc = desc_for_p_b_075.get(p_val, "Invalid p for 1-set match")
        else:
            # b=1
            match_type = desc_for_b[b_val]
            outcome_desc = desc_for_p_b_1.get(p_val, f"p={p_val} not recognized")

        full_desc = f"{match_type}; {outcome_desc}"

        results.append({
            "b": b_val,
            "p": p_val,
            "e1": round(e1, 4),
            "x1": round(x1, 4),
            "description": full_desc
        })

    # Construct response
    response_data = {
        "team1_players": [
            {"identifier": team1_identifiers[0], "resolved_name": t1p1_name},
            {"identifier": team1_identifiers[1], "resolved_name": t1p2_name}
        ],
        "team2_players": [
            {"identifier": team2_identifiers[0], "resolved_name": t2p1_name},
            {"identifier": team2_identifiers[1], "resolved_name": t2p2_name}
        ],
        "team1_rating": r1,
        "team2_rating": r2,
        "combinations": results
    }
    return jsonify(response_data)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
