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
# HELPERS GÉNÉRIQUES
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


def to_int_stat(value):
    """Convertit une valeur de statistique brute en entier si possible."""
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace(",", "").strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return int(round(float(text)))
    return value


def finalize_stats(stats):
    """Convertit systématiquement chaque valeur home/away en int."""
    cleaned = {}
    for label, vals in stats.items():
        if not isinstance(vals, dict):
            cleaned[label] = vals
            continue
        cleaned[label] = {
            "home": to_int_stat(vals.get("home")),
            "away": to_int_stat(vals.get("away")),
        }
    return cleaned


def us_to_decimal(val):
    """Convertit une cote américaine en cote décimale."""
    if not val:
        return None
    try:
        n = int(val.replace("+", "").strip())
        return round(1 + (n / 100), 2) if n > 0 else round(1 + (100 / abs(n)), 2)
    except Exception:
        return None


# ===============================================================
# EXTRACTION D'UNE LIGNE DE MATCH (page schedule)
# ===============================================================

def extract_match_row(row, match_date):
    """
    Parse une ligne <tr> de la page schedule ESPN. Structure réelle
    observée :
      [0] events__col -> équipe à domicile (classe Table__Team away
                         dans le HTML ESPN, mais correspond en
                         réalité au lieu du match, donc au domicile)
      [1] colspan__col -> lien score/match + équipe extérieure
                         (bloc "local" dans le HTML ESPN)
      [2] teams__col   -> statut (FT, ou heure si match à venir)
    L'heure et le lieu précis sont récupérés plus tard sur la page
    du match elle-même (section "Game Information").
    """
    cells = row.find_all("td")
    if len(cells) < 3:
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

    return {
        "date": match_date,
        "time": None,
        "status": status,
        "home_team": home_team_name,
        "home_team_id": home_team_id,
        "home_logo_url": build_logo_url(home_team_id),
        "home_score": home_score,
        "away_team": away_team_name,
        "away_team_id": away_team_id,
        "away_logo_url": build_logo_url(away_team_id),
        "away_score": away_score,
        "venue": None,
        "match_id": game_id,
        "match_url": match_url,
        "stats": {},
        "odds": {"home": None, "away": None, "draw": None},
    }


# ===============================================================
# EXTRACTION DES STATS D'ÉQUIPE (page du match, structure Prism)
# ===============================================================

def extract_match_stats(soup):
    """
    Extrait les statistiques d'équipe depuis la section "Team Stats"
    de la page du match (structure Prism ESPN).
    """
    stats = {}
    try:
        section = None
        for sec in soup.find_all("section", {"data-testid": "prism-LayoutCard"}):
            h2 = sec.find("h2", {"data-testid": "prism-LayoutCardSlot"})
            if h2 and "stat" in h2.get_text(strip=True).lower():
                section = sec
                break

        if not section:
            return stats

        stat_blocks = section.select("div.THHyw")
        for block in stat_blocks:
            paragraphs = block.select("div.jaZjJ p")
            if len(paragraphs) < 3:
                continue

            home_span = paragraphs[0].find("span")
            home_val = home_span.get_text(strip=True) if home_span else paragraphs[0].get_text(strip=True)

            label = paragraphs[1].get_text(strip=True)

            away_span = paragraphs[2].find("span")
            away_val = away_span.get_text(strip=True) if away_span else paragraphs[2].get_text(strip=True)

            if label:
                stats[label] = {"home": home_val, "away": away_val}

    except Exception as e:
        print(f"  ⚠️ Erreur extraction stats : {e}")

    return stats


# ===============================================================
# MI-TEMPS / 2NDE MI-TEMPS (repris de Teams_tracker.py)
# ===============================================================

def extract_match_timeline_halftime(soup):
    """
    Extrait le score à la mi-temps et à la 2nde mi-temps depuis la
    frise "Match Timeline".
    """
    try:
        section = None
        for sec in soup.find_all("section", {"data-testid": "prism-LayoutCard"}):
            h2 = sec.find("h2", {"data-testid": "prism-LayoutCardSlot"})
            if h2 and "match timeline" in h2.get_text(strip=True).lower():
                section = sec
                break

        if not section:
            return None, None

        ht_percent = None
        for span in section.find_all("span"):
            if span.get_text(strip=True).upper() == "HT":
                style = span.get("style", "")
                m = re.search(r"left:\s*([\d.]+)%", style)
                if m:
                    ht_percent = float(m.group(1))
                break
        if ht_percent is None:
            ht_percent = 50.0

        icon_rows = section.select("div.XYehN.ThkOQ.lZur")
        if len(icon_rows) < 2:
            return None, None

        def count_goals(row):
            first_half = 0
            second_half = 0
            for icon_div in row.select('div[role="button"]'):
                svg = icon_div.find("svg", attrs={"data-icon": "soccer-goal02"})
                if not svg:
                    continue
                style = icon_div.get("style", "")
                m = re.search(r"left:\s*([\d.]+)%", style)
                pos = float(m.group(1)) if m else None
                if pos is None:
                    continue
                if pos <= ht_percent:
                    first_half += 1
                else:
                    second_half += 1
            return first_half, second_half

        home_ht, home_2h = count_goals(icon_rows[0])
        away_ht, away_2h = count_goals(icon_rows[1])

        return {"home": home_ht, "away": away_ht}, {"home": home_2h, "away": away_2h}

    except Exception as e:
        print(f"  ⚠️ Erreur extraction mi-temps (timeline) : {e}")
        return None, None


# ===============================================================
# COTES 1X2 (repris de Teams_tracker.py)
# ===============================================================

def extract_match_odds(soup):
    """
    Extrait les cotes 1X2 (Moneyline) depuis la page du match.
    Reprend exactement la logique validée de Teams_tracker.py :
    les cellules home/away/draw correspondent aux index 0, 3 et 6
    parmi les div[data-testid="OddsCell"] (7 cellules minimum).
    """
    empty = {"home": None, "away": None, "draw": None}
    try:
        cells = soup.find_all("div", {"data-testid": "OddsCell"})
        if len(cells) < 7:
            return empty

        def read(cell):
            return cell.get_text(strip=True) or None

        def is_valid(val):
            if not val:
                return False
            try:
                int(val.replace("+", "").replace("-", ""))
                return True
            except Exception:
                return False

        home_us = read(cells[0])
        away_us = read(cells[3])
        draw_us = read(cells[6])

        if not all(is_valid(v) for v in [home_us, away_us, draw_us]):
            return empty

        return {
            "home": us_to_decimal(home_us),
            "away": us_to_decimal(away_us),
            "draw": us_to_decimal(draw_us),
        }
    except Exception as e:
        print(f"  ⚠️ Erreur extraction cotes : {e}")
        return empty


# ===============================================================
# HEURE ET LIEU DU MATCH (section "Game Information")
# ===============================================================

def extract_game_time_and_venue(soup):
    """
    Extrait l'heure du match et le lieu (stade + ville/pays) depuis
    la section "Game Information" de la page du match.
    Retourne (time_str, venue_str). La date n'est pas ré-extraite ici
    puisqu'elle est déjà connue depuis la page schedule.
    """
    time_value = None
    venue_value = None

    try:
        section = None
        for sec in soup.find_all("section", {"data-testid": "prism-LayoutCard"}):
            h2 = sec.find("h2", {"data-testid": "prism-LayoutCardSlot"})
            if h2 and "game information" in h2.get_text(strip=True).lower():
                section = sec
                break

        if not section:
            return time_value, venue_value

        # --- Heure (bloc avec l'icône calendrier) ---
        calendar_icon = section.find("svg", attrs={"data-icon": "misc-calendarOutline"})
        if calendar_icon:
            block = calendar_icon.find_parent("div", class_="RbXOe")
            if block:
                h4 = block.find("h4")
                if h4:
                    raw_text = h4.get_text(strip=True)
                    # Format observé: "7:00 PM, May 18, 2026"
                    m = re.match(r"^([\d:]+\s*[APMapm]{2})", raw_text)
                    time_value = m.group(1).strip() if m else raw_text

        # --- Lieu (bloc avec l'icône de localisation) ---
        location_icon = section.find("svg", attrs={"data-icon": "misc-locationPin"})
        if location_icon:
            block = location_icon.find_parent("div", class_="RbXOe")
            if block:
                h4 = block.find("h4")
                stadium_name = h4.get_text(strip=True) if h4 else ""

                p = block.find("p")
                city_country = p.get_text(" ", strip=True) if p else ""
                city_country = re.sub(r"\s+", " ", city_country).strip()

                if stadium_name and city_country:
                    venue_value = f"{stadium_name}, {city_country}"
                else:
                    venue_value = stadium_name or city_country or None

    except Exception as e:
        print(f"  ⚠️ Erreur extraction heure/lieu : {e}")

    return time_value, venue_value


# ===============================================================
# VISITE DE LA PAGE DU MATCH — enrichissement complet
# ===============================================================

def get_match_details(driver, match_url):
    """
    Charge la page du match via Selenium et retourne
    (stats, odds, time, venue).
    """
    empty_odds = {"home": None, "away": None, "draw": None}
    if not match_url:
        return {}, empty_odds, None, None

    try:
        driver.get(match_url)
        WebDriverWait(driver, 12).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "section[data-testid='prism-LayoutCard']")
            )
        )
        time.sleep(1)
    except TimeoutException:
        pass
    except WebDriverException as e:
        print(f"    ⚠️ WebDriver erreur ({match_url}) : {e}")
        return {}, empty_odds, None, None

    soup = BeautifulSoup(driver.page_source, "html.parser")

    stats = extract_match_stats(soup)
    odds = extract_match_odds(soup)
    match_time, venue = extract_game_time_and_venue(soup)

    try:
        halftime, second_half = extract_match_timeline_halftime(soup)
        if halftime is not None:
            stats["Score 1ère mi-temps"] = {"home": halftime["home"], "away": halftime["away"]}
        if second_half is not None:
            stats["Score 2nde mi-temps"] = {"home": second_half["home"], "away": second_half["away"]}
    except Exception as e:
        print(f"    ⚠️ Erreur injection mi-temps : {e}")

    stats = finalize_stats(stats)

    return stats, odds, match_time, venue


def enrich_matches_with_details(driver, matches):
    """
    Visite chaque match (via son match_url) pour récupérer les stats
    d'équipe, les cotes 1X2, les scores de mi-temps/2nde mi-temps,
    ainsi que l'heure et le lieu du match, puis les injecte dans
    chaque dict de match.
    """
    total = len(matches)
    print("\n" + "=" * 60)
    print(f"🔄 PHASE D'ENRICHISSEMENT — Stats, cotes, mi-temps, heure & lieu ({total} match(s))")
    print("=" * 60)

    for idx, match in enumerate(matches, 1):
        if not match.get("match_url"):
            continue

        print(f"\n  [{idx}/{total}] {match['home_team']} vs {match['away_team']} "
              f"(id={match['match_id']})")

        try:
            stats, odds, match_time, venue = get_match_details(driver, match["match_url"])
        except Exception as e:
            print(f"    ⚠️ Erreur enrichissement gameId={match['match_id']}: {e}")
            stats = {}
            odds = {"home": None, "away": None, "draw": None}
            match_time, venue = None, None

        match["stats"] = stats
        match["odds"] = odds
        match["time"] = match_time
        match["venue"] = venue

        odds_str = (
            f"💰 {odds['home']}/{odds['draw']}/{odds['away']}"
            if odds.get("home") is not None
            else "ℹ️ pas de cotes"
        )
        print(f"    📊 {len(stats)} statistique(s)  |  {odds_str}  |  🕒 {match_time}  |  📍 {venue}")
        time.sleep(0.8)


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
    print("⚽ ESPN SCHEDULE SCRAPER — par date / ligue (+ stats, cotes, mi-temps, heure & lieu)")
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

        if matches:
            enrich_matches_with_details(driver, matches)
        else:
            print("\nℹ️ Aucun match à enrichir")

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