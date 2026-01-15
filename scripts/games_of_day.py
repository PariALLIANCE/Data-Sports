import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
import re
import os
import time

# ================= HEADERS =================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}

# ================= DOSSIERS =================
BASE_DIR = "data/football"
TEAMS_DIR = os.path.join(BASE_DIR, "teams")
LEAGUES_DIR = os.path.join(BASE_DIR, "leagues")
OUTPUT_DIR = BASE_DIR

os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(OUTPUT_DIR, "games_of_day.json")
TEAMS_FILE = os.path.join(TEAMS_DIR, "football_teams.json")

# ================= LIGUES =================
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

# ================= DATE =================
today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ================= UTILITAIRES =================
def convert_date_to_iso(date_text):
    try:
        date_obj = datetime.strptime(date_text, "%A, %B %d, %Y")
        return date_obj.strftime("%Y-%m-%d")
    except:
        return date_text

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

# ================= FORMES RÉCENTES =================
def normalize_team_name(name):
    return name.lower().strip() if name else ""

def load_league_history(league_name):
    league_file = os.path.join(LEAGUES_DIR, f"{league_name}.json")
    if not os.path.exists(league_file):
        print(f"⚠️ Historique ligue introuvable : {league_file}")
        return []
    with open(league_file, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_recent_matches(team_name, league_matches, limit=7):
    team_norm = normalize_team_name(team_name)
    team_games = []

    for match in league_matches:
        t1 = normalize_team_name(match.get("team1", ""))
        t2 = normalize_team_name(match.get("team2", ""))

        if team_norm == t1 or team_norm == t2:
            match_copy = dict(match)
            match_copy["date"] = convert_date_to_iso(match_copy.get("date", ""))
            team_games.append(match_copy)

    team_games.sort(key=lambda x: x.get("date", ""), reverse=True)
    return team_games[:limit]

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

        return {
            "home": us_to_decimal(home_us),
            "away": us_to_decimal(away_us),
            "draw": us_to_decimal(draw_us)
        }
    except Exception as e:
        print(f"⚠️ Erreur récupération cotes ML : {e}")
        return None

# ================= JOUEURS CLÉS =================
def parse_players(section):
    players = []
    athletes = section.find_all("a", class_="Athlete")

    for a in athletes:
        name_tag = a.find("span", class_="Athlete__PlayerName")
        stats_tag = a.find("div", class_="Athlete__Stats")

        name = name_tag.get_text(strip=True) if name_tag else None
        stats_block = stats_tag.get_text("\n", strip=True) if stats_tag else None

        if name:
            players.append({
                "name": name,
                "raw_stats": stats_block
            })
    return players

def extract_top_scorers_and_assists(match_url):
    try:
        res = requests.get(match_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        top_scorers_header = soup.find("h3", string="Top Scorers")
        most_assists_header = soup.find("h3", string="Most Assists")

        if not top_scorers_header or not most_assists_header:
            return {"top_scorers": [], "most_assists": []}

        top_scorers_section = top_scorers_header.find_parent("section", class_="Card")
        most_assists_section = most_assists_header.find_parent("section", class_="Card")

        top_scorers = parse_players(top_scorers_section) if top_scorers_section else []
        most_assists = parse_players(most_assists_section) if most_assists_section else []

        return {
            "top_scorers": top_scorers,
            "most_assists": most_assists
        }

    except Exception as e:
        print(f"⚠️ Erreur récupération joueurs clés : {e}")
        return {"top_scorers": [], "most_assists": []}

# ================= CHARGEMENT DES ÉQUIPES =================
if not os.path.exists(TEAMS_FILE):
    raise FileNotFoundError(f"❌ Fichier introuvable : {TEAMS_FILE}")

with open(TEAMS_FILE, "r", encoding="utf-8") as f:
    football_teams = json.load(f)

teams_index = {}
for league, teams in football_teams.items():
    teams_index[league] = {}
    for t in teams:
        teams_index[league][t["team"].strip().lower()] = t

print(f"✅ {len(teams_index)} ligues chargées")

# ================= SCRAPING PRINCIPAL =================
games_of_day = {}
league_history_cache = {}

for league_name, league_code in LEAGUES.items():
    print(f"📅 {league_name}")

    try:
        res = requests.get(
            BASE_URL.format(date=today_str, league=league_code),
            headers=HEADERS,
            timeout=15
        )
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        print(f"⚠️ Erreur réseau {league_name}: {e}")
        continue

    if league_name not in league_history_cache:
        league_history_cache[league_name] = load_league_history(league_name)

    league_history = league_history_cache[league_name]

    for table in soup.select("div.ResponsiveTable"):
        date_title = table.select_one("div.Table__Title")
        date_text = date_title.text.strip() if date_title else today_str
        date_text_iso = convert_date_to_iso(date_text)

        if date_text_iso != today_iso:
            continue

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

            team1_name = teams[0].text.strip()
            team2_name = teams[1].text.strip()

            team1_data = teams_index.get(league_name, {}).get(team1_name.lower(), {})
            team2_data = teams_index.get(league_name, {}).get(team2_name.lower(), {})

            match_url = "https://www.espn.com" + score_tag["href"]

            # Cotes
            ml_odds = extract_ml_by_index(match_url)
            time.sleep(1)

            # Joueurs clés
            key_players = extract_top_scorers_and_assists(match_url)
            time.sleep(1)

            # 🔥 Forme récente intégrée directement
            recent_team1 = extract_recent_matches(team1_name, league_history)
            recent_team2 = extract_recent_matches(team2_name, league_history)

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

                "recent_form": {
                    "match1": {
                        "team": team1_name,
                        "last_matches": recent_team1
                    },
                    "match2": {
                        "team": team2_name,
                        "last_matches": recent_team2
                    }
                },

                "odds": {
                    "moneyline": ml_odds,
                    "key_players": {
                        "top_scorers": key_players.get("top_scorers", []),
                        "most_assists": key_players.get("most_assists", [])
                    }
                },

                "match_url": match_url
            }

            time.sleep(0.5)

# ================= SAUVEGARDE =================
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(list(games_of_day.values()), f, indent=2, ensure_ascii=False)

print(f"\n💾 {len(games_of_day)} matchs sauvegardés avec forme récente + cotes + joueurs clés dans {OUTPUT_FILE}")