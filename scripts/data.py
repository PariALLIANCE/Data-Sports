import json
import os
from datetime import datetime
from collections import defaultdict

# ========= CHEMINS =========
GAMES_FILE = "data/football/games_of_day.json"
STANDINGS_FILE = "data/football/standings/Standings.json"
LEAGUES_DIR = "data/football/league"  # contient Germany_Bundesliga.json, etc.
OUTPUT_DIR = "data/football/prédictions"
# ===========================


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_team_name(name):
    return name.lower().strip()


def load_league_matches(league):
    """
    Charge le fichier correspondant à la ligue :
    data/football/league/<league>.json
    """
    league_file = os.path.join(LEAGUES_DIR, f"{league}.json")
    if not os.path.exists(league_file):
        print(f"[WARN] Fichier de ligue introuvable : {league_file}")
        return []
    return load_json(league_file)


def extract_last_matches(team_name, league_matches, limit=7):
    """
    Récupère les 7 derniers matchs d'une équipe dans une ligue donnée.
    """
    team_norm = normalize_team_name(team_name)
    team_games = []

    for match in league_matches:
        t1 = normalize_team_name(match.get("team1", ""))
        t2 = normalize_team_name(match.get("team2", ""))

        if team_norm == t1 or team_norm == t2:
            team_games.append(match)

    # On suppose que les fichiers sont déjà chronologiques (du plus ancien au plus récent)
    # On prend les 7 derniers
    return team_games[-limit:]


def main():
    print("📂 Lecture de games_of_day.json...")
    games = load_json(GAMES_FILE)

    print("📂 Lecture de Standings.json...")
    standings = load_json(STANDINGS_FILE)

    result = []

    # Cache pour éviter de recharger plusieurs fois la même ligue
    league_cache = {}

    for match in games:
        league = match.get("league")

        # ===== Classement de la ligue =====
        league_standings = standings.get(league, [])
        if not league_standings:
            print(f"[WARN] Aucun classement trouvé pour la ligue : {league}")

        # ===== Chargement des matchs historiques de la ligue =====
        if league not in league_cache:
            print(f"📂 Chargement de l'historique pour la ligue : {league}")
            league_cache[league] = load_league_matches(league)

        league_matches = league_cache[league]

        # ===== Récupération des 7 derniers matchs pour chaque équipe =====
        team1 = match.get("team1")
        team2 = match.get("team2")

        last_matches_team1 = extract_last_matches(team1, league_matches, limit=7)
        last_matches_team2 = extract_last_matches(team2, league_matches, limit=7)

        enriched_match = {
            **match,
            "league_standings": league_standings,
            "recent_form": {
                "team1": {
                    "name": team1,
                    "last_7_matches": last_matches_team1
                },
                "team2": {
                    "name": team2,
                    "last_7_matches": last_matches_team2
                }
            }
        }

        result.append(enriched_match)

    today = datetime.now().strftime("%Y-%m-%d")
    output_file = os.path.join(OUTPUT_DIR, f"stats_football-{today}.json")

    save_json(output_file, result)

    print("===================================")
    print(f"✅ Fichier généré : {output_file}")
    print(f"📊 Matchs traités : {len(result)}")
    print("📈 Chaque match contient maintenant :")
    print("   - le classement complet de la ligue")
    print("   - les 7 derniers matchs de chaque équipe")
    print("===================================")


if __name__ == "__main__":
    main()