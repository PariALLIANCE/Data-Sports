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

# ─────────────────────────────────────────────
# URLS À SCRAPER
# ─────────────────────────────────────────────

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
# ÉQUIPES DEPUIS LE GAMESTRIP
# Source : liens a[data-clubhouse-uid] dans le Gamestrip__Container
# href="/soccer/team/_/id/9969/ceara"  → team_id=9969
# span.NzyJW.NMnSM                     → nom long "Ceará"
# span.HUcap.mpjVY                     → sigle "CEA"
# ─────────────────────────────────────────────

def extract_teams_gamestrip(driver):
    """
    Retourne [home, away] chacun = {name, sigle, team_id}
    Les deux liens équipes dans le Gamestrip ont data-clubhouse-uid
    et href="/soccer/team/_/id/XXXX/slug".
    On les prend dans l'ordre DOM : home d'abord, away ensuite.
    """
    teams = []
    try:
        container = driver.find_element(By.CSS_SELECTOR, "div.Gamestrip__Container")
        links = container.find_elements(
            By.CSS_SELECTOR, "a[data-clubhouse-uid][href*='/soccer/team/_/id/']"
        )
        seen_ids = []
        for a in links:
            href = a.get_attribute("href") or ""
            uid  = a.get_attribute("data-clubhouse-uid") or ""

            # team_id depuis href
            m = re.search(r"/soccer/team/_/id/(\d+)/", href)
            if not m:
                continue
            team_id = m.group(1)
            if team_id in seen_ids:
                continue
            seen_ids.append(team_id)

            # nom long
            try:
                name = a.find_element(By.CSS_SELECTOR, "span.NMnSM").text.strip()
            except NoSuchElementException:
                name = ""

            # sigle
            try:
                sigle = a.find_element(By.CSS_SELECTOR, "span.HUcap").text.strip()
            except NoSuchElementException:
                sigle = ""

            # fallback nom = alt de l'image
            if not name:
                try:
                    name = a.find_element(By.CSS_SELECTOR, "img").get_attribute("alt") or ""
                except NoSuchElementException:
                    pass

            teams.append({"name": name, "sigle": sigle, "team_id": team_id})

    except NoSuchElementException:
        pass
    except Exception as e:
        print(f"    ⚠️  Erreur équipes gamestrip : {e}")

    home = teams[0] if len(teams) > 0 else {"name": None, "sigle": None, "team_id": None}
    away = teams[1] if len(teams) > 1 else {"name": None, "sigle": None, "team_id": None}
    return home, away

# ─────────────────────────────────────────────
# ÉQUIPES EN GRAS DANS LE CLASSEMENT
# a.AnchorLink.featuredTeam → équipes du match
# data-clubhouse-uid="s:600~t:9969" → team_id
# span.Standings__TeamName           → nom
# ─────────────────────────────────────────────

def extract_featured_standings(driver):
    """
    Retourne la liste des équipes marquées featuredTeam dans le tableau
    de classement, avec leur nom et team_id.
    """
    featured = []
    try:
        links = driver.find_elements(
            By.CSS_SELECTOR,
            "a.AnchorLink.featuredTeam[data-clubhouse-uid]"
        )
        for a in links:
            uid = a.get_attribute("data-clubhouse-uid") or ""
            m   = re.search(r"t:(\d+)", uid)
            team_id = m.group(1) if m else None

            try:
                name = a.find_element(By.CSS_SELECTOR, "span.Standings__TeamName").text.strip()
            except NoSuchElementException:
                name = ""

            if name or team_id:
                featured.append({"name": name, "team_id": team_id})

    except Exception as e:
        print(f"    ⚠️  Erreur featured standings : {e}")

    return featured

# ─────────────────────────────────────────────
# SCORE ET STATUT
# div.uCTxv   → chiffre du score (home=1er, away=2ème)
# span.zRALO  → statut "FT" / "HT" / "45'" etc.
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
# ÉVÉNEMENTS (buts, cartons)
# Chaque événement = div.VZTD.ZLXw.yvbRH.JLJBa.CLwPV.ucZkc
#   texte  : div.awXxV.rlVU.vXdaT
#   icône  : svg[data-icon]
#     "soccer-goal02" → but
#     "soccer-card03" → carton
#       fill="#FF3232" → rouge  /  sinon jaune
# ─────────────────────────────────────────────

def extract_events(driver):
    events = []
    try:
        blocks = driver.find_elements(
            By.CSS_SELECTOR,
            "div.VZTD.ZLXw.yvbRH.JLJBa.CLwPV.ucZkc"
        )
        for block in blocks:
            # texte de l'événement
            try:
                text = block.find_element(
                    By.CSS_SELECTOR, "div.awXxV.rlVU.vXdaT"
                ).text.strip()
            except NoSuchElementException:
                continue
            if not text:
                continue

            # type via l'icône SVG
            event_type = "unknown"
            try:
                svg       = block.find_element(By.CSS_SELECTOR, "svg[data-icon]")
                icon_name = svg.get_attribute("data-icon") or ""

                if "goal" in icon_name:
                    event_type = "goal"
                elif "card" in icon_name:
                    # couleur du path pour distinguer jaune/rouge
                    try:
                        fill = svg.find_element(By.TAG_NAME, "path").get_attribute("fill") or ""
                        if "FF3232" in fill.upper() or "red" in fill.lower():
                            event_type = "red_card"
                        else:
                            event_type = "yellow_card"
                    except NoSuchElementException:
                        event_type = "card"

            except NoSuchElementException:
                pass

            events.append({"type": event_type, "text": text})

    except Exception as e:
        print(f"    ⚠️  Erreur événements : {e}")

    return events

# ─────────────────────────────────────────────
# STATS DU MATCH
# section[data-testid='prism-LayoutCard']
#   div.LOSQp  → ligne de stat
#     span.OkRBU         → nom de la stat
#     span.bLeWt (x2)    → valeur home / away
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

    print(f"\n🔍 gameId={game_id}  {url}")

    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.Gamestrip__Container"))
        )
    except TimeoutException:
        print(f"  ⚠️  Timeout chargement page")
        return None
    except WebDriverException as e:
        print(f"  ⚠️  WebDriver : {e}")
        return None

    time.sleep(1.5)

    home, away             = extract_teams_gamestrip(driver)
    home_score, away_score, status = extract_score(driver)
    featured               = extract_featured_standings(driver)
    events                 = extract_events(driver)
    stats                  = extract_stats(driver)

    result = {
        "gameId":            game_id,
        "url":               url,
        "team_home":         home["name"],
        "team_home_id":      home["team_id"],
        "team_home_sigle":   home["sigle"],
        "team_away":         away["name"],
        "team_away_id":      away["team_id"],
        "team_away_sigle":   away["sigle"],
        "home_score":        home_score,
        "away_score":        away_score,
        "status":            status,
        "featured_standings": featured,
        "events":            events,
        "stats":             stats,
    }

    print(f"  ✅ {home['name']} (id={home['team_id']}) {home_score} - {away_score} {away['name']} (id={away['team_id']})  [{status}]")
    print(f"  📊 {len(stats)} stats | {len(events)} événements")
    for ev in events:
        print(f"     • [{ev['type']}] {ev['text']}")

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