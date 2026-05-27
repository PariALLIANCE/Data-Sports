import json
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

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

# ──────────────────────────────────────────────────────────────────────────────
# Zones de positions par ligue
# Chaque entrée : (position_min, position_max, label, avantage/désavantage)
# avantage = True  → bonne zone  |  avantage = False → mauvaise zone
# ──────────────────────────────────────────────────────────────────────────────
LEAGUE_ZONES = {
    "England_Premier_League": [
        (1, 4,  "UEFA Champions League",          True),
        (5, 5,  "UEFA Europa League",              True),
        (6, 6,  "UEFA Conference League Playoff",  True),
        (18, 18, "Relégation Playoff",             False),
        (19, 20, "Relégation",                     False),
    ],
    "Spain_Laliga": [
        (1, 4,  "UEFA Champions League",           True),
        (5, 6,  "UEFA Europa League",              True),
        (7, 7,  "UEFA Conference League",          True),
        (18, 18, "Relégation Playoff",             False),
        (19, 20, "Relégation",                     False),
    ],
    "Germany_Bundesliga": [
        (1, 4,  "UEFA Champions League",           True),
        (5, 5,  "UEFA Europa League",              True),
        (6, 6,  "UEFA Conference League",          True),
        (16, 16, "Relégation Playoff",             False),
        (17, 18, "Relégation",                     False),
    ],
    "France_Ligue_1": [
        (1, 3,  "UEFA Champions League",           True),
        (4, 4,  "UEFA Champions League Playoff",   True),
        (5, 5,  "UEFA Europa League",              True),
        (6, 6,  "UEFA Conference League",          True),
        (16, 16, "Relégation Playoff",             False),
        (17, 18, "Relégation",                     False),
    ],
    "Italy_Serie_A": [
        (1, 4,  "UEFA Champions League",           True),
        (5, 5,  "UEFA Europa League",              True),
        (6, 6,  "UEFA Conference League",          True),
        (18, 18, "Relégation Playoff",             False),
        (19, 20, "Relégation",                     False),
    ],
    "Portugal_Primeira_Liga": [
        (1, 4,  "UEFA Champions League",           True),
        (5, 5,  "UEFA Europa League",              True),
        (6, 6,  "UEFA Conference League",          True),
        (16, 16, "Relégation Playoff",             False),
        (17, 18, "Relégation",                     False),
    ],
    "Netherlands_Eredivisie": [
        (1, 1,  "UEFA Champions League",           True),
        (2, 4,  "UEFA Europa League",              True),
        (5, 5,  "UEFA Conference League",          True),
        (16, 16, "Relégation Playoff",             False),
        (17, 18, "Relégation",                     False),
    ],
    "Belgium_Jupiler_Pro_League": [
        (1, 1,  "UEFA Champions League Playoff",   True),
        (2, 3,  "UEFA Europa League",              True),
        (4, 4,  "UEFA Conference League",          True),
        (16, 16, "Relégation Playoff",             False),
    ],
    "Turkey_Super_Lig": [
        (1, 2,  "UEFA Champions League",           True),
        (3, 4,  "UEFA Europa League",              True),
        (5, 5,  "UEFA Conference League",          True),
        (17, 17, "Relégation Playoff",             False),
        (18, 19, "Relégation",                     False),
    ],
    "Greece_Super_League_1": [
        (1, 1,  "UEFA Champions League",           True),
        (2, 3,  "UEFA Europa League",              True),
        (4, 4,  "UEFA Conference League",          True),
        (13, 14, "Relégation Playoff",             False),
        (15, 16, "Relégation",                     False),
    ],
    "Austria_Bundesliga": [
        (1, 2,  "UEFA Champions League",           True),
        (3, 4,  "UEFA Europa League",              True),
        (5, 5,  "UEFA Conference League",          True),
        (10, 10, "Relégation Playoff",             False),
        (11, 12, "Relégation",                     False),
    ],
    "Switzerland_Super_League": [
        (1, 1,  "UEFA Champions League",           True),
        (2, 3,  "UEFA Europa League",              True),
        (4, 4,  "UEFA Conference League",          True),
        (9, 9,  "Relégation Playoff",              False),
        (10, 10, "Relégation",                     False),
    ],
    "Romania_Liga_I": [
        (1, 2,  "UEFA Conference League",          True),
        (14, 14, "Relégation Playoff",             False),
        (15, 16, "Relégation",                     False),
    ],
    "Russia_Premier_League": [
        (1, 6,  "Playoff Champions",               True),
        (13, 14, "Relégation Playoff",             False),
        (15, 16, "Relégation",                     False),
    ],
    "Sweden_Allsvenskan": [
        (1, 1,  "UEFA Conference League",          True),
        (14, 14, "Relégation Playoff",             False),
        (15, 16, "Relégation",                     False),
    ],
    "Saudi_Arabia_Pro_League": [
        (1, 4,  "AFC Champions League",            True),
        (14, 14, "Relégation Playoff",             False),
        (15, 16, "Relégation",                     False),
    ],
    "Brazil_Serie_A": [
        (1, 4,  "CONMEBOL Libertadores (Groupes)", True),
        (5, 6,  "CONMEBOL Libertadores Playoff",   True),
        (7, 12, "CONMEBOL Sudamericana",           True),
        (17, 20, "Relégation Serie B",             False),
    ],
    "Brazil_Serie_B": [
        (1, 4,  "Promotion Serie A",               True),
        (17, 20, "Relégation Serie C",             False),
    ],
    "Argentina_Primera_Nacional": [
        (1, 2,  "Promotion Primera Division",      True),
        (3, 4,  "Promotion Playoff",               True),
    ],
    "Colombia_Primera_A": [
        (1, 8,  "Playoffs Título",                 True),
        (1, 3,  "CONMEBOL Libertadores",           True),
        (4, 8,  "CONMEBOL Sudamericana",           True),
    ],
    "Chile_Primera_Division": [
        (1, 3,  "CONMEBOL Libertadores",           True),
        (4, 8,  "CONMEBOL Sudamericana",           True),
        (14, 14, "Relégation Playoff",             False),
        (15, 16, "Relégation",                     False),
    ],
    "Peru_Primera_Division": [
        (1, 2,  "CONMEBOL Libertadores",           True),
        (3, 4,  "CONMEBOL Sudamericana",           True),
        (17, 18, "Relégation",                     False),
    ],
    "Paraguay_Division_Profesional": [
        (1, 2,  "CONMEBOL Libertadores",           True),
        (3, 4,  "CONMEBOL Sudamericana",           True),
    ],
    "Venezuela_Primera_Division": [
        (1, 2,  "CONMEBOL Libertadores",           True),
        (3, 4,  "CONMEBOL Sudamericana",           True),
    ],
    "Mexico_Liga_MX": [
        (1, 4,  "Liguilla directe",                True),
        (5, 12, "Reclasificación",                 True),
    ],
    "USA_Major_League_Soccer": [
        (1, 7,  "MLS Cup Playoffs",                True),
        (8, 9,  "Playoffs wild-card",              True),
    ],
    "Japan_J1_League": [
        (1, 2,  "AFC Champions League (Elite)",    True),
        (3, 3,  "AFC Champions League Playoff",    True),
        (17, 17, "Relégation Playoff",             False),
        (18, 20, "Relégation J2",                  False),
    ],
    "China_Super_League": [
        (1, 2,  "AFC Champions League",            True),
        (3, 4,  "AFC Challenge League",            True),
        (14, 16, "Relégation",                     False),
    ],
    "England_National_League": [
        (1, 1,  "Promotion EFL League Two",        True),
        (2, 7,  "Promotion Playoff",               True),
        (22, 24, "Relégation",                     False),
    ],
    "UEFA_Champions_League": [
        (1, 8,  "Huitièmes de finale",             True),
        (9, 16, "Huitièmes Playoff",               True),
        (17, 24, "Repêchage Europa League",        True),
        (25, 36, "Élimination",                    False),
    ],
    "UEFA_Europa_League": [
        (1, 8,  "Huitièmes de finale",             True),
        (9, 16, "Huitièmes Playoff",               True),
        (17, 24, "Repêchage Conference League",    True),
        (25, 36, "Élimination",                    False),
    ],
    "FIFA_Club_World_Cup": [],  # Format variable, pas de zones fixes
}

BASE_DIR = "data/football/standings"
os.makedirs(BASE_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(BASE_DIR, "Standings.json")


def get_position_zone(league_name: str, position: int) -> dict | None:
    """
    Retourne le dictionnaire de zone pour une position donnée dans une ligue,
    ou None si la position n'est dans aucune zone définie.
    """
    zones = LEAGUE_ZONES.get(league_name, [])
    for pos_min, pos_max, label, is_advantage in zones:
        if pos_min <= position <= pos_max:
            return {
                "label": label,
                "type": "avantage" if is_advantage else "désavantage"
            }
    return None


def setup_driver():
    """Configure Chrome en mode headless pour GitHub Actions / CI"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    chrome_options.add_argument(f"user-agent={user_agent}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def fetch_standings_with_selenium(league_id):
    """Charge la page ESPN et extrait les standings avec Selenium"""
    url = f"https://www.espn.com/soccer/standings/_/league/{league_id}"
    driver = setup_driver()

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.Table--fixed-left")))
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".Table__Scroller table")))

        team_rows = driver.find_elements(By.CSS_SELECTOR, "table.Table--fixed-left tbody tr")
        stats_rows = driver.find_elements(By.CSS_SELECTOR, ".Table__Scroller table tbody tr")

        standings = []
        for i in range(min(len(team_rows), len(stats_rows))):
            team_row = team_rows[i]
            stat_row = stats_rows[i]

            pos_elem = team_row.find_element(By.CSS_SELECTOR, "span.team-position")
            position = int(pos_elem.text.strip())

            name_elem = team_row.find_element(By.CSS_SELECTOR, ".hide-mobile a")
            name = name_elem.text.strip()

            stat_cells = stat_row.find_elements(By.CSS_SELECTOR, "td span.stat-cell")
            if len(stat_cells) < 8:
                continue

            values = [cell.text.strip() for cell in stat_cells[:8]]
            gp, w, d, l, f, a, gd, p = values

            if gd.startswith('+'):
                gd = gd[1:]

            standings.append({
                "position": position,
                "name": name,
                "stats": {
                    "GP": int(gp),
                    "W": int(w),
                    "D": int(d),
                    "L": int(l),
                    "F": int(f),
                    "A": int(a),
                    "GD": int(gd),
                    "P": int(p)
                }
            })
        return standings

    except Exception as e:
        print(f"  Erreur Selenium : {e}")
        with open(f"debug_{league_id}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        return []
    finally:
        driver.quit()


def load_existing_data() -> dict:
    """Charge le fichier Standings.json existant si présent."""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Impossible de lire l'ancien fichier : {e}")
    return {}


def enrich_standings_with_zones(league_name: str, standings: list) -> list:
    """Ajoute le champ 'zone' à chaque équipe selon sa position."""
    enriched = []
    for team in standings:
        zone = get_position_zone(league_name, team["position"])
        entry = dict(team)  # copie superficielle
        if zone:
            entry["zone"] = zone
        else:
            entry["zone"] = None
        enriched.append(entry)
    return enriched


def scrape_all_leagues():
    existing_data = load_existing_data()
    all_data = {}

    for league_name, league_id in LEAGUES.items():
        try:
            print(f"🔹 Scraping {league_name}...")
            standings = fetch_standings_with_selenium(league_id)
            num_teams = len(standings)

            if num_teams == 0:
                # ── FALLBACK : conserver l'ancien classement ──────────────────
                if league_name in existing_data and existing_data[league_name].get("standings"):
                    print(f"⚠️  Aucun résultat — conservation du classement précédent pour {league_name}")
                    all_data[league_name] = existing_data[league_name]
                else:
                    print(f"❌  Aucun résultat et aucun classement précédent pour {league_name}")
                    all_data[league_name] = {
                        "total_journees": 0,
                        "position_zones": LEAGUE_ZONES.get(league_name, []),
                        "standings": []
                    }
                continue

            total_journees = num_teams * 2 - 2

            # Enrichir avec les zones de positions
            standings_enriched = enrich_standings_with_zones(league_name, standings)

            # Construire les métadonnées des zones pour la ligue
            zones_meta = [
                {
                    "positions": f"{pmin}-{pmax}" if pmin != pmax else str(pmin),
                    "label": label,
                    "type": "avantage" if adv else "désavantage"
                }
                for pmin, pmax, label, adv in LEAGUE_ZONES.get(league_name, [])
            ]

            all_data[league_name] = {
                "total_journees": total_journees,
                "position_zones": zones_meta,
                "standings": standings_enriched
            }

            print(f"✔ {num_teams} équipes — {total_journees} journées — {len(zones_meta)} zones définies pour {league_name}\n")
            time.sleep(2)

        except Exception as e:
            print(f"❌ Erreur pour {league_name}: {e}")
            # Fallback en cas d'exception inattendue
            if league_name in existing_data and existing_data[league_name].get("standings"):
                print(f"⚠️  Exception — conservation du classement précédent pour {league_name}")
                all_data[league_name] = existing_data[league_name]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)
    print(f"\n✅ Tous les classements enregistrés dans {OUTPUT_FILE}")


if __name__ == "__main__":
    scrape_all_leagues()
