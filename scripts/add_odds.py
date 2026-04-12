import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime

# ================= CONFIG =================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}

LEAGUES_DIR    = "data/football/leagues"
INPUT_FILE     = os.path.join(LEAGUES_DIR, "Italy_Serie_A.json")
OUTPUT_FILE    = "dataset_with_odds.json"
MAX_MISS       = 10   # Arrêt après 10 matchs consécutifs sans cotes

# ================= UTILITAIRES =================
def us_to_decimal(odds_str):
    if not odds_str:
        return None
    try:
        val = int(odds_str.replace("+", "").strip())
        if val > 0:
            return round(1 + (val / 100), 2)
        else:
            return round(1 + (100 / abs(val)), 2)
    except:
        return None

def parse_date(date_str):
    """Convertit 'Sunday, January 1, 2023' en datetime pour tri."""
    try:
        return datetime.strptime(date_str, "%A, %B %d, %Y")
    except:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return datetime.min

def extract_odds(match_url):
    """
    Extrait les cotes moneyline depuis une page ESPN.
    Structure : 7 OddsCell, ML aux indices 0 (home), 3 (away), 6 (draw).
    """
    try:
        res = requests.get(match_url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        odds_cells = soup.find_all("div", {"data-testid": "OddsCell"})

        if len(odds_cells) < 7:
            return None

        home_us = odds_cells[0].get_text(strip=True) or None
        away_us = odds_cells[3].get_text(strip=True) or None
        draw_us = odds_cells[6].get_text(strip=True) or None

        # Vérification : les valeurs doivent ressembler à des cotes US (+XXX ou -XXX)
        def is_valid(val):
            if not val:
                return False
            try:
                int(val.replace("+", "").replace("-", ""))
                return True
            except:
                return False

        if not (is_valid(home_us) and is_valid(away_us) and is_valid(draw_us)):
            return None

        return {
            "home": us_to_decimal(home_us),
            "away": us_to_decimal(away_us),
            "draw": us_to_decimal(draw_us)
        }

    except Exception as e:
        print(f"    ⚠️  Erreur : {e}")
        return None

# ================= CHARGEMENT =================
print(f"📂 Lecture de {INPUT_FILE}...")
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    matches = json.load(f)

print(f"   {len(matches)} matchs chargés")

# Tri du plus récent au plus ancien
matches_sorted = sorted(matches, key=lambda m: parse_date(m.get("date", "")), reverse=True)

# ================= CHARGEMENT DATASET EXISTANT =================
existing_ids = set()
existing_matches = []

if os.path.exists(OUTPUT_FILE):
    print(f"📂 Dataset existant trouvé : {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        existing_matches = json.load(f)
    existing_ids = {m["gameId"] for m in existing_matches}
    print(f"   {len(existing_matches)} matchs déjà présents")
else:
    print(f"📂 Nouveau dataset : {OUTPUT_FILE}")

# ================= SCRAPING =================
new_matches   = []
consecutive_miss = 0
total_scraped = 0
total_skipped = 0

print(f"\n🚀 Démarrage du scraping (arrêt après {MAX_MISS} miss consécutifs)...\n")

for match in matches_sorted:
    game_id   = match.get("gameId")
    match_url = match.get("match_url")
    date_str  = match.get("date", "?")
    team1     = match.get("team1", "?")
    team2     = match.get("team2", "?")

    # Déjà dans le dataset → skip
    if game_id in existing_ids:
        total_skipped += 1
        continue

    print(f"🔍 [{date_str}] {team1} vs {team2}")

    if not match_url:
        print(f"   ⚠️  Pas d'URL → skip")
        consecutive_miss += 1
    else:
        odds = extract_odds(match_url)
        time.sleep(1)

        if odds:
            match_copy = dict(match)
            match_copy["odds"] = odds
            new_matches.append(match_copy)
            consecutive_miss = 0
            total_scraped += 1
            print(f"   ✅ home={odds['home']}  draw={odds['draw']}  away={odds['away']}")
        else:
            consecutive_miss += 1
            print(f"   ℹ️  Cotes indisponibles ({consecutive_miss}/{MAX_MISS})")

    if consecutive_miss >= MAX_MISS:
        print(f"\n⛔ {MAX_MISS} miss consécutifs — arrêt du scraping")
        break

# ================= SAUVEGARDE =================
final_dataset = existing_matches + new_matches

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(final_dataset, f, indent=2, ensure_ascii=False)

print(f"\n{'='*50}")
print(f"💾 Sauvegardé : {OUTPUT_FILE}")
print(f"   Nouveaux matchs ajoutés : {total_scraped}")
print(f"   Déjà présents (skippés) : {total_skipped}")
print(f"   Total dans le dataset   : {len(final_dataset)}")
print(f"{'='*50}")
