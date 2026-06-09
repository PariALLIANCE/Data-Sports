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
STANDINGS_DIR = os.path.join(BASE_DIR, "standings")

os.makedirs(BASE_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(BASE_DIR, "games_of_day.json")

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

def extract_team_id_from_logo(logo_url):
    """Extrait le team_id depuis l'URL du logo ESPN.
    Ex: https://a.espncdn.com/i/teamlogos/soccer/500/6272.png → '6272'
    """
    if not logo_url:
        return None
    match = re.search(r"/(\d+)\.png$", logo_url)
    return match.group(1) if match else None

# ================= EXTRACTION LOGOS DEPUIS LA PAGE SCHEDULE =================
def extract_logos_from_row(row):
    """
    Extrait les URLs des logos home/away depuis les <img data-testid="prism-image">
    présents dans la ligne du tableau de schedule ESPN.
    Retourne (logo_home, logo_away) ou (None, None) si non trouvés.
    """
    imgs = row.select('img[data-testid="prism-image"]')
    logo_home = imgs[0]["src"] if len(imgs) >= 1 else None
    logo_away = imgs[1]["src"] if len(imgs) >= 2 else None
    return logo_home, logo_away

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
    stats = {}
    try:
        soup = get_soup(
            driver,
            match_url,
            wait_selector=".StatCellContent, .GameStat, [class*='gamepackage-matchup-charts']",
            timeout=15,
        )

        # ── Tentative 1 : layout "StatCellContent" ──
        stat_rows = soup.select("div.StatCellContent")
        if stat_rows:
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

        # ── Tentative 4 : sélecteur générique data-stat ──
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

    return {}

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

                # ── Logos extraits directement depuis la ligne du tableau ──
                logo_home, logo_away = extract_logos_from_row(row)
                team_id_home = extract_team_id_from_logo(logo_home)
                team_id_away = extract_team_id_from_logo(logo_away)

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
                        "team_id": team_id_home,
                        "logo":    logo_home,
                        "url":     f"https://www.espn.com/soccer/team/_/id/{team_id_home}" if team_id_home else None,
                    },
                    "away": {
                        "team":    team2,
                        "team_id": team_id_away,
                        "logo":    logo_away,
                        "url":     f"https://www.espn.com/soccer/team/_/id/{team_id_away}" if team_id_away else None,
                    },

                    "odds": {
                        "home": ml["home"] if ml else None,
                        "away": ml["away"] if ml else None,
                        "draw": ml["draw"] if ml else None,
                    },

                    "stats": match_stats,
                }

                odds_str  = f"✅ {ml['home']} / {ml['draw']} / {ml['away']}" if ml else "ℹ️  pas de cotes"
                stats_str = f"📊 {len(match_stats)} stats" if match_stats else "📊 pas de stats"
                logo_str  = f"🖼️  {team_id_home} / {team_id_away}" if team_id_home else "🖼️  logos manquants"
                print(f"  {team1} vs {team2} → {odds_str} | {stats_str} | {logo_str}")
                time.sleep(0.5)

finally:
    driver.quit()

# ================= SAUVEGARDE ATOMIQUE =================
tmp_file = OUTPUT_FILE + ".tmp"
with open(tmp_file, "w", encoding="utf-8") as f:
    json.dump(list(games_of_day.values()), f, indent=2, ensure_ascii=False)
os.replace(tmp_file, OUTPUT_FILE)

print(f"\n💾 {len(games_of_day)} matchs sauvegardés → {OUTPUT_FILE}")