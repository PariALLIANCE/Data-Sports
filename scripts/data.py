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


# Conversion date ESPN → datetime
def parse_match_date(date_str):
    """
    Exemple ESPN : 'Sunday, February 12, 2023'
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
    return load_json(league_file)


def extract_last_matches(team_name, league_matches, limit=7):
    """
    - Trie tous les matchs par date décroissante
    - Parcourt du plus récent au plus ancien
    - Garde uniquement ceux où l'équipe apparaît
    - S'arrête dès qu'on atteint la limite
    """
    team_norm = normalize_team_name(team_name)

    # 1. Ajout de la date parsée
    dated_matches = []
    for match in league_matches:
        match_date = parse_match_date(match.get("date", ""))
        if match_date:
            match["_parsed_date"] = match_date
            dated_matches.append(match)

    # 2. Tri du plus récent au plus ancien
    dated_matches.sort(key=lambda x: x["_parsed_date"], reverse=True)

    # 3. Filtrage par équipe
    team_games = []
    for match in dated_matches:
        t1 = normalize_team_name(match.get("team1", ""))
        t2 = normalize_team_name(match.get("team2", ""))

        if team_norm == t1 or team_norm == t2:
            team_games.append(match)

        if len(team_games) >= limit:
            break

    # 4. Nettoyage de la clé interne
    for match in team_games:
        match.pop("_parsed_date", None)

    return team_games


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

        last_team1 = extract_last_matches(team1, league_matches)
        last_team2 = extract_last_matches(team2, league_matches)

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