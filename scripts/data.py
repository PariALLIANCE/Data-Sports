import json
import os
from datetime import datetime

# ========= CHEMINS =========
GAMES_FILE = "data/football/games_of_day.json"
STANDINGS_FILE = "data/football/standings/Standings.json"
LEAGUES_DIR = "data/football/leagues"
OUTPUT_DIR = "data/football/predictions"
# ===========================

def load_json(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        print(f"📁 Création du dossier : {directory}")
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Fichier écrit physiquement : {os.path.abspath(path)}")

def normalize_team_name(name):
    if not name:
        return ""
    return name.lower().strip()

def convert_date_to_iso(date_text):
    """Convertit une date ESPN 'Sunday, February 12, 2023' → 'YYYY-MM-DD'"""
    try:
        date_obj = datetime.strptime(date_text, "%A, %B %d, %Y")
        return date_obj.strftime("%Y-%m-%d")
    except:
        return date_text

def load_league_matches(league):
    league_file = os.path.join(LEAGUES_DIR, f"{league}.json")
    if not os.path.exists(league_file):
        print(f"[WARN] Fichier de ligue introuvable : {league_file}")
        return []
    return load_json(league_file)

def extract_recent_matches(team_name, league_matches, limit=7):
    """Récupère tous les matchs où figure l'équipe, convertit les dates et ne garde que les plus récents"""
    team_norm = normalize_team_name(team_name)
    # Filtrer les matchs où l'équipe joue
    team_games = []
    for match in league_matches:
        t1 = normalize_team_name(match.get("team1", ""))
        t2 = normalize_team_name(match.get("team2", ""))
        if team_norm == t1 or team_norm == t2:
            # Cloner le match pour ne pas modifier l'original
            match_copy = dict(match)
            match_copy["date"] = convert_date_to_iso(match_copy.get("date", ""))
            team_games.append(match_copy)
    # Trier par date décroissante (les plus récents en premier)
    team_games.sort(key=lambda x: x.get("date", ""), reverse=True)
    # Ne garder que les 7 derniers
    return team_games[:limit]

def main():
    print("📂 Chargement des matchs du jour...")
    games = load_json(GAMES_FILE)

    print("📂 Chargement des classements...")
    standings = load_json(STANDINGS_FILE)

    result = []
    league_cache = {}

    for match in games:
        league = match.get("league")
        league_standings = standings.get(league, [])

        if league not in league_cache:
            print(f"📊 Chargement historique ligue : {league}")
            league_cache[league] = load_league_matches(league)
        league_matches = league_cache[league]

        team1 = match.get("team1")
        team2 = match.get("team2")

        last_team1 = extract_recent_matches(team1, league_matches)
        last_team2 = extract_recent_matches(team2, league_matches)

        enriched_match = {
            **match,
            "league_standings": league_standings,
            "recent_form": {
                "team1": {
                    "name": team1,
                    "last_7_matches": last_team1
                },
                "team2": {
                    "name": team2,
                    "last_7_matches": last_team2
                }
            }
        }

        result.append(enriched_match)

    today = datetime.now().strftime("%Y-%m-%d")
    output_file = os.path.join(OUTPUT_DIR, f"stats_football-{today}.json")

    print(f"📝 Tentative d’écriture du fichier : {output_file}")
    save_json(output_file, result)

    print("===================================")
    print("✅ FICHIER CRÉÉ AVEC SUCCÈS")
    print(f"📍 Emplacement : {output_file}")
    print(f"📊 Matchs traités : {len(result)}")
    print("===================================")

if __name__ == "__main__":
    main()