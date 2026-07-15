from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
import json
import re
import os
import time
from datetime import datetime

# ===============================================================
# CONFIGURATION
# ===============================================================

LEAGUE_SLUG = "eng.1"          # eng.1 = Premier League (voir /soccer/schedule/_/date/.../league/{slug})
SCHEDULE_DATE = "20260520"     # format YYYYMMDD, comme dans l'URL fournie

OUTPUT_DIR = os.path.join("data", "football", "schedule")
OUTPUT_JSON_PATH = os.path.join(OUTPUT_DIR, f"schedule_{SCHEDULE_DATE}.json")

BASE_URL = "https://www.espn.com"


# ===============================================================
# SETUP SELENIUM
# ===============================================================

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--lang=en-US,en")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(10)
    return driver


# ===============================================================
# HELPERS
# ===============================================================

def fix_url(url, base=BASE_URL):
    """Normalise une URL relative en URL absolue."""
    if not url:
        return ""
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        return f"https:{url}"
    return f"{base}{url}"


KNOWN_TEAM_ACRONYMS = {
    "afc", "fc", "cf", "fk", "sc", "ac", "ca", "cd", "us", "as",
    "ud", "sv", "vfb", "vfl", "tsv", "bsc", "rc", "rcd", "cfc",
}


def normalize_team_name(name):
    """Met en majuscules les acronymes connus au sein d'un nom d'équipe."""
    if not name:
        return name
    words = name.split(" ")
    normalized_words = [
        w.upper() if w.lower() in KNOWN_TEAM_ACRONYMS else w
        for w in words
    ]
    return " ".join(normalized_words)


def team_name_from_href(href):
    """Extrait le nom lisible depuis l'URL de l'équipe ESPN (.../id/{id}/{slug})."""
    if not href:
        return ""
    slug = href.rstrip("/").split("/")[-1]
    raw_name = slug.replace("-", " ").title()
    return normalize_team_name(raw_name)


def extract_team_id(href):
    """Extrait l'ID d'équipe depuis une URL ESPN /soccer/team/_/id/{id}/..."""
    if not href:
        return None
    m = re.search(r"/id/(\d+)/", href)
    return m.group(1) if m else None


def build_logo_url(team_id):
    """Construit l'URL du logo ESPN à partir de l'ID d'équipe."""
    if not team_id:
        return ""
    return f"https://a.espncdn.com/i/teamlogos/soccer/500/{team_id}.png"


def parse_title_date(title_text):
    """
    Convertit un titre de bloc de type "Sunday, May 24, 2026" en date
    ISO "YYYY-MM-DD". Retourne None si le format n'est pas reconnu.
    """
    if not title_text:
        return None
    cleaned = title_text.strip()
    try:
        dt = datetime.strptime(cleaned, "%A, %B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_score_text(score_text):
    """
    Extrait (home_score, away_score) depuis un texte de type
    "  0 - 3  ". Retourne (None, None) si aucun score n'est trouvé
    (cas d'un match pas encore joué, où ce champ contient une heure).
    """
    if not score_text:
        return None, None
    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", score_text)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def extract_attendance(text):
    """Convertit un texte d'affluence ("31,729" ou "N/A") en entier ou None."""
    if not text:
        return None
    cleaned = text.strip().replace(",", "")
    return int(cleaned) if cleaned.isdigit() else None


# ===============================================================
# EXTRACTION D'UNE LIGNE DE MATCH
# ===============================================================

def extract_match_row(row, match_date):
    """
    Parse une ligne <tr> de la page schedule ESPN. Structure réelle
    observée (5 <td>) :
      [0] events__col   -> équipe à domicile (classe Table__Team away
                           dans le HTML ESPN, mais correspond en
                           réalité au lieu/venue du match, donc au
                           domicile)
      [1] colspan__col   -> lien score/match + équipe extérieure
                           (bloc "local" dans le HTML ESPN)
      [2] teams__col     -> statut (FT, ou heure si match à venir)
      [3] venue__col     -> lieu du match
      [4] attendance__col -> affluence
    Convention : vérifiée empiriquement via le lieu du match — le
    venue correspond systématiquement à l'équipe de cells[0], donc
    cells[0] = domicile et l'équipe du bloc "local" = extérieur.
    """
    cells = row.find_all("td")
    if len(cells) < 5:
        return None

    # --- Équipe à domicile (cells[0]) ---
    home_container = cells[0].select_one("span.Table__Team.away") or cells[0]
    home_links = home_container.find_all("a")
    home_href = home_links[0].get("href") if home_links else ""
    home_team_id = extract_team_id(home_href)
    home_team_name = team_name_from_href(home_href)

    # --- Bloc score + équipe extérieure (cells[1]) ---
    local_div = cells[1].select_one("div.local") or cells[1]

    score_link = local_div.select_one("a.at") or local_div.find("a")
    match_url = fix_url(score_link.get("href")) if score_link else ""
    game_id_m = re.search(r"/gameId/(\d+)", match_url)
    game_id = game_id_m.group(1) if game_id_m else None

    score_text = score_link.get_text(strip=True) if score_link else ""
    home_score, away_score = parse_score_text(score_text)

    away_container = local_div.select_one("span.Table__Team")
    away_links = away_container.find_all("a") if away_container else []
    away_href = away_links[0].get("href") if away_links else ""
    away_team_id = extract_team_id(away_href)
    away_team_name = team_name_from_href(away_href)

    # --- Statut (cells[2]) : "FT" si terminé, sinon heure du coup d'envoi ---
    status_el = cells[2].find("a") or cells[2]
    status = status_el.get_text(strip=True) if status_el else None

    # --- Lieu (cells[3]) ---
    venue_el = cells[3].find("div")
    venue = venue_el.get_text(strip=True) if venue_el else None

    # --- Affluence (cells[4]) ---
    attendance_text = cells[4].get_text(strip=True) if len(cells) > 4 else None
    attendance = extract_attendance(attendance_text)

    return {
        "date": match_date,
        "status": status,
        "home_team": home_team_name,
        "home_team_id": home_team_id,
        "home_logo_url": build_logo_url(home_team_id),
        "home_score": home_score,
        "away_team": away_team_name,
        "away_team_id": away_team_id,
        "away_logo_url": build_logo_url(away_team_id),
        "away_score": away_score,
        "venue": venue,
        "attendance": attendance,
        "match_id": game_id,
        "match_url": match_url,
    }


# ===============================================================
# SCRAPING DE LA PAGE SCHEDULE
# ===============================================================

def scrape_schedule_page(driver, date_str, league_slug):
    """
    Scrape la page schedule ESPN pour une date et une ligue données.
    Retourne la liste des matchs trouvés (tous blocs ResponsiveTable
    confondus, chaque bloc correspondant en général à une journée).
    """
    url = f"{BASE_URL}/soccer/schedule/_/date/{date_str}/league/{league_slug}"
    print(f"🌐 Accès: {url}")

    driver.get(url)
    print("⏳ Attente du chargement initial (5s)...")
    time.sleep(5)

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.ResponsiveTable"))
        )
        print("✅ Tables détectées")
    except TimeoutException:
        print("⚠️ Timeout en attendant les tables — tentative quand même…")

    soup = BeautifulSoup(driver.page_source, "html.parser")
    tables = soup.select("div.ResponsiveTable")
    print(f"📊 {len(tables)} bloc(s) trouvé(s)")

    if not tables:
        print("❌ Aucun tableau trouvé pour cette date/ligue.")
        return []

    all_matches = []

    for table in tables:
        title_el = table.select_one("div.Table__Title")
        title_text = title_el.get_text(strip=True) if title_el else ""
        match_date = parse_title_date(title_text) or date_str
        print(f"\n📅 Bloc: {title_text or '(sans titre)'}")

        rows = table.select("tr.Table__TR.Table__TR--sm")
        print(f"   → {len(rows)} ligne(s) trouvée(s)")

        for row in rows:
            match_data = extract_match_row(row, match_date)
            if match_data:
                all_matches.append(match_data)
                score_str = (
                    f"{match_data['home_score']} - {match_data['away_score']}"
                    if match_data["home_score"] is not None
                    else match_data["status"]
                )
                print(
                    f"   ✅ {match_data['home_team']} {score_str} {match_data['away_team']}"
                    f"  (id={match_data['match_id']})"
                )
            else:
                print("   ⚠️ Ligne ignorée (extraction échouée)")

    return all_matches


# ===============================================================
# MAIN
# ===============================================================

def main():
    print("=" * 60)
    print("⚽ ESPN SCHEDULE SCRAPER — par date / ligue")
    print(f"📆 Date: {SCHEDULE_DATE}  |  Ligue: {LEAGUE_SLUG}")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    driver = None
    matches = []

    try:
        print("\n🚀 Démarrage du navigateur (headless)...")
        driver = setup_driver()
        print("✅ Navigateur démarré")

        matches = scrape_schedule_page(driver, SCHEDULE_DATE, LEAGUE_SLUG)

    except WebDriverException as e:
        print(f"❌ Erreur WebDriver: {e}")
    except Exception as e:
        print(f"❌ Erreur globale: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            print("\n🧹 Fermeture du navigateur…")
            driver.quit()

    output_data = {
        "date": SCHEDULE_DATE,
        "league": LEAGUE_SLUG,
        "scraped_at": datetime.now().isoformat(),
        "nb_matches": len(matches),
        "matches": matches,
    }

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2, separators=(",", ": "))

    print(f"\n💾 {OUTPUT_JSON_PATH} sauvegardé ({len(matches)} match(s))")


if __name__ == "__main__":
    main()
