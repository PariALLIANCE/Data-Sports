import requests
from bs4 import BeautifulSoup
import json
import os
import time
import glob

# ================= HEADERS =================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}

# ================= DOSSIERS =================
LEAGUES_DIR = "data/football/leagues"

# ================= UTILITAIRES =================
def us_to_decimal(odds):
    if not odds:
        return None
    try:
        odds = odds.replace("+", "").strip()
        odds = int(odds)
        if odds > 0:
            return round(1 + (odds / 100), 2)
        else:
            return round(1 + (100 / abs(odds)), 2)
    except:
        return None

# ================= EXTRACTION COTES =================
def extract_ml_by_index(match_url):
    try:
        res = requests.get(match_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        odds_cells = soup.find_all("div", {"data-testid": "OddsCell"})
        if len(odds_cells) < 10:
            return None

        def get_value(cell):
            val = cell.find("div", class_="FTMw")
            return val.text.strip() if val else None

        home_us = get_value(odds_cells[1])
        away_us = get_value(odds_cells[5])
        draw_us = get_value(odds_cells[9])

        home = us_to_decimal(home_us)
        away = us_to_decimal(away_us)
        draw = us_to_decimal(draw_us)

        # Si toutes les cotes sont None → pas de données disponibles
        if home is None and away is None and draw is None:
            return None

        return {
            "home": home,
            "away": away,
            "draw": draw
        }

    except Exception as e:
        print(f"    ⚠️  Erreur récupération cotes : {e}")
        return None

# ================= TRAITEMENT =================
json_files = glob.glob(os.path.join(LEAGUES_DIR, "*.json"))

if not json_files:
    print(f"❌ Aucun fichier JSON trouvé dans {LEAGUES_DIR}")
    exit(1)

print(f"📂 {len(json_files)} fichier(s) trouvé(s)\n")

total_matches   = 0
total_enriched  = 0
total_null      = 0
total_skipped   = 0

for json_file in sorted(json_files):
    league_name = os.path.splitext(os.path.basename(json_file))[0]
    print(f"🏆 {league_name}")

    with open(json_file, "r", encoding="utf-8") as f:
        matches = json.load(f)

    modified = False

    for match in matches:
        total_matches += 1
        game_id    = match.get("gameId", "?")
        match_url  = match.get("match_url")

        # Déjà enrichi → on saute
        if "odds" in match:
            print(f"   ⏭️  {game_id} — déjà enrichi, ignoré")
            total_skipped += 1
            continue

        if not match_url:
            print(f"   ⚠️  {game_id} — pas d'URL, odds=null")
            match["odds"] = {"home": None, "away": None, "draw": None}
            total_null += 1
            modified = True
            continue

        print(f"   🔍 {game_id} — {match.get('team1')} vs {match.get('team2')}")
        odds = extract_ml_by_index(match_url)

        if odds:
            match["odds"] = odds
            print(f"       ✅ home={odds['home']}  draw={odds['draw']}  away={odds['away']}")
            total_enriched += 1
        else:
            match["odds"] = {"home": None, "away": None, "draw": None}
            print(f"       ℹ️  Cotes indisponibles → null")
            total_null += 1

        modified = True
        time.sleep(1)  # Pause polie entre chaque requête

    if modified:
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(matches, f, indent=2, ensure_ascii=False)
        print(f"   💾 Fichier mis à jour\n")
    else:
        print(f"   ✔️  Aucune modification nécessaire\n")

# ================= RÉSUMÉ =================
print("=" * 50)
print(f"✅ Terminé !")
print(f"   Total matchs    : {total_matches}")
print(f"   Enrichis (cotes): {total_enriched}")
print(f"   Cotes null      : {total_null}")
print(f"   Déjà enrichis   : {total_skipped}")
print("=" * 50)
