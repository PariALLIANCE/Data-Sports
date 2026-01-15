import json
import os
from datetime import datetime

# ====== CHEMINS LOCAUX DANS TON REPO ======
GAMES_FILE = "data/football/games_of_day.json"
STANDINGS_FILE = "data/football/standings/Standings.json"

# Nouveau chemin de sortie
OUTPUT_DIR = "data/football/prédictions"
# =======================================


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    print("📂 Lecture de games_of_day.json...")
    games = load_json(GAMES_FILE)

    print("📂 Lecture de Standings.json...")
    standings = load_json(STANDINGS_FILE)

    result = []

    for match in games:
        league = match.get("league")
        league_standings = standings.get(league, [])

        enriched_match = {
            **match,
            "league_standings": league_standings
        }

        if not league_standings:
            print(f"[WARN] Aucun classement trouvé pour la ligue : {league}")

        result.append(enriched_match)

    today = datetime.now().strftime("%Y-%m-%d")
    output_file = os.path.join(OUTPUT_DIR, f"stats_football-{today}.json")

    save_json(output_file, result)

    print("===================================")
    print(f"✅ Fichier généré : {output_file}")
    print(f"📊 Matchs traités : {len(result)}")
    print("===================================")


if __name__ == "__main__":
    main()