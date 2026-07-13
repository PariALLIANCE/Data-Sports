import json
import os
import time
from datetime import datetime
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
}

# ──────────────────────────────────────────────────────────────────────────────
# Paramètres de scraping multi-saisons
# ──────────────────────────────────────────────────────────────────────────────
START_SEASON = 2023
CURRENT_YEAR = datetime.now().year


def get_historical_seasons(active_season: int) -> list:
    """Saisons antérieures à la saison active : de START_SEASON à active_season - 1."""
    return list(range(START_SEASON, active_season))


# ──────────────────────────────────────────────────────────────────────────────
# Ligues dont la page ESPN utilise des sous-groupes (subgroup-headers).
# ──────────────────────────────────────────────────────────────────────────────
SUBGROUP_LEAGUES = set()

# ──────────────────────────────────────────────────────────────────────────────
# Ligues avec deux phases distinctes.
# ──────────────────────────────────────────────────────────────────────────────
MULTI_PHASE_LEAGUES = {
    "Belgium_Jupiler_Pro_League": {
        "regular": "https://www.espn.com/soccer/standings/_/league/BEL.1/seasontype/1",
        "playoffs": "https://www.espn.com/soccer/standings/_/league/BEL.1/seasontype/2",
        "regular_journees": 30,
        "playoff_max_journees": 10,
        "phase1_label": "regular_season",
        "phase2_label": "playoffs",
        "phase2_is_subgroup": True,
    },
    "Mexico_Liga_MX": {
        "regular": "https://www.espn.com/soccer/standings/_/league/MEX.1/seasontype/1",
        "playoffs": "https://www.espn.com/soccer/standings/_/league/MEX.1/seasontype/2",
        "regular_journees": 17,
        "playoff_max_journees": 17,
        "phase1_label": "apertura",
        "phase2_label": "clausura",
        "phase2_is_subgroup": False,
    },
}

LEAGUE_ZONES = {
    "Belgium_Jupiler_Pro_League": [
        (1,  6,  "Championship Playoffs",  True),
        (7,  12, "European Playoffs",      True),
        (13, 16, "Relegation Playoffs",    False),
    ],
    "Belgium_Jupiler_Pro_League_Playoffs": [
        (1,  1,  "Champion + UEFA Champions League",   True),
        (2,  2,  "UEFA Champions League",              True),
        (3,  4,  "UEFA Europa League",                 True),
        (5,  5,  "UEFA Conference League",             True),
        (6,  6,  "Éliminé compétitions UEFA",          False),
        (7,  7,  "UEFA Conference League Playoff",     True),
        (8,  12, "Éliminé",                            False),
        (13, 13, "Maintien garanti",                   True),
        (14, 14, "Playoff Relégation vs Challenger",   False),
        (15, 16, "Relégation",                         False),
    ],
    "Mexico_Liga_MX": [
        (1,  6,  "Liguilla directe (Quarts de finale)", True),
        (7,  10, "Play-in (Reclasificación)",           True),
    ],
    "Mexico_Liga_MX_Clausura": [
        (1,  6,  "Liguilla directe (Quarts de finale)", True),
        (7,  10, "Play-in (Reclasificación)",           True),
    ],
    "England_Premier_League": [
        (1,  4,  "UEFA Champions League",          True),
        (5,  5,  "UEFA Europa League",             True),
        (6,  6,  "UEFA Conference League Playoff", True),
        (18, 18, "Relégation Playoff",             False),
        (19, 20, "Relégation",                     False),
    ],
    "Spain_Laliga": [
        (1,  4,  "UEFA Champions League",          True),
        (5,  6,  "UEFA Europa League",             True),
        (7,  7,  "UEFA Conference League",         True),
        (18, 18, "Relégation Playoff",             False),
        (19, 20, "Relégation",                     False),
    ],
    "Germany_Bundesliga": [
        (1,  4,  "UEFA Champions League",          True),
        (5,  5,  "UEFA Europa League",             True),
        (6,  6,  "UEFA Conference League",         True),
        (16, 16, "Relégation Playoff",             False),
        (17, 18, "Relégation",                     False),
    ],
    "France_Ligue_1": [
        (1,  3,  "UEFA Champions League",          True),
        (4,  4,  "UEFA Champions League Playoff",  True),
        (5,  5,  "UEFA Europa League",             True),
        (6,  6,  "UEFA Conference League",         True),
        (16, 16, "Relégation Playoff",             False),
        (17, 18, "Relégation",                     False),
    ],
    "Italy_Serie_A": [
        (1,  4,  "UEFA Champions League",          True),
        (5,  5,  "UEFA Europa League",             True),
        (6,  6,  "UEFA Conference League",         True),
        (18, 18, "Relégation Playoff",             False),
        (19, 20, "Relégation",                     False),
    ],
    "Portugal_Primeira_Liga": [
        (1,  4,  "UEFA Champions League",          True),
        (5,  5,  "UEFA Europa League",             True),
        (6,  6,  "UEFA Conference League",         True),
        (16, 16, "Relégation Playoff",             False),
        (17, 18, "Relégation",                     False),
    ],
    "Netherlands_Eredivisie": [
        (1,  1,  "UEFA Champions League",          True),
        (2,  4,  "UEFA Europa League",             True),
        (5,  5,  "UEFA Conference League",         True),
        (16, 16, "Relégation Playoff",             False),
        (17, 18, "Relégation",                     False),
    ],
    "Turkey_Super_Lig": [
        (1,  2,  "UEFA Champions League",          True),
        (3,  4,  "UEFA Europa League",             True),
        (5,  5,  "UEFA Conference League",         True),
        (17, 17, "Relégation Playoff",             False),
        (18, 19, "Relégation",                     False),
    ],
    "Greece_Super_League_1": [
        (1,  1,  "UEFA Champions League",          True),
        (2,  3,  "UEFA Europa League",             True),
        (4,  4,  "UEFA Conference League",         True),
        (13, 14, "Relégation Playoff",             False),
        (15, 16, "Relégation",                     False),
    ],
    "Austria_Bundesliga": [
        (1,  2,  "UEFA Champions League",          True),
        (3,  4,  "UEFA Europa League",             True),
        (5,  5,  "UEFA Conference League",         True),
        (10, 10, "Relégation Playoff",             False),
        (11, 12, "Relégation",                     False),
    ],
    "Switzerland_Super_League": [
        (1,  1,  "UEFA Champions League",          True),
        (2,  3,  "UEFA Europa League",             True),
        (4,  4,  "UEFA Conference League",         True),
        (9,  9,  "Relégation Playoff",             False),
        (10, 10, "Relégation",                     False),
    ],
    "Romania_Liga_I": [
        (1,  2,  "UEFA Conference League",         True),
        (14, 14, "Relégation Playoff",             False),
        (15, 16, "Relégation",                     False),
    ],
    "Russia_Premier_League": [
        (1,  6,  "Playoff Champions",              True),
        (13, 14, "Relégation Playoff",             False),
        (15, 16, "Relégation",                     False),
    ],
    "Sweden_Allsvenskan": [
        (1,  1,  "UEFA Conference League",         True),
        (14, 14, "Relégation Playoff",             False),
        (15, 16, "Relégation",                     False),
    ],
    "Saudi_Arabia_Pro_League": [
        (1,  4,  "AFC Champions League",           True),
        (14, 14, "Relégation Playoff",             False),
        (15, 16, "Relégation",                     False),
    ],
    "Brazil_Serie_A": [
        (1,  4,  "CONMEBOL Libertadores (Groupes)", True),
        (5,  6,  "CONMEBOL Libertadores Playoff",   True),
        (7,  12, "CONMEBOL Sudamericana",            True),
        (17, 20, "Relégation Serie B",              False),
    ],
    "Brazil_Serie_B": [
        (1,  4,  "Promotion Serie A",              True),
        (17, 20, "Relégation Serie C",             False),
    ],
    "Colombia_Primera_A": [
        (1,  8,  "Playoffs Título",                True),
        (1,  3,  "CONMEBOL Libertadores",          True),
        (4,  8,  "CONMEBOL Sudamericana",          True),
    ],
    "Chile_Primera_Division": [
        (1,  3,  "CONMEBOL Libertadores",          True),
        (4,  8,  "CONMEBOL Sudamericana",          True),
        (14, 14, "Relégation Playoff",             False),
        (15, 16, "Relégation",                     False),
    ],
    "Peru_Primera_Division": [
        (1,  2,  "CONMEBOL Libertadores",          True),
        (3,  4,  "CONMEBOL Sudamericana",          True),
        (17, 18, "Relégation",                     False),
    ],
    "Paraguay_Division_Profesional": [
        (1,  2,  "CONMEBOL Libertadores",          True),
        (3,  4,  "CONMEBOL Sudamericana",          True),
    ],
    "Venezuela_Primera_Division": [
        (1,  2,  "CONMEBOL Libertadores",          True),
        (3,  4,  "CONMEBOL Sudamericana",          True),
    ],
    "USA_Major_League_Soccer": [
        (1,  7,  "MLS Cup Playoffs",               True),
        (8,  9,  "Playoffs wild-card",             True),
    ],
    "Japan_J1_League": [
        (1,  2,  "AFC Champions League (Elite)",   True),
        (3,  3,  "AFC Champions League Playoff",   True),
        (17, 17, "Relégation Playoff",             False),
        (18, 20, "Relégation J2",                  False),
    ],
    "China_Super_League": [
        (1,  2,  "AFC Champions League",           True),
        (3,  4,  "AFC Challenge League",           True),
        (14, 16, "Relégation",                     False),
    ],
    "England_National_League": [
        (1,  1,  "Promotion EFL League Two",       True),
        (2,  7,  "Promotion Playoff",              True),
        (22, 24, "Relégation",                     False),
    ],
    "UEFA_Champions_League": [
        (1,  8,  "Huitièmes de finale",            True),
        (9,  16, "Huitièmes Playoff",              True),
        (17, 24, "Repêchage Europa League",        True),
        (25, 36, "Élimination",                    False),
    ],
}

BASE_DIR = "data/football/standings"
os.makedirs(BASE_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(BASE_DIR, "Standings.json")


def get_position_zone(league_name: str, position: int) -> dict | None:
    zones = LEAGUE_ZONES.get(league_name, [])
    for pos_min, pos_max, label, is_advantage in zones:
        if pos_min <= position <= pos_max:
            return {
                "label": label,
                "type": "avantage" if is_advantage else "désavantage"
            }
    return None


def setup_driver():
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
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    chrome_options.add_argument(f"user-agent={user_agent}")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def _is_subheader_row(row) -> bool:
    classes = row.get_attribute("class") or ""
    return "subgroup-headers" in classes or "Table__sub-header" in classes


def fetch_standings_from_url(url: str) -> list:
    driver = setup_driver()
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.Table--fixed-left")))
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".Table__Scroller table")))

        left_rows  = driver.find_elements(By.CSS_SELECTOR, "table.Table--fixed-left tbody tr")
        right_rows = driver.find_elements(By.CSS_SELECTOR, ".Table__Scroller table tbody tr")

        standings = []
        for i in range(min(len(left_rows), len(right_rows))):
            left_row = left_rows[i]
            stat_row = right_rows[i]

            pos_elem = left_row.find_element(By.CSS_SELECTOR, "span.team-position")
            position = int(pos_elem.text.strip())

            name_elem = left_row.find_element(By.CSS_SELECTOR, ".hide-mobile a")
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
                    "GP": int(gp), "W": int(w),  "D": int(d),
                    "L":  int(l),  "F": int(f),  "A": int(a),
                    "GD": int(gd), "P": int(p)
                }
            })
        return standings

    except Exception as e:
        print(f"  Erreur Selenium ({url}) : {e}")
        slug = url.split("/league/")[-1].replace("/", "_")
        with open(f"debug_{slug}.html", "w", encoding="utf-8") as fh:
            fh.write(driver.page_source)
        return []
    finally:
        driver.quit()


def fetch_subgroup_standings(url: str) -> list:
    driver = setup_driver()
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.Table--fixed-left")))
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".Table__Scroller table")))

        left_rows  = driver.find_elements(By.CSS_SELECTOR, "table.Table--fixed-left tbody tr")
        right_rows = driver.find_elements(By.CSS_SELECTOR, ".Table__Scroller table tbody tr")

        standings    = []
        global_pos   = 0
        right_cursor = 0

        for left_row in left_rows:
            if _is_subheader_row(left_row):
                if right_cursor < len(right_rows) and _is_subheader_row(right_rows[right_cursor]):
                    right_cursor += 1
                continue

            try:
                name_elem = left_row.find_element(By.CSS_SELECTOR, ".hide-mobile a")
                name = name_elem.text.strip()
            except Exception:
                right_cursor += 1
                continue

            while right_cursor < len(right_rows) and _is_subheader_row(right_rows[right_cursor]):
                right_cursor += 1

            if right_cursor >= len(right_rows):
                break

            stat_cells = right_rows[right_cursor].find_elements(
                By.CSS_SELECTOR, "td span.stat-cell"
            )
            right_cursor += 1

            if len(stat_cells) < 8:
                continue

            values = [cell.text.strip() for cell in stat_cells[:8]]
            gp, w, d, l, f, a, gd, p = values
            if gd.startswith('+'):
                gd = gd[1:]

            global_pos += 1
            standings.append({
                "position": global_pos,
                "name": name,
                "stats": {
                    "GP": int(gp), "W": int(w),  "D": int(d),
                    "L":  int(l),  "F": int(f),  "A": int(a),
                    "GD": int(gd), "P": int(p)
                }
            })

        return standings

    except Exception as e:
        print(f"  Erreur Selenium subgroups ({url}) : {e}")
        slug = url.split("/league/")[-1].replace("/", "_")
        with open(f"debug_{slug}_subgroups.html", "w", encoding="utf-8") as fh:
            fh.write(driver.page_source)
        return []
    finally:
        driver.quit()


def fetch_standings_with_selenium(league_name: str, league_id: str, season: int) -> list:
    """Scrape le classement d'une ligue simple (une seule phase) pour une saison donnée."""
    url = f"https://www.espn.com/soccer/standings/_/league/{league_id}/season/{season}"
    if league_name in SUBGROUP_LEAGUES:
        return fetch_subgroup_standings(url)
    return fetch_standings_from_url(url)


def load_existing_data() -> dict:
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Impossible de lire l'ancien fichier : {e}")
    return {}


def build_zones_meta(league_name: str) -> list:
    return [
        {
            "positions": f"{pmin}-{pmax}" if pmin != pmax else str(pmin),
            "label": label,
            "type": "avantage" if adv else "désavantage"
        }
        for pmin, pmax, label, adv in LEAGUE_ZONES.get(league_name, [])
    ]


def enrich_standings_with_zones(league_name: str, standings: list) -> list:
    enriched = []
    for team in standings:
        zone = get_position_zone(league_name, team["position"])
        entry = dict(team)
        entry["zone"] = zone
        enriched.append(entry)
    return enriched


def _season_entry_has_standings(entry: dict, is_multi_phase: bool) -> bool:
    """Vérifie si une entrée de saison (simple ou multi-phases) contient un classement non vide."""
    if not entry:
        return False
    if is_multi_phase:
        for key, value in entry.items():
            if isinstance(value, dict) and value.get("standings"):
                return True
        return False
    return bool(entry.get("standings"))


def scrape_single_phase_season(league_name: str, league_id: str, season: int) -> dict:
    standings = fetch_standings_with_selenium(league_name, league_id, season)
    num_teams = len(standings)

    if num_teams == 0:
        return {
            "saison": season,
            "total_journees": 0,
            "position_zones": build_zones_meta(league_name),
            "standings": []
        }

    total_journees = num_teams * 2 - 2

    return {
        "saison": season,
        "total_journees": total_journees,
        "position_zones": build_zones_meta(league_name),
        "standings": enrich_standings_with_zones(league_name, standings)
    }


def scrape_multi_phase_season(league_name: str, phase_config: dict, season: int) -> dict:
    """Scrape une ligue à deux phases pour une saison donnée. Chaque phase reçoit
    un indicateur "partie" (1 ou 2) pour savoir si c'est la 1ère ou la 2ème partie
    du classement."""
    result = {}
    phase1_label = phase_config["phase1_label"]
    phase2_label = phase_config["phase2_label"]
    phase2_zone_key = f"{league_name}_{phase2_label.capitalize()}" \
        if league_name == "Mexico_Liga_MX" \
        else f"{league_name}_Playoffs"

    print(f"  📋 Phase 1 ({phase1_label}) - saison {season}...")
    url_phase1 = f"{phase_config['regular']}/season/{season}"
    phase1_standings = fetch_standings_from_url(url_phase1)
    time.sleep(2)

    result[phase1_label] = {
        "partie": 1,
        "saison": season,
        "total_journees": phase_config["regular_journees"],
        "position_zones": build_zones_meta(league_name),
        "standings": enrich_standings_with_zones(league_name, phase1_standings) if phase1_standings else []
    }
    if phase1_standings:
        print(f"  ✔ {phase1_label} : {len(phase1_standings)} équipes")

    print(f"  🏆 Phase 2 ({phase2_label}) - saison {season}...")
    url_phase2 = f"{phase_config['playoffs']}/season/{season}"
    if phase_config["phase2_is_subgroup"]:
        phase2_standings = fetch_subgroup_standings(url_phase2)
    else:
        phase2_standings = fetch_standings_from_url(url_phase2)
    time.sleep(2)

    result[phase2_label] = {
        "partie": 2,
        "saison": season,
        "total_journees": phase_config["playoff_max_journees"],
        "position_zones": build_zones_meta(phase2_zone_key),
        "standings": enrich_standings_with_zones(phase2_zone_key, phase2_standings) if phase2_standings else []
    }
    if phase2_standings:
        print(f"  ✔ {phase2_label} : {len(phase2_standings)} équipes")

    return result


def scrape_season_entry(league_name, league_id, season, is_multi_phase, phase_config) -> dict:
    if is_multi_phase:
        return scrape_multi_phase_season(league_name, phase_config, season)
    return scrape_single_phase_season(league_name, league_id, season)


def determine_active_season(
    league_name: str,
    league_id: str,
    is_multi_phase: bool,
    phase_config: dict | None,
    existing_league_data: dict
) -> tuple[int, dict]:
    """
    Détermine quelle saison est actuellement "active" pour cette ligue et scrape
    cette saison à chaque run (toujours en direct, jamais figée sur du cache) :

    1) On tente CURRENT_YEAR (ex: 2026). Si ça renvoie des données -> c'est la
       saison active.
    2) Si CURRENT_YEAR est vide (ex: la saison ESPN 2025-2026 est encore
       référencée comme "2025"), on retombe sur CURRENT_YEAR - 1 (ex: 2025)
       et on la RE-SCRAPE à ce run (pas de simple lecture du cache), pour que
       le classement 2025 continue d'être mis à jour tant que 2026 n'a pas
       démarré côté ESPN.
    3) Si même CURRENT_YEAR - 1 échoue au scraping, on garde en dernier recours
       le cache existant de CURRENT_YEAR - 1 s'il existe.
    """
    print(f"  🔎 Tentative saison active {CURRENT_YEAR}...")
    entry_current = scrape_season_entry(league_name, league_id, CURRENT_YEAR, is_multi_phase, phase_config)

    if _season_entry_has_standings(entry_current, is_multi_phase):
        return CURRENT_YEAR, entry_current

    print(f"  ⚠️  Saison {CURRENT_YEAR} vide côté ESPN — la saison active est probablement {CURRENT_YEAR - 1}.")
    fallback_season = CURRENT_YEAR - 1
    time.sleep(2)
    print(f"  🔁 Re-scraping de la saison {fallback_season} (mise à jour à chaque run)...")
    entry_fallback = scrape_season_entry(league_name, league_id, fallback_season, is_multi_phase, phase_config)

    if _season_entry_has_standings(entry_fallback, is_multi_phase):
        return fallback_season, entry_fallback

    existing_fallback = existing_league_data.get(str(fallback_season))
    if _season_entry_has_standings(existing_fallback, is_multi_phase):
        print(f"  ⚠️  Nouveau scraping {fallback_season} vide aussi — conservation du dernier cache disponible.")
        return fallback_season, existing_fallback

    print(f"  ❌ Aucune donnée disponible ni pour {CURRENT_YEAR} ni pour {fallback_season}.")
    return CURRENT_YEAR, entry_current


def scrape_all_leagues():
    existing_data = load_existing_data()
    all_data = {}

    for league_name, league_id in LEAGUES.items():
        try:
            print(f"🔹 Scraping {league_name}...")
            existing_league_data = existing_data.get(league_name, {})
            is_multi_phase = league_name in MULTI_PHASE_LEAGUES
            phase_config = MULTI_PHASE_LEAGUES.get(league_name)

            # ── Saison active : toujours scrapée en direct à chaque run ────────
            active_season, active_entry = determine_active_season(
                league_name, league_id, is_multi_phase, phase_config, existing_league_data
            )

            league_result = {str(active_season): active_entry}

            # ── Saisons historiques : de START_SEASON jusqu'à active_season - 1 ─
            # Une fois qu'elles ont des données en cache, elles ne sont plus
            # re-scrapées (contrairement à la saison active).
            for season in get_historical_seasons(active_season):
                season_key = str(season)
                existing_entry = existing_league_data.get(season_key)

                if _season_entry_has_standings(existing_entry, is_multi_phase):
                    print(f"  ⏭️  Saison {season} déjà en cache, non re-scrapée.")
                    league_result[season_key] = existing_entry
                    continue

                print(f" 📅 Saison historique manquante {season}, scraping...")
                fresh_entry = scrape_season_entry(league_name, league_id, season, is_multi_phase, phase_config)
                time.sleep(2)
                league_result[season_key] = fresh_entry if _season_entry_has_standings(fresh_entry, is_multi_phase) else (existing_entry or fresh_entry)

            all_data[league_name] = league_result
            print(f"✔ {league_name} terminé — saison active : {active_season}\n")

        except Exception as e:
            print(f"❌ Erreur pour {league_name}: {e}")
            if league_name in existing_data:
                print(f"⚠️  Exception — conservation des données précédentes pour {league_name}")
                all_data[league_name] = existing_data[league_name]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)
    print(f"\n✅ Tous les classements enregistrés dans {OUTPUT_FILE}")


if __name__ == "__main__":
    scrape_all_leagues()