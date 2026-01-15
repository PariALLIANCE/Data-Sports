import json
import os
from datetime import datetime

# ========= CHEMINS =========
GAMES_FILE = "data/football/games_of_day.json"
STANDINGS_FILE = "data/football/standings/Standings.json"
LEAGUES_DIR = "data/football/league"
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


def parse_match_date(date_str):
    """
    Exemple dans tes fichiers ligue :
    'Friday, January 20, 2023'
    """
    try:
        return datetime.strptime(date_str, "%A, %B %d, %Y")
    except Exception:
        return None


def load_league_matches(league):
    league_file = os.path.join(LEAGUES_DIR, f"{league}.json")
    if not os.path.exists(league_file):
        print(f"[WARN] Fichier de ligue introuvable : {league_file}")
        return []

    matches = load_json(league_file)

    # On trie les matchs par date réelle pour garantir les "derniers matchs"
    def sort_key(m):
        d = parse_match_date(m.get("date", ""))
        return d if d else datetime.min

    matches.sort(key=sort_key)
    return matches


def extract_last_matches(team_name, league_matches, limit=7):
    team_norm = normalize_team_name(team_name)
    team_games = []

    for match in league_matches:
        t1 = normalize_team_name(match.get("team1"))
        t2 = normalize_team_name(match.get("team2"))

        if team_norm == t1 or team_norm == t2:
            team_games.append(match)

    # On prend les 7 plus récents
    return team_games[-limit:]


def main():
    print("📂 Chargement des matchs du jour...")
    games = load_json(GAMES_FILE)

    print("📂 Chargement des classements...")
    standings = load_json(STANDINGS_FILE)

    result = []
    league_cache = {}

    for match in games:
        league = match.get("league")

        if not league:
            print("[WARN] Match sans ligue détecté, ignoré")
            continue

        # ===== Classement de la ligue =====
        league_standings = standings.get(league, [])
        if not league_standings:
            print(f"[WARN] Aucun classement trouvé pour la ligue : {league}")

        # ===== Chargement historique ligue (cache) =====
        if league not in league_cache:
            print(f"📊 Chargement historique ligue : {league}")
            league_cache[league] = load_league_matches(league)

        league_matches = league_cache[league]

        team1 = match.get("team1")
        team2 = match.get("team2")

        if not team1 or not team2:
            print(f"[WARN] Match incomplet (équipes manquantes) : {match.get('gameId')}")
            continue

        # ===== 7 derniers matchs =====
        last_team1 = extract_last_matches(team1, league_matches, limit=7)
        last_team2 = extract_last_matches(team2, league_matches, limit=7)

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
    print("📈 Chaque match contient :")
    print("   - le classement de la ligue")
    print("   - les 7 derniers matchs réels de chaque équipe (triés par date)")
    print("===================================")


if __name__ == "__main__":
    main()