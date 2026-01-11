import requests
from bs4 import BeautifulSoup
import json
import re
import os
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
}

# === DOSSIER DE SORTIE ===
OUTPUT_DIR = "data/football"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "games_of_day.json")

# === LIGUES COMPLÈTES ===
LEAGUES = {
    "England_Premier_League": "eng.1",
    "Spain_Laliga": "esp.1",
    "Germany_Bundesliga": "ger.1",
    "Argentina_Primera_Nacional": "arg.2",
    "Austria_Bundesliga": "aut.1",
    "Belgium_Jupiler_Pro_League": "bel.1",
    "Brazil_Serie_A": "bra.1",
    "Brazil_Serie_B": "bra.2",
    "Chile_Primera_Division": "chi.1",
    "China_Super_League": "chn.1",
    "Colombia_Primera_A": "col.1",
    "England_National_League": "eng.5",
    "France_Ligue_1": "fra.1",
    "Greece_Super_League_1": "gre.1",
    "Italy_Serie_A": "ita.1",
    "Japan_J1_League": "jpn.1",
    "Mexico_Liga_MX": "mex.1",
    "Netherlands_Eredivisie": "ned.1",
    "Paraguay_Division_Profesional": "par.1",
    "Peru_Primera_Division": "per.1",
    "Portugal_Primeira_Liga": "por.1",
    "Romania_Liga_I": "rou.1",
    "Russia_Premier_League": "rus.1",
    "Saudi_Arabia_Pro_League": "ksa.1",
    "Sweden_Allsvenskan": "swe.1",
    "Switzerland_Super_League": "sui.1",
    "Turkey_Super_Lig": "tur.1",
    "USA_Major_League_Soccer": "usa.1",
    "Venezuela_Primera_Division": "ven.1",
    "UEFA_Champions_League": "uefa.champions",
    "UEFA_Europa_League": "uefa.europa",
    "FIFA_Club_World_Cup": "fifa.cwc"
}

games_of_day = {}
BASE_URL = "https://www.espn.com/soccer/schedule/_/date/{date}/league/{league}"

# Date du jour pour l'URL (format ESPN)
from datetime import datetime, timezone
today_str = datetime.now(timezone.utc).strftime("%Y%m%d")

for league_name, league_code in LEAGUES.items():
    print(f"📅 Récupération {league_name} ({today_str})")

    try:
        res = requests.get(BASE_URL.format(date=today_str, league=league_code), headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
    except Exception as e:
        print(f"⚠️ Erreur réseau {league_name}: {e}")
        continue

    for table in soup.select("div.ResponsiveTable"):
        for row in table.select("tbody > tr.Table__TR"):
            teams = row.select("span.Table__Team a.AnchorLink:last-child")
            score_tag = row.select_one("a.AnchorLink.at")

            if len(teams) != 2 or not score_tag:
                continue

            score = score_tag.text.strip()

            # ⚡ Match non joué uniquement
            if score.lower() != "v":
                continue

            match_id = re.search(r"gameId/(\d+)", score_tag["href"])
            if not match_id:
                continue

            game_id = match_id.group(1)

            games_of_day[game_id] = {
                "gameId": game_id,
                "league": league_name,
                "team1": teams[0].text.strip(),
                "team2": teams[1].text.strip(),
                "score": score,
                "match_url": "https://www.espn.com" + score_tag["href"]
            }

            time.sleep(0.5)  # Respect du site

# Écriture JSON
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(list(games_of_day.values()), f, indent=2, ensure_ascii=False)

print(f"\n💾 {len(games_of_day)} matchs non joués sauvegardés dans {OUTPUT_FILE}")