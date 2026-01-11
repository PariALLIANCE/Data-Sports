import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
import re
import os
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
}

# === DOSSIER DE SORTIE ===
OUTPUT_DIR = "data/football"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === LIGUES ===
LEAGUES = {
    "England_Premier_League": {"id": "eng.1", "json": "England_Premier_League.json"},
    "Spain_Laliga": {"id": "esp.1", "json": "Spain_Laliga.json"},
    "Germany_Bundesliga": {"id": "ger.1", "json": "Germany_Bundesliga.json"},
    "Argentina_Primera_Nacional": {"id": "arg.2", "json": "Argentina_Primera_Nacional.json"},
    "Austria_Bundesliga": {"id": "aut.1", "json": "Austria_Bundesliga.json"},
    "Belgium_Jupiler_Pro_League": {"id": "bel.1", "json": "Belgium_Jupiler_Pro_League.json"},
    "Brazil_Serie_A": {"id": "bra.1", "json": "Brazil_Serie_A.json"},
    "Brazil_Serie_B": {"id": "bra.2", "json": "Brazil_Serie_B.json"},
    "Chile_Primera_Division": {"id": "chi.1", "json": "Chile_Primera_Division.json"},
    "China_Super_League": {"id": "chn.1", "json": "China_Super_League.json"},
    "Colombia_Primera_A": {"id": "col.1", "json": "Colombia_Primera_A.json"},
    "England_National_League": {"id": "eng.5", "json": "England_National_League.json"},
    "France_Ligue_1": {"id": "fra.1", "json": "France_Ligue_1.json"},
    "Greece_Super_League_1": {"id": "gre.1", "json": "Greece_Super_League_1.json"},
    "Italy_Serie_A": {"id": "ita.1", "json": "Italy_Serie_A.json"},
    "Japan_J1_League": {"id": "jpn.1", "json": "Japan_J1_League.json"},
    "Mexico_Liga_MX": {"id": "mex.1", "json": "Mexico_Liga_MX.json"},
    "Netherlands_Eredivisie": {"id": "ned.1", "json": "Netherlands_Eredivisie.json"},
    "Paraguay_Division_Profesional": {"id": "par.1", "json": "Paraguay_Division_Profesional.json"},
    "Peru_Primera_Division": {"id": "per.1", "json": "Peru_Primera_Division.json"},
    "Portugal_Primeira_Liga": {"id": "por.1", "json": "Portugal_Primeira_Liga.json"},
    "Romania_Liga_I": {"id": "rou.1", "json": "Romania_Liga_I.json"},
    "Russia_Premier_League": {"id": "rus.1", "json": "Russia_Premier_League.json"},
    "Saudi_Arabia_Pro_League": {"id": "ksa.1", "json": "Saudi_Arabia_Pro_League.json"},
    "Sweden_Allsvenskan": {"id": "swe.1", "json": "Sweden_Allsvenskan.json"},
    "Switzerland_Super_League": {"id": "sui.1", "json": "Switzerland_Super_League.json"},
    "Turkey_Super_Lig": {"id": "tur.1", "json": "Turkey_Super_Lig.json"},
    "USA_Major_League_Soccer": {"id": "usa.1", "json": "USA_Major_League_Soccer.json"},
    "Venezuela_Primera_Division": {"id": "ven.1", "json": "Venezuela_Primera_Division.json"},
    "UEFA_Champions_League": {"id": "uefa.champions", "json": "UEFA_Champions_League.json"},
    "UEFA_Europa_League": {"id": "uefa.europa", "json": "UEFA_Europa_League.json"},
    "FIFA_Club_World_Cup": {"id": "fifa.cwc", "json": "FIFA_Club_World_Cup.json"}
}

# === DATE DU JOUR ===
today_str = datetime.now(timezone.utc).strftime("%Y%m%d")

# === SCRAPING ===
BASE_URL = "https://www.espn.com/soccer/schedule/_/date/{date}/league/{league}"

for league_name, league_info in LEAGUES.items():
    print(f"📅 Récupération {league_name} ({today_str})")
    try:
        res = requests.get(BASE_URL.format(date=today_str, league=league_info["id"]), headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
    except Exception as e:
        print(f"⚠️ Erreur réseau {league_name}: {e}")
        continue

    games_of_day = {}
    for table in soup.select("div.ResponsiveTable"):
        date_title = table.select_one("div.Table__Title")
        date_text = date_title.text.strip() if date_title else today_str

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
                "date": date_text,
                "league": league_name,
                "team1": teams[0].text.strip(),
                "team2": teams[1].text.strip(),
                "score": score,
                "match_url": "https://www.espn.com" + score_tag["href"]
            }

            time.sleep(0.5)  # Respect du site

    # === ÉCRITURE DU JSON PAR LIGUE ===
    output_file = os.path.join(OUTPUT_DIR, league_info["json"])
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(list(games_of_day.values()), f, indent=2, ensure_ascii=False)

    print(f"💾 {len(games_of_day)} matchs sauvegardés dans {output_file}\n")