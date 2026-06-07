import json
from datetime import datetime, timezone
import re
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# ================= DRIVER SELENIUM =================
def make_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
    )
    options.add_argument("--lang=en-US")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    return driver

def get_soup(driver, url, wait_selector=None, timeout=15):
    driver.get(url)
    if wait_selector:
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
            )
        except Exception:
            pass
    return BeautifulSoup(driver.page_source, "html.parser")

# ================= DOSSIERS =================
BASE_DIR      = "data/football"
TEAMS_DIR     = os.path.join(BASE_DIR, "teams")
STANDINGS_DIR = os.path.join(BASE_DIR, "standings")

os.makedirs(BASE_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(BASE_DIR, "games_of_day.json")
TEAMS_FILE  = os.path.join(TEAMS_DIR, "football_teams.json")

# ================= LIGUES =================
LEAGUES = {
    "England_Premier_League":        "eng.1",
    "Spain_Laliga":                  "esp.1",
    "Germany_Bundesliga":            "ger.1",
    "Argentina_Primera_Nacional":    "arg.2",
    "Austria_Bundesliga":            "aut.1",
    "Belgium_Jupiler_Pro_League":    "bel.1",
    "Brazil_Serie_A":                "bra.1",
    "Brazil_Serie_B":                "bra.2",
    "Chile_Primera_Division":        "chi.1",
    "China_Super_League":            "chn.1",
    "Colombia_Primera_A":            "col.1",
    "England_National_League":       "eng.5",
    "France_Ligue_1":                "fra.1",
    "Greece_Super_League_1":         "gre.1",
    "Italy_Serie_A":                 "ita.1",
    "Japan_J1_League":               "jpn.1",
    "Mexico_Liga_MX":                "mex.1",
    "Netherlands_Eredivisie":        "ned.1",
    "Paraguay_Division_Profesional": "par.1",
    "Peru_Primera_Division":         "per.1",
    "Portugal_Primeira_Liga":        "por.1",
    "Romania_Liga_I":                "rou.1",
    "Russia_Premier_League":         "rus.1",
    "Saudi_Arabia_Pro_League":       "ksa.1",
    "Sweden_Allsvenskan":            "swe.1",
    "Switzerland_Super_League":      "sui.1",
    "Turkey_Super_Lig":              "tur.1",
    "USA_Major_League_Soccer":       "usa.1",
    "Venezuela_Primera_Division":    "ven.1",
    "UEFA_Champions_League":         "uefa.champions",
    "UEFA_Europa_League":            "uefa.europa",
    "FIFA_Club_World_Cup":           "fifa.cwc",
    "FA_Cup":                        "eng.fa",
    "EFL_Cup":                       "eng.league_cup",
    "Copa_del_Rey":                  "esp.copa_del_rey",
    "DFB_Pokal":                     "ger.dfb_pokal",
    "Coppa_Italia":                  "ita.coppa_italia",
    "Coupe_de_France":               "fra.coupe_de_france",
    "KNVB_Cup":                      "ned.cup",
    "Taca_de_Portugal":              "por.taca.portugal",
    "Kings_Cup_Saudi":               "ksa.kings.cup",
}

BASE_URL = "https://www.espn.com/soccer/schedule/_/date/{date}/league/{league}"

# ================= DATE =================
today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ================= UTILITAIRES =================
def convert_date_to_iso(date_text):
    try:
        return datetime.strptime(date_text, "%A, %B %d, %Y").strftime("%Y-%m-%d")
    except:
        return date_text

def convert_time_to_utc(time_str):
    try:
        dt = datetime.strptime(time_str, "%I:%M %p")
        return f"{(dt.hour - 4) % 24:02d}:{dt.minute:02d}"
    except:
        return time_str

def us_to_decimal(val):
    if not val:
        return None
    try:
        n = int(val.replace("+", "").strip())
        return round(1 + (n / 100), 2) if n > 0 else round(1 + (100 / abs(n)), 2)
    except:
        return None

def normalize(name):
    return name.lower().strip() if name else ""

# ================= EXTRACTION COTES ESPN =================
def extract_ml_odds(driver, match_url):
    try:
        soup = get_soup(
            driver,
            match_url,
            wait_selector='[data-testid="OddsCell"]',
            timeout=15,
        )

        cells = soup.find_all("div", {"data-testid": "OddsCell"})
        if len(cells) < 7:
            return None

        def read(cell):
            return cell.get_text(strip=True) or None

        def is_valid(val):
            if not val:
                return False
            try:
                int(val.replace("+", "").replace("-", ""))
                return True
            except:
                return False

        home_us = read(cells[0])
        away_us = read(cells[3])
        draw_us = read(cells[6])

        if not all(is_valid(v) for v in [home_us, away_us, draw_us]):
            return None

        return {
            "home": us_to_decimal(home_us),
            "away": us_to_decimal(away_us),
            "draw": us_to_decimal(draw_us),
        }

    except Exception as e:
        print(f"  ⚠️ Erreur cotes : {e}")
        return None

# ================= EXTRACTION STATS DU MATCH =================
def extract_match_stats(driver, match_url):
    """
    Scrape la page ESPN du match pour récupérer les stats clés.
    Retourne un dict { label: { home: val, away: val } } ou {} si rien trouvé.

    ESPN affiche les stats dans une section identifiable via
    la classe 'StatCellContent' ou des blocs 'GameStat'.
    On tente plusieurs sélecteurs pour couvrir les variantes de layout.
    """
    stats = {}
    try:
        # La page du match a les stats sous l'onglet "Match Stats"
        # ESPN charge les stats dans le HTML initial si le match est terminé,
        # sinon elles peuvent être absentes pour les matchs à venir.
        soup = get_soup(
            driver,
            match_url,
            wait_selector=".StatCellContent, .GameStat, [class*='gamepackage-matchup-charts']",
            timeout=15,
        )

        # ── Tentative 1 : layout "StatCellContent" (matchs terminés récents) ──
        stat_rows = soup.select("div.StatCellContent")
        if stat_rows:
            # Structure : [home_val, label, away_val] répété
            values = [el.get_text(strip=True) for el in stat_rows]
            i = 0
            while i + 2 < len(values):
                home_val = values[i]
                label    = values[i + 1]
                away_val = values[i + 2]
                if label and not label.replace(" ", "").isdigit():
                    stats[label] = {"home": home_val, "away": away_val}
                    i += 3
                else:
                    i += 1
            if stats:
                return stats

        # ── Tentative 2 : layout "GameStat" ──
        game_stat_rows = soup.select("div.GameStat")
        if game_stat_rows:
            for row in game_stat_rows:
                cols = row.select("div")
                texts = [c.get_text(strip=True) for c in cols if c.get_text(strip=True)]
                if len(texts) >= 3:
                    stats[texts[1]] = {"home": texts[0], "away": texts[2]}
            if stats:
                return stats

        # ── Tentative 3 : layout gamepackage (ancienne structure ESPN) ──
        gp_rows = soup.select("div.gamepackage-matchup-charts tr")
        if gp_rows:
            for row in gp_rows:
                cells = row.select("td")
                if len(cells) == 3:
                    home_val = cells[0].get_text(strip=True)
                    label    = cells[1].get_text(strip=True)
                    away_val = cells[2].get_text(strip=True)
                    if label:
                        stats[label] = {"home": home_val, "away": away_val}
            if stats:
                return stats

        # ── Tentative 4 : sélecteur générique basé sur aria-label / data-stat ──
        rows = soup.select("tr[data-stat], div[data-stat]")
        for row in rows:
            label    = row.get("data-stat", "")
            children = row.select("td, div.value")
            if len(children) >= 2 and label:
                stats[label] = {
                    "home": children[0].get_text(strip=True),
                    "away": children[1].get_text(strip=True),
                }
        if stats:
            return stats

    except Exception as e:
        print(f"  ⚠️ Erreur stats : {e}")

    return {}  # stats indisponibles (match à venir, page incomplète, etc.)

# ================= CHARGEMENT ÉQUIPES =================
if not os.path.exists(TEAMS_FILE):
    raise FileNotFoundError(f"❌ Fichier introuvable : {TEAMS_FILE}")

with open(TEAMS_FILE, "r", encoding="utf-8") as f:
    football_teams = json.load(f)

teams_index = {
    league: {t["team"].strip().lower(): t for t in teams}
    for league, teams in football_teams.items()
}
print(f"✅ {len(teams_index)} ligues chargées")

# ================= CHARGEMENT STANDINGS =================
STANDINGS_FILE = os.path.join(STANDINGS_DIR, "Standings.json")
standings_data = {}
if os.path.exists(STANDINGS_FILE):
    with open(STANDINGS_FILE, "r", encoding="utf-8") as f:
        standings_data = json.load(f)
else:
    print(f"⚠️ Standings introuvables : {STANDINGS_FILE}")

# ================= SCRAPING PRINCIPAL =================
games_of_day = {}
driver = make_driver()

try:
    for league_name, league_code in LEAGUES.items():
        print(f"\n📅 {league_name}")

        try:
            soup = get_soup(
                driver,
                BASE_URL.format(date=today_str, league=league_code),
                wait_selector="div.ResponsiveTable",
                timeout=15,
            )
        except Exception as e:
            print(f"  ⚠️ Erreur réseau : {e}")
            continue

        standing = standings_data.get(league_name, [])

        for table in soup.select("div.ResponsiveTable"):
            date_tag = table.select_one("div.Table__Title")
            date_iso = convert_date_to_iso(date_tag.text.strip() if date_tag else today_str)

            if date_iso != today_iso:
                continue

            for row in table.select("tbody > tr.Table__TR"):
                teams     = row.select("span.Table__Team a.AnchorLink:last-child")
                score_tag = row.select_one("a.AnchorLink.at")
                time_tag  = row.select_one("td.date__col a")

                if len(teams) != 2 or not score_tag:
                    continue
                if score_tag.text.strip().lower() != "v":
                    continue

                match_id = re.search(r"gameId/(\d+)", score_tag["href"])
                if not match_id:
                    continue

                game_id   = match_id.group(1)
                team1     = teams[0].text.strip()
                team2     = teams[1].text.strip()
                match_url = "https://www.espn.com" + score_tag["href"]
                raw_time  = time_tag.text.strip() if time_tag else None

                t1_data = teams_index.get(league_name, {}).get(team1.lower(), {})
                t2_data = teams_index.get(league_name, {}).get(team2.lower(), {})

                # ── Cotes ──
                ml = extract_ml_odds(driver, match_url)
                time.sleep(1)

                # ── Stats ──
                match_stats = extract_match_stats(driver, match_url)
                time.sleep(0.5)

                games_of_day[game_id] = {
                    "gameId":    game_id,
                    "date":      date_iso,
                    "time_utc":  convert_time_to_utc(raw_time) if raw_time else None,
                    "league":    league_name,
                    "match_url": match_url,

                    "home": {
                        "team":    team1,
                        "team_id": t1_data.get("team_id"),
                        "logo":    t1_data.get("logo"),
                        "url":     f"https://www.espn.com/soccer/team/_/id/{t1_data['team_id']}" if t1_data.get("team_id") else None,
                    },
                    "away": {
                        "team":    team2,
                        "team_id": t2_data.get("team_id"),
                        "logo":    t2_data.get("logo"),
                        "url":     f"https://www.espn.com/soccer/team/_/id/{t2_data['team_id']}" if t2_data.get("team_id") else None,
                    },

                    "odds": {
                        "home": ml["home"] if ml else None,
                        "away": ml["away"] if ml else None,
                        "draw": ml["draw"] if ml else None,
                    },

                    "stats": match_stats,  # {} si match à venir / stats indisponibles
                }

                odds_str  = f"✅ {ml['home']} / {ml['draw']} / {ml['away']}" if ml else "ℹ️  pas de cotes"
                stats_str = f"📊 {len(match_stats)} stats" if match_stats else "📊 pas de stats"
                print(f"  {team1} vs {team2} → {odds_str} | {stats_str}")
                time.sleep(0.5)

finally:
    driver.quit()

# ================= SAUVEGARDE ATOMIQUE =================
tmp_file = OUTPUT_FILE + ".tmp"
with open(tmp_file, "w", encoding="utf-8") as f:
    json.dump(list(games_of_day.values()), f, indent=2, ensure_ascii=False)
os.replace(tmp_file, OUTPUT_FILE)

print(f"\n💾 {len(games_of_day)} matchs sauvegardés → {OUTPUT_FILE}")