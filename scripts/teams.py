import os
import json
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -------------------- CONFIG --------------------
FOOTBALL_BASE_URL = "https://www.espn.com/soccer/teams/_/league/"
FOOTBALL_LOGO_URL = "https://a.espncdn.com/i/teamlogos/soccer/500/{team_id}.png"
FOOTBALL_OUTPUT_DIR = "data/football/teams"
FOOTBALL_OUTPUT_FILE = "football_teams.json"

FOOTBALL_LEAGUES = {
  "England_Premier_League":        {"id": "eng.1",  "country": "England"},
  "England_Championship":          {"id": "eng.2",  "country": "England"},
  "England_League_One":            {"id": "eng.3",  "country": "England"},
  "England_League_Two":            {"id": "eng.4",  "country": "England"},
  "England_National_League":       {"id": "eng.5",  "country": "England"},
  "Spain_Laliga":                  {"id": "esp.1",  "country": "Spain"},
  "Spain_Laliga2":                 {"id": "esp.2",  "country": "Spain"},
  "Germany_Bundesliga":            {"id": "ger.1",  "country": "Germany"},
  "Germany_2_Bundesliga":          {"id": "ger.2",  "country": "Germany"},
  "Austria_Bundesliga":            {"id": "aut.1",  "country": "Austria"},
  "Belgium_Jupiler_Pro_League":    {"id": "bel.1",  "country": "Belgium"},
  "Brazil_Serie_A":                {"id": "bra.1",  "country": "Brazil"},
  "Brazil_Serie_B":                {"id": "bra.2",  "country": "Brazil"},
  "Chile_Primera_Division":        {"id": "chi.1",  "country": "Chile"},
  "China_Super_League":            {"id": "chn.1",  "country": "China"},
  "Colombia_Primera_A":            {"id": "col.1",  "country": "Colombia"},
  "France_Ligue_1":                {"id": "fra.1",  "country": "France"},
  "France_Ligue_2":                {"id": "fra.2",  "country": "France"},
  "Greece_Super_League_1":         {"id": "gre.1",  "country": "Greece"},
  "Italy_Serie_A":                 {"id": "ita.1",  "country": "Italy"},
  "Italy_Serie_B":                 {"id": "ita.2",  "country": "Italy"},
  "Japan_J1_League":               {"id": "jpn.1",  "country": "Japan"},
  "Mexico_Liga_MX":                {"id": "mex.1",  "country": "Mexico"},
  "Netherlands_Eredivisie":        {"id": "ned.1",  "country": "Netherlands"},
  "Paraguay_Division_Profesional": {"id": "par.1",  "country": "Paraguay"},
  "Peru_Primera_Division":         {"id": "per.1",  "country": "Peru"},
  "Portugal_Primeira_Liga":        {"id": "por.1",  "country": "Portugal"},
  "Romania_Liga_I":                {"id": "rou.1",  "country": "Romania"},
  "Russia_Premier_League":         {"id": "rus.1",  "country": "Russia"},
  "Saudi_Arabia_Pro_League":       {"id": "ksa.1",  "country": "Saudi_Arabia"},
  "Scotland_Premiership":          {"id": "sco.1",  "country": "Scotland"},
  "Scotland_Championship":         {"id": "sco.2",  "country": "Scotland"},
  "Sweden_Allsvenskan":            {"id": "swe.1",  "country": "Sweden"},
  "Switzerland_Super_League":      {"id": "sui.1",  "country": "Switzerland"},
  "Turkey_Super_Lig":              {"id": "tur.1",  "country": "Turkey"},
  "USA_Major_League_Soccer":       {"id": "usa.1",  "country": "USA"},
  "Venezuela_Primera_Division":    {"id": "ven.1",  "country": "Venezuela"},
  "Argentina_Liga_Profesional":    {"id": "arg.1",  "country": "Argentina"},
  "Argentina_Nacional_B":          {"id": "arg.2",  "country": "Argentina"},
  "Argentina_Primera_B":           {"id": "arg.3",  "country": "Argentina"},
}

NHL_URL = "https://www.espn.com/nhl/teams"
NHL_OUTPUT_FILE = "data/hockey/teams/hockey_NHL_teams.json"


# -------------------- DRIVER --------------------
def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    return driver


# -------------------- FONCTIONS --------------------
def get_football_teams_for_league(driver, league_id):
    url = FOOTBALL_BASE_URL + league_id
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "section.TeamLinks"))
        )
    except Exception:
        print(f"   ⚠️ Timeout ou aucune section trouvée pour {league_id}")
        return []

    time.sleep(2)

    teams = []
    sections = driver.find_elements(By.CSS_SELECTOR, "section.TeamLinks")

    for section in sections:
        try:
            name_tag = section.find_element(By.TAG_NAME, "h2")
            team_name = name_tag.text.strip()
        except Exception:
            continue

        try:
            links = section.find_elements(By.CSS_SELECTOR, "a[href*='/soccer/team/_/id/']")
            if not links:
                continue
            href = links[0].get_attribute("href")
            match = re.search(r"/id/(\d+)", href)
            if not match:
                continue
            team_id = match.group(1)
        except Exception:
            continue

        logo_url = FOOTBALL_LOGO_URL.format(team_id=team_id)
        teams.append({"team": team_name, "team_id": team_id, "logo": logo_url})

    return teams


def get_nhl_teams(driver):
    driver.get(NHL_URL)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "section.TeamLinks"))
        )
    except Exception:
        print("   ⚠️ Timeout ou aucune section NHL trouvée")
        return []

    time.sleep(2)

    teams = []
    sections = driver.find_elements(By.CSS_SELECTOR, "section.TeamLinks")

    for section in sections:
        try:
            name_tag = section.find_element(By.TAG_NAME, "h2")
            team_name = name_tag.text.strip()
        except Exception:
            continue

        try:
            link = section.find_element(By.TAG_NAME, "a")
            href = link.get_attribute("href")
            parts = href.strip("/").split("/")
            if "name" not in parts:
                continue
            team_id = parts[parts.index("name") + 1]
        except Exception:
            continue

        logo_url = f"https://a.espncdn.com/i/teamlogos/nhl/500/{team_id}.png"
        teams.append({"team": team_name, "team_id": team_id, "logo": logo_url})

    return teams


def merge_teams(existing_teams, new_teams):
    existing_by_id = {t["team_id"]: t for t in existing_teams}

    for team in new_teams:
        tid = team["team_id"]
        if tid not in existing_by_id:
            existing_by_id[tid] = team
            print(f"      ➕ Nouvelle équipe ajoutée : {team['team']} (ID {tid})")
        else:
            existing_by_id[tid]["team"] = team["team"]
            existing_by_id[tid]["logo"] = team["logo"]

    return list(existing_by_id.values())


def scrape_football_teams(driver):
    output_path = os.path.join(FOOTBALL_OUTPUT_DIR, FOOTBALL_OUTPUT_FILE)

    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        print(f"📂 Fichier existant chargé : {output_path}")
    else:
        existing_data = {}
        print("📂 Aucun fichier existant, création d'un nouveau.")

    for league_name, league_info in FOOTBALL_LEAGUES.items():
        league_id = league_info["id"]
        country = league_info["country"]
        print(f"🏆 [{country}] Scraping {league_name} ({league_id})")
        try:
            new_teams = get_football_teams_for_league(driver, league_id)
            existing_teams = existing_data.get(country, [])
            merged = merge_teams(existing_teams, new_teams)
            existing_data[country] = merged
            print(f"   → {len(new_teams)} scrapées | {len(merged)} total pour {country}")
        except Exception as e:
            print(f"❌ Erreur pour {league_name} : {e}")
            if country not in existing_data:
                existing_data[country] = []
        time.sleep(2)

    os.makedirs(FOOTBALL_OUTPUT_DIR, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Fichier football mis à jour : {output_path}")


def scrape_nhl_teams(driver):
    print("🏒 Scraping équipes NHL...")

    if os.path.exists(NHL_OUTPUT_FILE):
        with open(NHL_OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        existing_teams = existing_data.get("NHL", [])
        print(f"📂 Fichier NHL existant chargé.")
    else:
        existing_teams = []
        print("📂 Aucun fichier NHL existant, création d'un nouveau.")

    new_teams = get_nhl_teams(driver)
    merged = merge_teams(existing_teams, new_teams)

    os.makedirs(os.path.dirname(NHL_OUTPUT_FILE), exist_ok=True)
    with open(NHL_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"NHL": merged}, f, indent=2, ensure_ascii=False)
    print(f"✅ {len(merged)} équipes NHL sauvegardées dans {NHL_OUTPUT_FILE}")


# -------------------- MAIN --------------------
if __name__ == "__main__":
    driver = create_driver()
    try:
        print("=== DÉBUT DU SCRAPING FOOTBALL ===")
        scrape_football_teams(driver)
        print("\n=== DÉBUT DU SCRAPING NHL ===")
        scrape_nhl_teams(driver)
    finally:
        driver.quit()
        print("\n🔒 Driver fermé.")