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
    # ajouter d'autres URLs ici
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
# ÉQUIPES DEPUIS L'URL
# Format ESPN : /gameId/XXXXX/team1-team2
# ─────────────────────────────────────────────

def teams_from_url(url):
    """
    Extrait les slugs d'équipes depuis l'URL ESPN.
    ex: /avai-ceara → ["avai", "ceara"]
    """
    m = re.search(r"/gameId/\d+/([a-z0-9\-]+)", url)
    if not m:
        return None, None
    slug = m.group(1)
    # Tente de couper au milieu (le slug ESPN est toujours team1-team2)
    # On cherche le séparateur en comparant avec les noms dans le gamestrip
    return slug  # retourné brut, sera affiné après scraping

# ─────────────────────────────────────────────
# EXTRACTION ÉQUIPES DEPUIS GAMESTRIP
# Les deux équipes sont dans span.NMnSM (nom long)
# ─────────────────────────────────────────────

def extract_teams(driver):
    """
    Récupère home/away : nom complet, sigle et ESPN team_id.
    Les liens équipes dans le Gamestrip :
      href="/soccer/team/_/id/9969/ceara"  → id=9969
      span.NMnSM = nom long
      span.HUcap = sigle
    """
    teams = []
    try:
        # Liens équipes dans le Gamestrip (data-clubhouse-uid présent)
        links = driver.find_elements(
            By.CSS_SELECTOR,
            "a[data-clubhouse-uid][href*='/soccer/team/_/id/']"
        )
        seen = []
        for a in links:
            href = a.get_attribute("href") or ""
            m = re.search(r"/soccer/team/_/id/(\d+)/", href)
            if not m:
                continue
            team_id = m.group(1)
            if team_id in seen:
                continue
            seen.append(team_id)

            try:
                name  = a.find_element(By.CSS_SELECTOR, "span.NMnSM").text.strip()
            except NoSuchElementException:
                name  = ""
            try:
                sigle = a.find_element(By.CSS_SELECTOR, "span.HUcap").text.strip()
            except NoSuchElementException:
                sigle = ""

            if name or sigle:
                teams.append({"name": name or sigle, "sigle": sigle, "team_id": team_id})

    except Exception as e:
        print(f"    ⚠️  Erreur équipes gamestrip : {e}")

    home = teams[0] if len(teams) > 0 else {"name": None, "sigle": None, "team_id": None}
    away = teams[1] if len(teams) > 1 else {"name": None, "sigle": None, "team_id": None}
    return home, away

# ─────────────────────────────────────────────
# ÉQUIPES EN GRAS DANS LE CLASSEMENT
# featuredTeam = équipes qui jouent ce match
# ─────────────────────────────────────────────

def extract_featured_teams_standings(driver):
    """
    Dans le tableau de classement, les équipes du match
    ont la classe 'featuredTeam' (affichées en gras).
    Retourne leurs noms dans l'ordre du classement (pas forcément home/away).
    """
    teams = []
    try:
        els = driver.find_elements(
            By.CSS_SELECTOR,
            "a.AnchorLink.featuredTeam span.Standings__TeamName"
        )
        for el in els:
            t = el.text.strip()
            if t and t not in teams:
                teams.append(t)
    except Exception as e:
        print(f"    ⚠️  Erreur featured standings : {e}")
    return teams

# ─────────────────────────────────────────────
# SCORE ET STATUT
# ─────────────────────────────────────────────

def extract_score(driver):
    """
    Score home/away depuis les div.uCTxv du Gamestrip.
    Statut (FT / HT / XX') depuis span.zRALO.
    """
    home_score = away_score = status = None
    try:
        score_els = driver.find_elements(By.CSS_SELECTOR, "div.uCTxv")
        scores = [s.text.strip() for s in score_els if re.match(r"^\d+$", s.text.strip())]
        if len(scores) >= 2:
            home_score, away_score = scores[0], scores[1]
        elif len(scores) == 1:
            home_score = scores[0]
    except Exception as e:
        print(f"    ⚠️  Erreur score : {e}")

    try:
        st_els  = driver.find_elements(By.CSS_SELECTOR, "span.zRALO")
        statuses = [s.text.strip() for s in st_els if s.text.strip()]
        if statuses:
            status = statuses[0]
    except Exception:
        pass

    return home_score, away_score, status

# ─────────────────────────────────────────────
# ÉVÉNEMENTS (buts, cartons)
# ─────────────────────────────────────────────

def extract_events(driver):
    """
    Récupère les événements affichés dans le Gamestrip :
    - Buts : icône data-icon="soccer-goal02"
    - Cartons : icône data-icon="soccer-card03"
      → rouge si fill contient #FF3232 / red
      → jaune sinon
    """
    events = []
    try:
        # Chaque bloc événement = div contenant texte + svg icône
        blocks = driver.find_elements(
            By.CSS_SELECTOR,
            "div.VZTD.ZLXw.yvbRH.JLJBa.CLwPV.ucZkc"
        )
        for block in blocks:
            try:
                text_el = block.find_element(By.CSS_SELECTOR, "div.awXxV.rlVU.vXdaT")
                text = text_el.text.strip()
            except NoSuchElementException:
                continue

            event_type = "unknown"
            try:
                svg = block.find_element(By.CSS_SELECTOR, "svg[data-icon]")
                icon_name = svg.get_attribute("data-icon") or ""
                if "goal" in icon_name:
                    event_type = "goal"
                elif "card" in icon_name:
                    try:
                        path_fill = svg.find_element(By.TAG_NAME, "path").get_attribute("fill") or ""
                        if "FF3232" in path_fill.upper() or "red" in path_fill.lower():
                            event_type = "red_card"
                        else:
                            event_type = "yellow_card"
                    except Exception:
                        event_type = "card"
            except NoSuchElementException:
                pass

            if text:
                events.append({"type": event_type, "text": text})

    except Exception as e:
        print(f"    ⚠️  Erreur événements : {e}")

    return events

# ─────────────────────────────────────────────
# STATS DU MATCH
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

    print(f"\n🔍 {url}")

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

    time.sleep(1.5)  # laisser le JS finir de rendre

    home, away                     = extract_teams(driver)
    home_score, away_score, status = extract_score(driver)
    featured                       = extract_featured_teams_standings(driver)
    events                         = extract_events(driver)
    stats                          = extract_stats(driver)

    result = {
        "gameId":     game_id,
        "url":        url,
        "team_home":  home["name"],
        "team_away":  away["name"],
        "team_home_id":  home["team_id"],
        "team_away_id":  away["team_id"],
        "team_home_sigle": home["sigle"],
        "team_away_sigle": away["sigle"],
        "home_score": home_score,
        "away_score": away_score,
        "status":     status,
        "featured_in_standings": featured,
        "events":     events,
        "stats":      stats,
    }

    print(f"  ✅ {home['name']} (id={home['team_id']}) {home_score} - {away_score} {away['name']} (id={away['team_id']})  [{status}]")
    print(f"  📊 {len(stats)} stats | {len(events)} événements")
    if featured:
        print(f"  🔲 En gras dans classement : {featured}")
    for ev in events:
        print(f"     • [{ev['type']}] {ev['text']}")

    return result

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

driver = create_driver()
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