import json
from datetime import datetime, timedelta, timezone
import re
import time
import os
import copy

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

OUTPUT_DIR = "data/football/leagues"
os.makedirs(OUTPUT_DIR, exist_ok=True)

LEAGUES = {
  "Austria_Bundesliga":            {"id": "aut.1",              "json": "Austria_Bundesliga.json"},
  "Belgium_Jupiler_Pro_League":    {"id": "bel.1",              "json": "Belgium_Jupiler_Pro_League.json"},
  "Brazil_Serie_A":                {"id": "bra.1",              "json": "Brazil_Serie_A.json"},
  "Brazil_Serie_B":                {"id": "bra.2",              "json": "Brazil_Serie_B.json"},
  "Chile_Primera_Division":        {"id": "chi.1",              "json": "Chile_Primera_Division.json"},
  "China_Super_League":            {"id": "chn.1",              "json": "China_Super_League.json"},
  "Colombia_Primera_A":            {"id": "col.1",              "json": "Colombia_Primera_A.json"},
  "England_National_League":       {"id": "eng.5",              "json": "England_National_League.json"},
  "England_Premier_League":        {"id": "eng.1",              "json": "England_Premier_League.json"},
  "FIFA_Club_World_Cup":           {"id": "fifa.cwc",           "json": "FIFA_Club_World_Cup.json"},
  "France_Ligue_1":                {"id": "fra.1",              "json": "France_Ligue_1.json"},
  "Germany_Bundesliga":            {"id": "ger.1",              "json": "Germany_Bundesliga.json"},
  "Greece_Super_League_1":         {"id": "gre.1",              "json": "Greece_Super_League_1.json"},
  "Italy_Serie_A":                 {"id": "ita.1",              "json": "Italy_Serie_A.json"},
  "Japan_J1_League":               {"id": "jpn.1",              "json": "Japan_J1_League.json"},
  "Mexico_Liga_MX":                {"id": "mex.1",              "json": "Mexico_Liga_MX.json"},
  "Netherlands_Eredivisie":        {"id": "ned.1",              "json": "Netherlands_Eredivisie.json"},
  "Paraguay_Division_Profesional": {"id": "par.1",              "json": "Paraguay_Division_Profesional.json"},
  "Peru_Primera_Division":         {"id": "per.1",              "json": "Peru_Primera_Division.json"},
  "Portugal_Primeira_Liga":        {"id": "por.1",              "json": "Portugal_Primeira_Liga.json"},
  "Romania_Liga_I":                {"id": "rou.1",              "json": "Romania_Liga_I.json"},
  "Russia_Premier_League":         {"id": "rus.1",              "json": "Russia_Premier_League.json"},
  "Saudi_Arabia_Pro_League":       {"id": "ksa.1",              "json": "Saudi_Arabia_Pro_League.json"},
  "Spain_Laliga":                  {"id": "esp.1",              "json": "Spain_Laliga.json"},
  "Sweden_Allsvenskan":            {"id": "swe.1",              "json": "Sweden_Allsvenskan.json"},
  "Switzerland_Super_League":      {"id": "sui.1",              "json": "Switzerland_Super_League.json"},
  "Turkey_Super_Lig":              {"id": "tur.1",              "json": "Turkey_Super_Lig.json"},
  "UEFA_Champions_League":         {"id": "uefa.champions",     "json": "UEFA_Champions_League.json"},
  "UEFA_Europa_League":            {"id": "uefa.europa",        "json": "UEFA_Europa_League.json"},
  "USA_Major_League_Soccer":       {"id": "usa.1",              "json": "USA_Major_League_Soccer.json"},
  "Venezuela_Primera_Division":    {"id": "ven.1",              "json": "Venezuela_Primera_Division.json"},
  "FA_Cup":           {"id": "eng.fa",              "json": "FA_Cup.json"},
  "EFL_Cup":          {"id": "eng.league_cup",      "json": "EFL_Cup.json"},
  "Copa_del_Rey":     {"id": "esp.copa_del_rey",    "json": "Copa_del_Rey.json"},
  "DFB_Pokal":        {"id": "ger.dfb_pokal",       "json": "DFB_Pokal.json"},
  "Coppa_Italia":     {"id": "ita.coppa_italia",    "json": "Coppa_Italia.json"},
  "Coupe_de_France":  {"id": "fra.coupe_de_france", "json": "Coupe_de_France.json"},
  "KNVB_Cup":         {"id": "ned.cup",             "json": "KNVB_Cup.json"},
  "Taca_de_Portugal": {"id": "por.taca.portugal",   "json": "Taca_de_Portugal.json"},
  "Kings_Cup_Saudi":  {"id": "ksa.kings.cup",       "json": "Kings_Cup_Saudi.json"},
}

# ─────────────────────────────────────────────
# DATES : J-1 ET J-2 UNIQUEMENT
# ─────────────────────────────────────────────

now = datetime.now(timezone.utc)
target_dates = {
    (now - timedelta(days=i)).strftime("%Y%m%d")
    for i in range(1, 3)
}
dates_to_fetch = sorted(target_dates)

# ─────────────────────────────────────────────
# PARSING DATES
# ─────────────────────────────────────────────

DATE_FORMATS = [
    "%A, %B %d, %Y",
    "%A, %d %B %Y",
    "%Y-%m-%d",
    "%Y%m%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
]

def parse_date_formats(date_str):
    for fmt in ("%A, %B %d, %Y", "%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y%m%d")
        except Exception:
            continue
    return None

def is_target_date(date_str):
    normalized = parse_date_formats(date_str)
    return normalized in target_dates

# ─────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────

def load_existing_matches(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {m["gameId"]: m for m in data if "gameId" in m}
    except Exception:
        return {}

# ─────────────────────────────────────────────
# DRIVER SELENIUM
# ─────────────────────────────────────────────

def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=fr-FR")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver

def safe_get(driver, url, wait_selector=None, timeout=15):
    try:
        driver.get(url)
        if wait_selector:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
            )
        else:
            time.sleep(2)
        return True
    except TimeoutException:
        return True
    except WebDriverException as e:
        print(f"    ⚠️  WebDriver erreur : {e}")
        return False

# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────

def get_match_stats(driver, game_id):
    url = f"https://www.espn.com/soccer/match/_/gameId/{game_id}"
    if not safe_get(driver, url, wait_selector="section[data-testid='prism-LayoutCard']", timeout=12):
        return {}
    try:
        stats_section = driver.find_element(By.CSS_SELECTOR, "section[data-testid='prism-LayoutCard']")
        rows  = stats_section.find_elements(By.CSS_SELECTOR, "div.LOSQp")
        stats = {}
        for row in rows:
            try:
                name_tag = row.find_element(By.CSS_SELECTOR, "span.OkRBU")
                values   = row.find_elements(By.CSS_SELECTOR, "span.bLeWt")
                if name_tag and len(values) >= 2:
                    stats[name_tag.text.strip()] = {
                        "home": values[0].text.strip(),
                        "away": values[1].text.strip()
                    }
            except NoSuchElementException:
                continue
        time.sleep(0.6)
        return stats
    except NoSuchElementException:
        return {}
    except Exception as e:
        print(f"    ⚠️  Erreur stats ({game_id}) : {e}")
        return {}

# ─────────────────────────────────────────────
# COTES ESPN
# ─────────────────────────────────────────────

def us_to_decimal(odds_str):
    if not odds_str:
        return None
    try:
        val = int(odds_str.replace("+", "").strip())
        return round(1 + (val / 100), 2) if val > 0 else round(1 + (100 / abs(val)), 2)
    except Exception:
        return None

def is_valid_us_odds(val):
    if not val:
        return False
    try:
        int(val.replace("+", "").replace("-", ""))
        return True
    except Exception:
        return False

def extract_odds(driver, game_id):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-testid='OddsCell']"))
        )
        cells = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='OddsCell']")
        if len(cells) < 7:
            return None

        home_us = cells[0].text.strip() or None
        away_us = cells[3].text.strip() or None
        draw_us = cells[6].text.strip() or None

        if not all(is_valid_us_odds(v) for v in [home_us, away_us, draw_us]):
            return None

        return {
            "home": us_to_decimal(home_us),
            "away": us_to_decimal(away_us),
            "draw": us_to_decimal(draw_us),
        }
    except TimeoutException:
        return None
    except Exception as e:
        print(f"    ⚠️  Erreur cotes ({game_id}) : {e}")
        return None

# ─────────────────────────────────────────────
# SCRAPING SCHEDULE
# ─────────────────────────────────────────────

def scrape_schedule(driver, league_id, date_str):
    url = f"https://www.espn.com/soccer/schedule/_/date/{date_str}/league/{league_id}"
    if not safe_get(driver, url, wait_selector="div.ResponsiveTable", timeout=15):
        return []

    results = []
    try:
        tables = driver.find_elements(By.CSS_SELECTOR, "div.ResponsiveTable")
        for table in tables:
            try:
                date_title = table.find_element(By.CSS_SELECTOR, "div.Table__Title")
                date_text  = date_title.text.strip()
            except NoSuchElementException:
                date_text = date_str

            rows = table.find_elements(By.CSS_SELECTOR, "tbody > tr.Table__TR")
            for row in rows:
                try:
                    teams     = row.find_elements(By.CSS_SELECTOR, "span.Table__Team a.AnchorLink:last-child")
                    score_tag = row.find_element(By.CSS_SELECTOR, "a.AnchorLink.at")
                except NoSuchElementException:
                    continue

                if len(teams) != 2:
                    continue

                score = score_tag.text.strip()
                if score.lower() == "v":
                    continue

                match_href = score_tag.get_attribute("href") or ""
                match_id   = re.search(r"gameId/(\d+)", match_href)
                if not match_id:
                    continue

                game_id   = match_id.group(1)
                match_url = (
                    match_href if match_href.startswith("http")
                    else "https://www.espn.com" + match_href
                )

                results.append({
                    "gameId":    game_id,
                    "date_text": date_text,
                    "team1":     teams[0].text.strip(),
                    "team2":     teams[1].text.strip(),
                    "score":     score,
                    "match_url": match_url,
                })
    except Exception as e:
        print(f"    ⚠️  Erreur parsing schedule : {e}")

    return results

# ─────────────────────────────────────────────
# BOUCLE PRINCIPALE
# ─────────────────────────────────────────────

print(f"📆 Dates ciblées : {sorted(target_dates)}")

driver = create_driver()

try:
    for league_name, league in LEAGUES.items():
        print(f"\n🏆 {league_name}")

        json_path = os.path.join(OUTPUT_DIR, league["json"])
        matches   = load_existing_matches(json_path)

        removed = [
            gid for gid, m in matches.items()
            if is_target_date(m.get("date", "")) and not m.get("odds")
        ]
        for gid in removed:
            del matches[gid]
        if removed:
            print(f"  🗑️  {len(removed)} match(s) sans cotes supprimé(s) et re-scrapés")

        new_count     = 0
        stats_updated = 0

        for date_str in dates_to_fetch:
            print(f"  📅 {date_str}")

            day_matches = scrape_schedule(driver, league["id"], date_str)

            for item in day_matches:
                game_id = item["gameId"]

                if game_id in matches:
                    if not matches[game_id].get("stats"):
                        stats = get_match_stats(driver, game_id)
                        if stats:
                            matches[game_id]["stats"] = stats
                            stats_updated += 1
                    continue

                stats = get_match_stats(driver, game_id)
                odds  = extract_odds(driver, game_id)
                time.sleep(1)

                match_data = {
                    "gameId":    game_id,
                    "date":      item["date_text"],
                    "team1":     item["team1"],
                    "team2":     item["team2"],
                    "score":     item["score"],
                    "title":     f"{item['team1']} VS {item['team2']}",
                    "match_url": item["match_url"],
                    "stats":     stats,
                }
                if odds:
                    match_data["odds"] = odds

                matches[game_id] = match_data
                new_count += 1

                status = f"{odds['home']} / {odds['draw']} / {odds['away']}" if odds else "pas de cotes"
                print(f"    ✅ {item['team1']} vs {item['team2']} → {status}")

        tmp_path = json_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(list(matches.values()), f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, json_path)

        print(f"  💾 {league_name} : {len(matches)} matchs | +{new_count} nouveaux | stats MAJ {stats_updated}")

finally:
    driver.quit()
    print("\n✅ Driver fermé proprement.")