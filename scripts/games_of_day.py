import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
import re
import os
import time

# === HEADERS ===
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}

# === DOSSIERS ===
BASE_DIR = "data/football"
TEAMS_DIR = os.path.join(BASE_DIR, "teams")
OUTPUT_DIR = BASE_DIR

os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(OUTPUT_DIR, "games_of_day.json")
TEAMS_FILE = os.path.join(TEAMS_DIR, "football_teams.json")

# === LIGUES LIMITÉES ===
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

BASE_URL = "https://www.espn.com/soccer/schedule/_/date/{date}/league/{league}"

# === DATE DU JOUR ===
today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# === CONVERSION DATE TEXTE → ISO ===
def convert_date_to_iso(date_text):
    """
    Convertit : 'Saturday, January 17, 2026' → '2026-01-17'
    """
    try:
        date_obj = datetime.strptime(date_text, "%A, %B %d, %Y")
        return date_obj.strftime("%Y-%m-%d")
    except Exception:
        return date_text


# === EXTRACTION DES COTES MONEYLINE PAR INDEX ===
def extract_ml_by_index(match_url):
    """
    Récupère les cotes MoneyLine (home / away / draw) depuis la page du match ESPN.
    Les valeurs sont insérées telles quelles dans le JSON.
    """
    try:
        res = requests.get(match_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        odds_cells = soup.find_all("div", {"data-testid": "OddsCell"})
        if len(odds_cells) < 10:
            return None

        def get_value(cell):
            val = cell.find("div", class_="FTMw")
            return val.text.strip() if val else None

        home_ml = get_value(odds_cells[1])   # 2ème
        away_ml = get_value(odds_cells[5])   # 6ème
        draw_ml = get_value(odds_cells[9])   # 10ème

        return {
            "home": home_ml,
            "away": away_ml,
            "draw": draw_ml
        }

    except Exception as e:
        print(f"⚠️ Erreur récupération cotes ML : {e}")
        return None


# === CHARGEMENT DES ÉQUIPES ===
if not os.path.exists(TEAMS_FILE):
    raise FileNotFoundError(f"❌ Fichier introuvable : {TEAMS_FILE}")

with open(TEAMS_FILE, "r", encoding="utf-8") as f:
    football_teams = json.load(f)

# === INDEX RAPIDE : league -> team_name -> data ===
teams_index = {}
for league, teams in football_teams.items():
    teams_index[league] = {}
    for t in teams:
        name_key = t["team"].strip().lower()
        teams_index[league][name_key] = t

print(f"✅ {len(teams_index)} ligues chargées depuis football_teams.json")

# === CONTENEUR DES MATCHS ===
games_of_day = {}

# === SCRAPING PRINCIPAL ===
for league_name, league_code in LEAGUES.items():
    print(f"📅 Récupération {league_name} ({today_str})")

    try:
        res = requests.get(
            BASE_URL.format(date=today_str, league=league_code),
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

        # ⚡ Uniquement les matchs du jour
        if date_text_iso != today_iso:
            continue

        for row in table.select("tbody > tr.Table__TR"):
            teams = row.select("span.Table__Team a.AnchorLink:last-child")
            score_tag = row.select_one("a.AnchorLink.at")

            if len(teams) != 2 or not score_tag:
                continue

            score = score_tag.text.strip()

            # ⚡ Uniquement les matchs non joués
            if score.lower() != "v":
                continue

            match_id = re.search(r"gameId/(\d+)", score_tag["href"])
            if not match_id:
                continue

            game_id = match_id.group(1)

            team1_name = teams[0].text.strip()
            team2_name = teams[1].text.strip()

            t1_key = team1_name.lower()
            t2_key = team2_name.lower()

            team1_data = teams_index.get(league_name, {}).get(t1_key, {})
            team2_data = teams_index.get(league_name, {}).get(t2_key, {})

            match_url = "https://www.espn.com" + score_tag["href"]

            # === RÉCUPÉRATION DES COTES ===
            ml_odds = extract_ml_by_index(match_url)
            time.sleep(1)  # pause dédiée au scraping des cotes

            games_of_day[game_id] = {
                "gameId": game_id,
                "date": date_text_iso,
                "league": league_name,

                "team1": team1_name,
                "team1_id": team1_data.get("team_id"),
                "team1_logo": team1_data.get("logo"),
                "team1_url": f"https://www.espn.com/soccer/team/_/id/{team1_data.get('team_id')}"
                if team1_data.get("team_id") else None,

                "team2": team2_name,
                "team2_id": team2_data.get("team_id"),
                "team2_logo": team2_data.get("logo"),
                "team2_url": f"https://www.espn.com/soccer/team/_/id/{team2_data.get('team_id')}"
                if team2_data.get("team_id") else None,

                "score": score,

                # 🔥 AJOUT DES COTES ICI, JUSTE APRÈS SCORE, SANS CHANGER LA STRUCTURE
                "odds": {
                    "moneyline": ml_odds
                },

                "match_url": match_url
            }

            time.sleep(0.5)  # Respect du site


# === ÉCRITURE DU JSON FINAL ===
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(list(games_of_day.values()), f, indent=2, ensure_ascii=False)

print(f"\n💾 {len(games_of_day)} matchs enrichis avec cotes ML sauvegardés dans {OUTPUT_FILE}")