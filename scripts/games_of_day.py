import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
import re
import os
import time
from difflib import SequenceMatcher

# ================= HEADERS =================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}

# ================= DOSSIERS =================
BASE_DIR = "data/football"
TEAMS_DIR = os.path.join(BASE_DIR, "teams")
LEAGUES_DIR = os.path.join(BASE_DIR, "leagues")
STANDINGS_DIR = os.path.join(BASE_DIR, "standings")
OUTPUT_DIR = BASE_DIR

os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(OUTPUT_DIR, "games_of_day.json")
TEAMS_FILE = os.path.join(TEAMS_DIR, "football_teams.json")

# ================= CLÉS API (rotation) =================
ODDS_API_KEYS = [k for k in [
    os.environ.get("ODDS1"),
    os.environ.get("ODDS2"),
    os.environ.get("ODDS3"),
    os.environ.get("ODDS4"),
    os.environ.get("ODDS5"),
] if k]

if not ODDS_API_KEYS:
    raise EnvironmentError("❌ Aucune clé ODDS trouvée dans les variables d'environnement (ODDS1..ODDS5)")

print(f"✅ {len(ODDS_API_KEYS)} clé(s) Odds-API chargée(s)")

_key_index = 0

def next_api_key():
    """Retourne la prochaine clé en rotation circulaire."""
    global _key_index
    key = ODDS_API_KEYS[_key_index % len(ODDS_API_KEYS)]
    _key_index += 1
    return key

# ================= LIGUES ESPN =================
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

ODDS_API_MAP_URL = "https://raw.githubusercontent.com/PariALLIANCE/Data-Sports/main/data/football/odds-api-paire.json"

# ================= DATE =================
today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ================= UTILITAIRES ESPN =================
def convert_date_to_iso(date_text):
    try:
        date_obj = datetime.strptime(date_text, "%A, %B %d, %Y")
        return date_obj.strftime("%Y-%m-%d")
    except:
        return date_text

def convert_time_to_utc(time_str):
    try:
        dt = datetime.strptime(time_str, "%I:%M %p")
        dt_utc_hour = (dt.hour + 4) % 24
        return f"{dt_utc_hour:02d}:{dt.minute:02d}"
    except:
        return time_str

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

def normalize_team_name(name):
    return name.lower().strip() if name else ""

# ================= FORMES RÉCENTES =================
def load_league_history(league_name):
    league_file = os.path.join(LEAGUES_DIR, f"{league_name}.json")
    if not os.path.exists(league_file):
        print(f"  ⚠️ Historique ligue introuvable : {league_file}")
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

def extract_h2h_matches(team1_name, team2_name, league_matches, limit=7):
    t1_norm = normalize_team_name(team1_name)
    t2_norm = normalize_team_name(team2_name)
    h2h_games = []
    for match in league_matches:
        m_t1 = normalize_team_name(match.get("team1", ""))
        m_t2 = normalize_team_name(match.get("team2", ""))
        if (t1_norm == m_t1 and t2_norm == m_t2) or (t1_norm == m_t2 and t2_norm == m_t1):
            match_copy = dict(match)
            match_copy["date"] = convert_date_to_iso(match_copy.get("date", ""))
            h2h_games.append(match_copy)
    h2h_games.sort(key=lambda x: x.get("date", ""), reverse=True)
    return h2h_games[:limit]

# ================= EXTRACTION COTES ESPN =================
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
        print(f"  ⚠️ Erreur cotes ESPN : {e}")
        return None

# ================= FUZZY MATCH =================
def normalize_odds(name):
    name = name.lower()
    name = re.sub(r"[àáâãäå]", "a", name)
    name = re.sub(r"[èéêë]", "e", name)
    name = re.sub(r"[ìíîï]", "i", name)
    name = re.sub(r"[òóôõö]", "o", name)
    name = re.sub(r"[ùúûü]", "u", name)
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    return name.strip()

def token_set_ratio(a, b):
    a_t = set(normalize_odds(a).split())
    b_t = set(normalize_odds(b).split())
    inter = a_t & b_t
    t0 = " ".join(sorted(inter))
    t1 = " ".join(sorted(inter | (a_t - b_t)))
    t2 = " ".join(sorted(inter | (b_t - a_t)))
    return max(
        SequenceMatcher(None, t0, t1).ratio(),
        SequenceMatcher(None, t0, t2).ratio(),
        SequenceMatcher(None, t1, t2).ratio(),
    )

def is_same_match(a, b, threshold=0.70):
    return token_set_ratio(a, b) >= threshold

def match_game(game, odds_games):
    t1, t2 = game["team1"], game["team2"]
    for og in odds_games:
        h, a = og["home_team"], og["away_team"]
        if (t1 == h and t2 == a) or (t1 == a and t2 == h):
            return og
        if (is_same_match(t1, h) and is_same_match(t2, a)) or \
           (is_same_match(t1, a) and is_same_match(t2, h)):
            return og
    return None

# ================= ODDS-API FETCH AVEC ROTATION =================
odds_cache = {}

def fetch_odds(sport_key):
    if sport_key in odds_cache:
        return odds_cache[sport_key]

    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {"regions": "eu", "markets": "h2h"}

    # Tente chaque clé dans l'ordre de rotation jusqu'à succès
    for attempt in range(len(ODDS_API_KEYS)):
        key = next_api_key()
        try:
            print(f"  🌐 Odds-API → {sport_key} (clé ...{key[-4:]})")
            r = requests.get(url, params={**params, "apiKey": key}, timeout=15)

            if r.status_code == 200:
                data = r.json()
                odds_cache[sport_key] = data
                return data

            elif r.status_code == 401:
                print(f"  ⛔ Clé invalide (...{key[-4:]}) — passage à la suivante")
                continue

            elif r.status_code == 429:
                print(f"  ⚠️ Quota dépassé (...{key[-4:]}) — passage à la suivante")
                continue

            else:
                print(f"  ⚠️ Erreur {r.status_code} avec clé ...{key[-4:]} — passage à la suivante")
                continue

        except requests.exceptions.Timeout:
            print(f"  ⚠️ Timeout avec clé ...{key[-4:]} — passage à la suivante")
            continue
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️ Erreur réseau avec clé ...{key[-4:]} : {e} — passage à la suivante")
            continue

    print(f"  ❌ Toutes les clés ont échoué pour {sport_key}")
    odds_cache[sport_key] = []
    return []

def get_best_bookmaker_h2h(odds_game):
    best = None
    best_score = 0
    for b in odds_game.get("bookmakers", []):
        for m in b.get("markets", []):
            if m.get("key") != "h2h":
                continue
            score = len(m.get("outcomes", []))
            if score > best_score:
                best_score = score
                best = b
    if not best:
        return None
    h2h = next((m for m in best["markets"] if m["key"] == "h2h"), None)
    return {
        "bookmaker": best["title"],
        "h2h": h2h["outcomes"] if h2h else []
    }

# ================= CHARGEMENT MAPPING ODDS-API =================
print("📥 Chargement du mapping Odds-API...")
league_map = requests.get(ODDS_API_MAP_URL).json()

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

# ================= CHARGEMENT DES STANDINGS =================
STANDINGS_FILE = os.path.join(STANDINGS_DIR, "Standings.json")
if os.path.exists(STANDINGS_FILE):
    with open(STANDINGS_FILE, "r", encoding="utf-8") as f:
        standings_data = json.load(f)
else:
    standings_data = {}
    print(f"⚠️ Standings introuvables : {STANDINGS_FILE}")

def get_league_standing(league_name):
    return standings_data.get(league_name, [])

# ================= SCRAPING PRINCIPAL =================
games_of_day = {}
league_history_cache = {}

for league_name, league_code in LEAGUES.items():
    print(f"\n📅 {league_name}")

    try:
        res = requests.get(
            BASE_URL.format(date=today_str, league=league_code),
            headers=HEADERS,
            timeout=15
        )
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        print(f"  ⚠️ Erreur réseau ESPN : {e}")
        continue

    # Cotes Odds-API pour cette ligue
    odds_data = []
    if league_name in league_map:
        sport_key = league_map[league_name]["id"]
        odds_data = fetch_odds(sport_key)

    if league_name not in league_history_cache:
        league_history_cache[league_name] = load_league_history(league_name)

    league_history = league_history_cache[league_name]
    league_standing = get_league_standing(league_name)

    for table in soup.select("div.ResponsiveTable"):
        date_title = table.select_one("div.Table__Title")
        date_text = date_title.text.strip() if date_title else today_str
        date_text_iso = convert_date_to_iso(date_text)

        if date_text_iso != today_iso:
            continue

        for row in table.select("tbody > tr.Table__TR"):
            teams = row.select("span.Table__Team a.AnchorLink:last-child")
            score_tag = row.select_one("a.AnchorLink.at")

            time_tag = row.select_one("td.date__col a")
            raw_time = time_tag.text.strip() if time_tag else None
            match_time_utc = convert_time_to_utc(raw_time) if raw_time else None

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

            # Recherche cotes bookmaker
            bookmaker_h2h = None
            if odds_data:
                game_stub = {"team1": team1_name, "team2": team2_name}
                matched = match_game(game_stub, odds_data)
                if matched:
                    bookmaker_h2h = get_best_bookmaker_h2h(matched)
                    print(f"  ✅ {team1_name} vs {team2_name} → {bookmaker_h2h['bookmaker'] if bookmaker_h2h else 'no odds'}")
                else:
                    print(f"  ❌ No odds match → {team1_name} vs {team2_name}")

            # Skip si pas de cotes bookmaker
            if not bookmaker_h2h:
                continue

            team1_data = teams_index.get(league_name, {}).get(team1_name.lower(), {})
            team2_data = teams_index.get(league_name, {}).get(team2_name.lower(), {})

            match_url = "https://www.espn.com" + score_tag["href"]

            ml_odds = extract_ml_by_index(match_url)
            time.sleep(1)

            recent_team1 = extract_recent_matches(team1_name, league_history)
            recent_team2 = extract_recent_matches(team2_name, league_history)
            h2h_matches = extract_h2h_matches(team1_name, team2_name, league_history)

            games_of_day[game_id] = {
                "gameId": game_id,
                "date": date_text_iso,
                "time_utc": match_time_utc,
                "league": league_name,

                "team1": team1_name,
                "team1_id": team1_data.get("team_id"),
                "team1_logo": team1_data.get("logo"),
                "team1_url": f"https://www.espn.com/soccer/team/_/id/{team1_data.get('team_id')}" if team1_data.get("team_id") else None,

                "team2": team2_name,
                "team2_id": team2_data.get("team_id"),
                "team2_logo": team2_data.get("logo"),
                "team2_url": f"https://www.espn.com/soccer/team/_/id/{team2_data.get('team_id')}" if team2_data.get("team_id") else None,

                "score": score,

                "recent_form": {
                    "match1": {"team": team1_name, "last_matches": recent_team1},
                    "match2": {"team": team2_name, "last_matches": recent_team2}
                },

                "h2h": h2h_matches,

                "odds": {
                    "moneyline": ml_odds,
                    "bookmaker_h2h": bookmaker_h2h
                },

                "match_url": match_url,
                "league_standing": league_standing
            }

            time.sleep(0.5)

# ================= SAUVEGARDE =================
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(list(games_of_day.values()), f, indent=2, ensure_ascii=False)

print(f"\n💾 {len(games_of_day)} matchs sauvegardés dans {OUTPUT_FILE}")