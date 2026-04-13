import requests
from bs4 import BeautifulSoup
import json
import os
import time
import glob
from datetime import datetime

# ================= CONFIG =================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}

LEAGUES_DIR = "data/football/leagues"
OUTPUT_FILE = "dataset_with_odds.json"
MAX_MISS    = 10  # Arrêt après 10 matchs consécutifs sans cotes par ligue

# ================= UTILITAIRES =================
def us_to_decimal(odds_str):
    if not odds_str:
        return None
    try:
        val = int(odds_str.replace("+", "").strip())
        return round(1 + (val / 100), 2) if val > 0 else round(1 + (100 / abs(val)), 2)
    except:
        return None

def parse_date(date_str):
    for fmt in ("%A, %B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    return datetime.min

def is_valid_us_odds(val):
    if not val:
        return False
    try:
        int(val.replace("+", "").replace("-", ""))
        return True
    except:
        return False

def extract_odds(match_url):
    """
    Extrait les cotes moneyline depuis une page ESPN.
    Structure : 7 OddsCell min, ML aux indices 0 (home), 3 (away), 6 (draw).
    """
    try:
        res = requests.get(match_url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        cells = soup.find_all("div", {"data-testid": "OddsCell"})

        if len(cells) < 7:
            return None

        home_us = cells[0].get_text(strip=True) or None
        away_us = cells[3].get_text(strip=True) or None
        draw_us = cells[6].get_text(strip=True) or None

        if not all(is_valid_us_odds(v) for v in [home_us, away_us, draw_us]):
            return None

        return {
            "home": us_to_decimal(home_us),
            "away": us_to_decimal(away_us),
            "draw": us_to_decimal(draw_us),
        }

    except Exception as e:
        print(f"    ⚠️  Erreur : {e}")
        return None

# ================= CHARGEMENT DATASET EXISTANT =================
existing_matches = []
existing_ids     = set()

if os.path.exists(OUTPUT_FILE):
    print(f"📂 Dataset existant trouvé : {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        existing_matches = json.load(f)
    existing_ids = {m["gameId"] for m in existing_matches}
    print(f"   {len(existing_matches)} matchs déjà présents\n")
else:
    print(f"📂 Nouveau dataset : {OUTPUT_FILE}\n")

# ================= DÉCOUVERTE DES FICHIERS =================
json_files = sorted(glob.glob(os.path.join(LEAGUES_DIR, "*.json")))

if not json_files:
    print(f"❌ Aucun fichier JSON trouvé dans {LEAGUES_DIR}")
    exit(1)

print(f"📋 {len(json_files)} ligue(s) à traiter\n")
print("=" * 50)

# ================= TRAITEMENT PAR LIGUE =================
all_new_matches   = []
grand_total_added = 0
grand_total_skip  = 0

for json_file in json_files:
    league_name = os.path.splitext(os.path.basename(json_file))[0]
    print(f"\n🏆 {league_name}")

    with open(json_file, "r", encoding="utf-8") as f:
        matches = json.load(f)

    # Tri du plus récent au plus ancien
    matches_sorted = sorted(
        matches,
        key=lambda m: parse_date(m.get("date", "")),
        reverse=True
    )

    new_matches      = []
    consecutive_miss = 0
    league_added     = 0
    league_skipped   = 0

    for match in matches_sorted:
        game_id   = match.get("gameId")
        match_url = match.get("match_url")
        date_str  = match.get("date", "?")
        team1     = match.get("team1", "?")
        team2     = match.get("team2", "?")

        # Déjà présent → skip silencieux
        if game_id in existing_ids:
            league_skipped += 1
            grand_total_skip += 1
            continue

        if not match_url:
            consecutive_miss += 1
            continue

        odds = extract_odds(match_url)
        time.sleep(1)

        if odds:
            match_copy = dict(match)
            match_copy["league"] = league_name
            match_copy["odds"]   = odds
            new_matches.append(match_copy)
            # Ajouter à existing_ids pour éviter doublons inter-ligues
            existing_ids.add(game_id)
            consecutive_miss = 0
            league_added    += 1
            grand_total_added += 1
            print(f"  ✅ [{date_str}] {team1} vs {team2} → {odds['home']} / {odds['draw']} / {odds['away']}")
        else:
            consecutive_miss += 1
            print(f"  ℹ️  [{date_str}] {team1} vs {team2} → pas de cotes ({consecutive_miss}/{MAX_MISS})")

        if consecutive_miss >= MAX_MISS:
            print(f"  ⛔ {MAX_MISS} miss consécutifs — passage à la ligue suivante")
            break

    all_new_matches.extend(new_matches)
    print(f"  → {league_added} ajoutés, {league_skipped} déjà présents")

# ================= SAUVEGARDE =================
final_dataset = existing_matches + all_new_matches

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(final_dataset, f, indent=2, ensure_ascii=False)

print(f"\n{'='*50}")
print(f"💾 Sauvegardé : {OUTPUT_FILE}")
print(f"   Ligues traitées       : {len(json_files)}")
print(f"   Nouveaux matchs       : {grand_total_added}")
print(f"   Déjà présents         : {grand_total_skip}")
print(f"   Total dans le dataset : {len(final_dataset)}")
print(f"{'='*50}")
