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

LEAGUES_DIR     = "data/football/leagues"
OUTPUT_DIR      = "data/football/leagues_with_odds"   # ← Nouveau dossier, originaux intacts
MAX_MISS        = 10   # Arrêt après 10 matchs consécutifs sans cotes par fichier
START_FROM      = ""   # Ex: "Germany_Bundesliga.json" pour reprendre à partir d'un fichier

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

# ================= CRÉATION DU DOSSIER DE SORTIE =================
os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"📁 Dossier de sortie : {OUTPUT_DIR}\n")

# ================= DÉCOUVERTE DES FICHIERS =================
json_files = sorted(glob.glob(os.path.join(LEAGUES_DIR, "*.json")))

if not json_files:
    print(f"❌ Aucun fichier JSON trouvé dans {LEAGUES_DIR}")
    exit(1)

# Filtrage à partir du fichier de départ
if START_FROM:
    start_names = [os.path.basename(f) for f in json_files]
    if START_FROM in start_names:
        start_idx  = start_names.index(START_FROM)
        json_files = json_files[start_idx:]
        print(f"▶️  Démarrage à partir de : {START_FROM}")
    else:
        print(f"⚠️  '{START_FROM}' introuvable — traitement de tous les fichiers")

print(f"📋 {len(json_files)} ligue(s) à traiter\n")
print("=" * 50)

# ================= TRAITEMENT PAR LIGUE =================
grand_total_with_odds    = 0
grand_total_without_odds = 0
grand_total_skipped_file = 0

for json_file in json_files:
    league_name = os.path.splitext(os.path.basename(json_file))[0]
    output_file = os.path.join(OUTPUT_DIR, os.path.basename(json_file))

    print(f"\n🏆 {league_name}")

    # ── Vérifier si ce fichier a déjà été traité ──────────────────────────
    # On considère "déjà traité" si le fichier output existe ET contient
    # au moins un match avec une clé "odds". Sinon on re-traite.
    already_processed_ids = set()
    enriched_index = {}   # gameId → match enrichi (sortie existante)

    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            existing_output = json.load(f)
        for m in existing_output:
            if "odds" in m:
                already_processed_ids.add(m["gameId"])
            enriched_index[m["gameId"]] = m
        print(f"   📂 Sortie existante : {len(enriched_index)} matchs ({len(already_processed_ids)} avec cotes)")

    # ── Charger le JSON source ─────────────────────────────────────────────
    with open(json_file, "r", encoding="utf-8") as f:
        matches = json.load(f)

    # Tri du plus récent au plus ancien pour la logique de miss consécutifs
    matches_sorted = sorted(
        matches,
        key=lambda m: parse_date(m.get("date", "")),
        reverse=True
    )

    league_with_odds    = 0
    league_without_odds = 0
    consecutive_miss    = 0
    stopped_early       = False

    # On travaille sur une copie enrichie de tous les matchs
    # enriched_index est initialisé avec ce qui existe déjà en sortie
    # Les matchs source non encore traités sont ajoutés tels quels
    for m in matches:
        if m["gameId"] not in enriched_index:
            enriched_index[m["gameId"]] = dict(m)

    for match in matches_sorted:
        game_id   = match.get("gameId")
        match_url = match.get("match_url")
        date_str  = match.get("date", "?")
        team1     = match.get("team1", "?")
        team2     = match.get("team2", "?")

        # Déjà enrichi avec des cotes → skip
        if game_id in already_processed_ids:
            league_with_odds += 1
            continue

        if not match_url:
            consecutive_miss += 1
            print(f"  ⚠️  [{date_str}] {team1} vs {team2} → pas d'URL ({consecutive_miss}/{MAX_MISS})")
            if consecutive_miss >= MAX_MISS:
                print(f"  ⛔ {MAX_MISS} miss consécutifs — passage à la ligue suivante")
                stopped_early = True
                break
            continue

        odds = extract_odds(match_url)
        time.sleep(1)

        if odds:
            enriched_index[game_id]["odds"] = odds
            already_processed_ids.add(game_id)
            consecutive_miss = 0
            league_with_odds += 1
            print(f"  ✅ [{date_str}] {team1} vs {team2} → {odds['home']} / {odds['draw']} / {odds['away']}")
        else:
            consecutive_miss += 1
            league_without_odds += 1
            print(f"  ℹ️  [{date_str}] {team1} vs {team2} → pas de cotes ({consecutive_miss}/{MAX_MISS})")

            if consecutive_miss >= MAX_MISS:
                print(f"  ⛔ {MAX_MISS} miss consécutifs — passage à la ligue suivante")
                stopped_early = True
                break

    # ── Reconstruire la liste finale dans l'ordre original du JSON source ──
    # On préserve l'ordre du fichier source (pas l'ordre de traitement)
    final_matches = []
    source_ids_ordered = [m["gameId"] for m in matches]

    for gid in source_ids_ordered:
        if gid in enriched_index:
            final_matches.append(enriched_index[gid])

    # Ajouter les matchs qui seraient dans enriched_index mais pas dans source
    # (cas théorique de fichier output plus complet que le source)
    source_ids_set = set(source_ids_ordered)
    for gid, m in enriched_index.items():
        if gid not in source_ids_set:
            final_matches.append(m)

    # ── Sauvegarde atomique ─────────────────────────────────────────────────
    tmp_file = output_file + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(final_matches, f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, output_file)

    grand_total_with_odds    += league_with_odds
    grand_total_without_odds += league_without_odds
    if stopped_early:
        grand_total_skipped_file += 1

    with_odds_count    = sum(1 for m in final_matches if "odds" in m)
    without_odds_count = sum(1 for m in final_matches if "odds" not in m)

    print(f"  → 💾 {os.path.basename(output_file)} : {len(final_matches)} matchs total")
    print(f"       ✅ avec cotes : {with_odds_count}  |  ℹ️  sans cotes : {without_odds_count}")

# ================= RÉSUMÉ FINAL =================
print(f"\n{'='*50}")
print(f"🏁 TRAITEMENT TERMINÉ")
print(f"   Ligues traitées              : {len(json_files)}")
print(f"   Fichiers avec arrêt anticipé : {grand_total_skipped_file}")
print(f"   Matchs enrichis (cotes)      : {grand_total_with_odds}")
print(f"   Matchs sans cotes            : {grand_total_without_odds}")
print(f"   Dossier de sortie            : {OUTPUT_DIR}/")
print(f"{'='*50}")
