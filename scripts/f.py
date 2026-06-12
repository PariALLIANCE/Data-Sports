import json
import time
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

MATCH_URLS = [
    "https://www.espn.com/soccer/match/_/gameId/401873943/avai-ceara",
]

OUTPUT_FILE = "match_details.json"

# ─────────────────────────────────────────────
# DRIVER
# ─────────────────────────────────────────────

def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")
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

# ─────────────────────────────────────────────
# IDs ÉQUIPES DEPUIS LE GAMESTRIP
# href="/soccer/team/_/id/9969/ceara" → team_id
# home = 1er lien, away = 2ème lien
# ─────────────────────────────────────────────

def extract_team_ids_gamestrip(driver):
    """Retourne (home_id, away_id) depuis les liens du Gamestrip__Container."""
    ids = []
    try:
        container = driver.find_element(By.CSS_SELECTOR, "div.Gamestrip__Container")
        links = container.find_elements(
            By.CSS_SELECTOR, "a[data-clubhouse-uid][href*='/soccer/team/_/id/']"
        )
        seen = []
        for a in links:
            href = a.get_attribute("href") or ""
            m = re.search(r"/soccer/team/_/id/(\d+)/", href)
            if not m:
                continue
            tid = m.group(1)
            if tid not in seen:
                seen.append(tid)
        ids = seen
    except Exception as e:
        print(f"    ⚠️  Erreur IDs gamestrip : {e}")

    home_id = ids[0] if len(ids) > 0 else None
    away_id = ids[1] if len(ids) > 1 else None
    return home_id, away_id

# ─────────────────────────────────────────────
# NOMS DEPUIS LE CLASSEMENT
# Toutes les équipes (featured + non featured)
# a.AnchorLink[href*='/soccer/team/_/id/']
#   span.Standings__TeamName → nom affiché
#   data-clubhouse-uid="s:600~t:9969" → team_id
# ─────────────────────────────────────────────

def build_standings_name_map(driver):
    """
    Retourne un dict {team_id: name} pour toutes les équipes
    présentes dans le tableau de classement.
    """
    name_map = {}
    try:
        links = driver.find_elements(
            By.CSS_SELECTOR,
            "a.AnchorLink[data-clubhouse-uid][href*='/soccer/team/_/id/']"
        )
        for a in links:
            uid = a.get_attribute("data-clubhouse-uid") or ""
            m   = re.search(r"t:(\d+)", uid)
            if not m:
                continue
            team_id = m.group(1)
            try:
                name = a.find_element(
                    By.CSS_SELECTOR, "span.Standings__TeamName"
                ).text.strip()
            except NoSuchElementException:
                continue
            if name:
                name_map[team_id] = name
    except Exception as e:
        print(f"    ⚠️  Erreur standings name map : {e}")
    return name_map

# ─────────────────────────────────────────────
# SCORE ET STATUT
# div.uCTxv  → score home (1er) / away (2ème)
# span.zRALO → statut FT / HT / XX'
# ─────────────────────────────────────────────

def extract_score(driver):
    home_score = away_score = status = None
    try:
        score_els = driver.find_elements(By.CSS_SELECTOR, "div.uCTxv")
        scores = [el.text.strip() for el in score_els if re.match(r"^\d+$", el.text.strip())]
        if len(scores) >= 2:
            home_score, away_score = scores[0], scores[1]
        elif len(scores) == 1:
            home_score = scores[0]
    except Exception as e:
        print(f"    ⚠️  Erreur score : {e}")
    try:
        st_els   = driver.find_elements(By.CSS_SELECTOR, "span.zRALO")
        statuses = [el.text.strip() for el in st_els if el.text.strip()]
        if statuses:
            status = statuses[0]
    except Exception:
        pass
    return home_score, away_score, status

# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────

def extract_stats(driver):
    stats = {}
    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "section[data-testid='prism-LayoutCard']")
            )
        )
        rows = driver.find_elements(By.CSS_SELECTOR, "div.LOSQp")
        for row in rows:
            try:
                name = row.find_element(By.CSS_SELECTOR, "span.OkRBU").text.strip()
                vals = row.find_elements(By.CSS_SELECTOR, "span.bLeWt")
                if name and len(vals) >= 2:
                    stats[name] = {
                        "home": vals[0].text.strip(),
                        "away": vals[1].text.strip()
                    }
            except NoSuchElementException:
                continue
    except TimeoutException:
        pass
    except Exception as e:
        print(f"    ⚠️  Erreur stats : {e}")
    return stats

# ─────────────────────────────────────────────
# SCRAPING D'UN MATCH
# ─────────────────────────────────────────────

def scrape_match(driver, url):
    m = re.search(r"gameId/(\d+)", url)
    game_id = m.group(1) if m else url

    print(f"\n🔍 gameId={game_id}")

    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.Gamestrip__Container"))
        )
    except TimeoutException:
        print(f"  ⚠️  Timeout")
        return None
    except WebDriverException as e:
        print(f"  ⚠️  WebDriver : {e}")
        return None

    time.sleep(1.5)

    # IDs depuis le gamestrip
    home_id, away_id = extract_team_ids_gamestrip(driver)

    # Noms depuis le classement, croisés par ID
    name_map  = build_standings_name_map(driver)
    home_name = name_map.get(home_id) if home_id else None
    away_name = name_map.get(away_id) if away_id else None

    home_score, away_score, status = extract_score(driver)
    stats = extract_stats(driver)

    result = {
        "gameId":       game_id,
        "url":          url,
        "team_home":    home_name,
        "team_home_id": home_id,
        "team_away":    away_name,
        "team_away_id": away_id,
        "home_score":   home_score,
        "away_score":   away_score,
        "status":       status,
        "stats":        stats,
    }

    print(f"  ✅ {home_name} (id={home_id}) {home_score} - {away_score} {away_name} (id={away_id})  [{status}]")
    print(f"  📊 {len(stats)} stats")
    return result

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

driver  = create_driver()
results = []

try:
    for url in MATCH_URLS:
        data = scrape_match(driver, url)
        if data:
            results.append(data)
        time.sleep(1)
finally:
    driver.quit()
    print("\n✅ Driver fermé.")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n💾 {len(results)} match(s) → {OUTPUT_FILE}")