import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
import re
import os
import time

# === HEADERS ===
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
}

# === DOSSIER DE SORTIE ===
OUTPUT_DIR = "data/football"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "game-of-day.json")

# === FICHIER DES ÉQUIPES ===
TEAMS_FILE = os.path.join(OUTPUT_DIR, "teams", "football_teams.json")
with open(TEAMS_FILE, "r", encoding="utf-8") as f:
    TEAMS_DATA = json.load(f)

# === LIGUES ===
LEAGUES = {
    "England_Premier_League": { "id": "eng.1" },
    "Spain_Laliga": { "id": "esp.1" },
    "Germany_Bundesliga": { "id": "ger.1" },
    "Argentina_Primera_Nacional": { "id": "arg.2" },
    "Austria_Bundesliga": { "id": "aut.1" },
    "Belgium_Jupiler_Pro_League": { "id": "bel.1" },
    "Brazil_Serie_A": { "id": "bra.1" },
    "Brazil_Serie_B": { "id": "bra.2" },
    "Chile_Primera_Division": { "id": "chi.1" },
    "China_Super_League": { "id": "chn.1" },
    "Colombia_Primera_A": { "id": "col.1" },
    "England_National_League": { "id": "eng.5" },
    "France_Ligue_1": { "id": "fra.1" },
    "Greece_Super_League_1": { "id": "gre.1" },
    "Italy_Serie_A": { "id": "ita.1" },
    "Japan_J1_League": { "id": "jpn.1" },
    "Mexico_Liga_MX": { "id": "mex.1" },
    "Netherlands_Eredivisie": { "id": "ned.1" },
    "Paraguay_Division_Profesional": { "id": "par.1" },
    "Peru_Primera_Division": { "id": "per.1" },
    "Portugal_Primeira_Liga": { "id": "por.1" },
    "Romania_Liga_I": { "id": "rou.1" },
    "Russia_Premier_League": { "id": "rus.1" },
    "Saudi_Arabia_Pro_League": { "id": "ksa.1" },
    "Sweden_Allsvenskan": { "id": "swe.1" },
    "Switzerland_Super_League": { "id": "sui.1" },
    "Turkey_Super_Lig": { "id": "tur.1" },
    "USA_Major_League_Soccer": { "id": "usa.1" },
    "Venezuela_Primera_Division": { "id": "ven.1" },
    "UEFA_Champions_League": { "id": "uefa.champions" },
    "UEFA_Europa_League": { "id": "uefa.europa" },
    "FIFA_Club_World_Cup": { "id": "fifa.cwc" }
}

# === DATE DU JOUR ===
today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

BASE_URL = "https://www.espn.com/soccer/schedule/_/date/{date}/league/{league}"

# === FONCTION DE CONVERSION DE DATE ===
def convert_date_to_iso(date_text):
    try:
        date_obj = datetime.strptime(date_text, "%A, %B %d, %Y")
        return date_obj.strftime("%Y-%m-%d")
    except Exception:
        return date_text

# === FONCTION POUR TROUVER LE LOGO ===
def get_team_logo(league_name, team_name):
    teams = TEAMS_DATA.get(league_name, [])
    for t in teams:
        if t["team"].lower() == team_name.lower():
            return t["logo"]
    return None

# === CONTENEUR GLOBAL ===
all_games = {}

# === SCRAPING PAR LIGUE ===
for league_name, league_info in LEAGUES.items():
    print(f"📅 Récupération {league_name} ({today_str})")

    try:
        res = requests.get(
            BASE_URL.format(date=today_str, league=league_info["id"]),
            headers=HEADERS,
            timeout=15
        )
        soup = BeautifulSoup(res.content, "html.parser")
    except Exception as e:
        print(f"⚠️ Erreur réseau {league_name}: {e}")
        continue

    for table in soup.select("div.ResponsiveTable"):
        date_title = table.select_one("div.Table__Title")
        date_text = date_title.text.strip() if date_title else today_str
        date_text_iso = convert_date_to_iso(date_text)

        for row in table.select("tbody > tr.Table__TR"):
            teams = row.select("span.Table__Team a.AnchorLink:last-child")
            score_tag = row.select_one("a.AnchorLink.at")

            if len(teams) != 2 or not score_tag:
                continue

            score = score_tag.text.strip()
            if score.lower() != "v":
                continue

            match_id = re.search(r"gameId/(\d+)", score_tag["href"])
            if not match_id:
                continue

            game_id = match_id.group(1)

            if date_text_iso != today_iso:
                continue

            team1_name = teams[0].text.strip()
            team2_name = teams[1].text.strip()

            all_games[game_id] = {
                "gameId": game_id,
                "date": date_text_iso,
                "league": league_name,
                "team1": team1_name,
                "team1_logo": get_team_logo(league_name, team1_name),
                "team2": team2_name,
                "team2_logo": get_team_logo(league_name, team2_name),
                "score": score,
                "match_url": "https://www.espn.com" + score_tag["href"]
            }

            time.sleep(0.5)

# === ÉCRITURE DU JSON GLOBAL ===
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(list(all_games.values()), f, indent=2, ensure_ascii=False)

print(f"\n💾 {len(all_games)} matchs du jour sauvegardés dans {OUTPUT_FILE}")
