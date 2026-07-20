from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup
import json
import time
import re
import shutil
import os
import urllib.request
from datetime import datetime

TEAMS_JSON_URL = "https://raw.githubusercontent.com/PariALLIANCE/Data-Sports/main/data/football/teams/football_teams.json"

# ── Sélection des ligues par plage d'index (1-based, inclusif) ──
# Exemple : LEAGUE_INDEX_START=1, LEAGUE_INDEX_END=1  → uniquement la 1ère ligue
# Exemple : LEAGUE_INDEX_START=1, LEAGUE_INDEX_END=5  → les 5 premières ligues
# Exemple : LEAGUE_INDEX_START=3, LEAGUE_INDEX_END=8  → de la 3ème à la 8ème ligue
# L'ordre des ligues est celui d'apparition dans football_teams.json (liste
# affichée en console au démarrage pour connaître les index disponibles).
LEAGUE_INDEX_START = 4
LEAGUE_INDEX_END = 5

START_SEASON = 2024
END_SEASON = datetime.now().year  # saison actuelle incluse

# ── Chemins de sortie / nettoyage ───────────────────────────────
LEAGUES_DIR = os.path.join("data", "football", "leagues")
DATASET_TMP_DIR = "dataset_tmp"
OUTPUT_JSON_PATH = os.path.join(LEAGUES_DIR, "data_teams.json")

# ── Préfixes de nationalité à retirer pour obtenir un libellé court ──
COUNTRY_ADJECTIVES = [
    "English", "Spanish", "Italian", "German", "French", "Portuguese",
    "Dutch", "Scottish", "Brazilian", "Turkish", "Belgian",
]


def reset_output_directories():
    """
    Prépare l'environnement de sortie SANS supprimer l'historique déjà
    trackée : data/football/leagues n'est plus supprimé. Seul
    dataset_tmp est supprimé.
    """
    os.makedirs(LEAGUES_DIR, exist_ok=True)
    print(f"📁 Dossier prêt (non réinitialisé): {LEAGUES_DIR}")

    if os.path.isdir(DATASET_TMP_DIR):
        print(f"🗑️  Suppression du dossier temporaire: {DATASET_TMP_DIR}")
        shutil.rmtree(DATASET_TMP_DIR)
    else:
        print(f"ℹ️  Aucun dossier temporaire {DATASET_TMP_DIR} à supprimer")


def load_existing_data():
    """
    Charge le JSON existant s'il existe, et retourne un dict
    {team_id: team_entry}.
    """
    if not os.path.isfile(OUTPUT_JSON_PATH):
        print(f"ℹ️ Aucun fichier existant ({OUTPUT_JSON_PATH}) — toutes les équipes seront traitées comme non trackées")
        return {}
    try:
        with open(OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"⚠️ Erreur lecture JSON existant : {e} — traité comme absent")
        return {}

    by_id = {}
    for team_entry in data.get("teams", []):
        tid = team_entry.get("team_id")
        if tid:
            by_id[tid] = team_entry

    print(f"📂 {len(by_id)} équipe(s) déjà trackée(s) trouvée(s) dans le JSON existant")
    return by_id


def flatten_existing_matches(team_entry):
    """Aplati matches_by_season d'une entrée existante en liste simple."""
    flat = []
    for season_matches in team_entry.get("matches_by_season", {}).values():
        flat.extend(season_matches)
    return flat


def merge_matches(existing_matches, new_matches):
    """
    Fusionne les matchs déjà connus avec les matchs fraîchement
    scrapés. Retourne (merged_matches, new_match_ids).
    """
    existing_by_id = {}
    no_id_existing = []
    for m in existing_matches:
        mid = m.get("match_id")
        if mid:
            existing_by_id[mid] = m
        else:
            no_id_existing.append(m)

    merged_by_id = dict(existing_by_id)
    new_match_ids = set()
    no_id_new = []

    for m in new_matches:
        mid = m.get("match_id")
        if mid:
            if mid not in existing_by_id:
                new_match_ids.add(mid)
            merged_by_id[mid] = m
        else:
            no_id_new.append(m)

    merged = list(merged_by_id.values()) + no_id_existing + no_id_new
    return merged, new_match_ids


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


def fix_url(url, base="https://www.espn.com"):
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
    """Extrait le nom lisible depuis l'URL de l'équipe ESPN."""
    if not href:
        return ""
    slug = href.rstrip("/").split("/")[-1]
    raw_name = slug.replace("-", " ").title()
    return normalize_team_name(raw_name)


def build_team_slug(team_name):
    """Construit un slug simplifié pour l'URL des fixtures ESPN."""
    if not team_name:
        return ""
    return re.sub(r"[^a-zA-Z0-9]+", "-", team_name.strip().lower()).strip("-")


def build_logo_url(team_id):
    """Construit l'URL du logo ESPN à partir de l'ID d'équipe."""
    if not team_id:
        return ""
    return f"https://a.espncdn.com/i/teamlogos/soccer/500/{team_id}.png"


def simplify_competition_label(competition):
    """
    Retire un préfixe de nationalité connu d'un libellé de compétition
    (ex: "English Premier League" → "Premier League").
    """
    if not competition:
        return competition
    text = competition.strip()
    for adj in COUNTRY_ADJECTIVES:
        if text.startswith(adj + " "):
            return text[len(adj) + 1:].strip()
    return text


# ===============================================================
# DÉCOUVERTE DES LIGUES DISPONIBLES ET SÉLECTION PAR PLAGE D'INDEX
# ===============================================================

def fetch_teams_json():
    """Télécharge et retourne le contenu complet de football_teams.json."""
    print(f"🌐 Téléchargement de {TEAMS_JSON_URL}")
    req = urllib.request.Request(TEAMS_JSON_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_all_leagues(data):
    """
    Construit la liste ordonnée (et dédupliquée) de toutes les ligues
    présentes dans football_teams.json, dans leur ordre d'apparition
    (pays par pays, puis équipe par équipe). Chaque entrée est un dict
    {"country": ..., "league_name": ...}. C'est cette liste, numérotée
    à partir de 1, qui sert de référence pour LEAGUE_INDEX_START/END.
    """
    leagues = []
    seen = set()
    for country, teams_list in data.items():
        for t in teams_list:
            league_name = t.get("league_name")
            if league_name and league_name not in seen:
                seen.add(league_name)
                leagues.append({"country": country, "league_name": league_name})
    return leagues


def select_leagues_by_range(all_leagues, index_start, index_end):
    """
    Sélectionne une plage de ligues (1-based, inclusive) parmi
    all_leagues, avec clamp automatique sur les bornes valides.
    """
    n = len(all_leagues)
    if n == 0:
        return []

    start = max(1, index_start)
    end = min(n, index_end)

    if start > end:
        print(f"⚠️ Plage invalide (start={index_start}, end={index_end}) — aucune ligue sélectionnée")
        return []

    return all_leagues[start - 1:end]


def target_league_label(league_name, country):
    """
    Dérive le libellé ESPN correspondant à un league_name composite
    (ex: "England_Premier_League" + country="England" → "Premier League").
    """
    parts = league_name.split("_")
    if len(parts) > 1 and parts[0] == country:
        parts = parts[1:]
    return " ".join(parts)


def fetch_teams_for_league(data, country, league_name):
    """
    Retourne TOUTES les équipes d'une ligue donnée (country +
    league_name) à partir du JSON déjà téléchargé.
    """
    country_teams = data.get(country, [])
    league_teams = [t for t in country_teams if t.get("league_name") == league_name]

    print(f"📋 {len(league_teams)} équipe(s) trouvée(s) pour {league_name}")
    for t in league_teams:
        print(f"   - {t['team']} (id={t['team_id']})")

    return league_teams


MONTH_ORDER = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


def format_season(season):
    """Convertit une saison ESPN en libellé "YYYY/YYYY+1"."""
    season = int(season)
    return f"{season}/{season + 1}"


def build_iso_date(date_text, month_text, year_str):
    """Construit une date ISO (YYYY-MM-DD) à partir des champs bruts ESPN."""
    month_str = (month_text or "").split(",")[0].strip()
    month_num = MONTH_ORDER.get(month_str, 0)

    day_m = re.search(r"(\d+)", date_text or "")
    day = int(day_m.group(1)) if day_m else 0

    year = int(year_str) if year_str and str(year_str).isdigit() else 0

    if month_num and day and year:
        try:
            return datetime(year, month_num, day).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def date_sort_key(m):
    """Clé de tri chronologique basée sur le champ "date" ISO."""
    d = m.get("date")
    if not d:
        return (0, 0, 0)
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        return (dt.year, dt.month, dt.day)
    except (ValueError, TypeError):
        return (0, 0, 0)


def extract_match_info(match_row, month, season):
    """Structure réelle ESPN (6 <td>) pour la page résultats."""
    try:
        cells = match_row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 6:
            return None

        date_els = cells[0].find_elements(By.CSS_SELECTOR, '[data-testid="date"]')
        date = date_els[0].text.strip() if date_els else ""

        local_links = cells[1].find_elements(By.TAG_NAME, "a")
        if not local_links:
            return None
        local_href = local_links[0].get_attribute("href") or ""
        local_id_m = re.search(r"/id/(\d+)/", local_href)
        local_team_id = local_id_m.group(1) if local_id_m else ""
        local_team_name = team_name_from_href(local_href)

        score_links = cells[2].find_elements(By.TAG_NAME, "a")

        home_score_raw = ""
        away_score_raw = ""
        match_url = ""
        match_id = ""

        if len(score_links) >= 3:
            score_text = score_links[1].text.strip()
            match_url = fix_url(score_links[1].get_attribute("href") or "")
            mid_m = re.search(r"/gameId/(\d+)", match_url)
            match_id = mid_m.group(1) if mid_m else ""

            score_m = re.search(r"(\d+)\s*[-:]\s*(\d+)", score_text)
            if score_m:
                home_score_raw = score_m.group(1)
                away_score_raw = score_m.group(2)

        away_links = cells[3].find_elements(By.TAG_NAME, "a")
        if not away_links:
            return None
        away_href = away_links[0].get_attribute("href") or ""
        away_id_m = re.search(r"/id/(\d+)/", away_href)
        away_team_id = away_id_m.group(1) if away_id_m else ""
        away_team_name = team_name_from_href(away_href)

        result_raw = ""
        result_els = cells[4].find_elements(By.CSS_SELECTOR, '[data-testid="result"]')
        if result_els:
            result_raw = result_els[0].text.strip()
        else:
            result_links = cells[4].find_elements(By.TAG_NAME, "a")
            if result_links:
                result_raw = result_links[0].text.strip()

        decided_by_penalties = bool(re.search(r"pens", result_raw, re.IGNORECASE))

        competition = ""
        comp_spans = cells[5].find_elements(By.TAG_NAME, "span")
        if comp_spans:
            competition = comp_spans[-1].text.strip()

        year_m = re.search(r"(\d{4})", month)
        match_year = year_m.group(1) if year_m else str(season)

        iso_date = build_iso_date(date, month, match_year)

        return {
            "date": iso_date,
            "home_team": local_team_name,
            "home_team_id": local_team_id,
            "home_logo_url": build_logo_url(local_team_id),
            "home_score": int(home_score_raw) if home_score_raw.isdigit() else None,
            "away_score": int(away_score_raw) if away_score_raw.isdigit() else None,
            "away_team": away_team_name,
            "away_team_id": away_team_id,
            "away_logo_url": build_logo_url(away_team_id),
            "match_url": match_url,
            "match_id": match_id,
            "result": result_raw,
            "decided_by_penalties": decided_by_penalties,
            "penalty_winner": None,
            "team_result": None,
            "competition": competition,
            "season": format_season(season),
            "matchday": None,
            "round": None,
            "odds": {"home": None, "away": None, "draw": None},
            "has_full_stats": False,
            "stats": {},
            "next_game": None,  # ← rempli en fin de traitement (match suivant chronologique)
        }

    except Exception as e:
        print(f"⚠️ Erreur extraction: {str(e)[:120]}")
        return None


def scrape_team_results_for_seasons(driver, team_name, team_id, seasons):
    """
    Scrape les résultats d'une équipe ESPN pour la liste de saisons
    donnée.
    """
    combined_matches = []

    for season in seasons:
        print(f"\n📆 Saison {season} — {team_name}")

        url = f"https://www.espn.com/soccer/team/results/_/id/{team_id}/season/{season}"
        print(f"🌐 Accès: {url}")
        try:
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

            result_tables = driver.find_elements(
                By.CSS_SELECTOR, "div.ResponsiveTable.Table__results-mobile"
            )
            if not result_tables:
                result_tables = driver.find_elements(By.CSS_SELECTOR, "div.ResponsiveTable")

            print(f"📊 {len(result_tables)} bloc(s) mensuel(s) trouvé(s) pour la saison {season}")

            if not result_tables:
                print(f"❌ Aucun tableau trouvé pour la saison {season}.")
                continue

            for table in result_tables:
                month_els = table.find_elements(By.CSS_SELECTOR, "div.Table__Title")
                month = month_els[0].text.strip() if month_els else "Unknown"
                print(f"\n📅 Mois: {month}")

                rows = table.find_elements(
                    By.CSS_SELECTOR, "tr.Table__TR.Table__TR--sm.Table__even"
                )
                print(f"   → {len(rows)} ligne(s) trouvée(s)")

                for row in rows:
                    match_data = extract_match_info(row, month, season)
                    if match_data:
                        combined_matches.append(match_data)
                        print(
                            f"   ✅ {match_data['home_team']} {match_data['home_score']}"
                            f" - {match_data['away_score']} {match_data['away_team']}"
                            f"  [{match_data['competition']}]"
                        )
                    else:
                        print("   ⚠️ Ligne ignorée (extraction échouée)")

        except Exception as e:
            print(f"❌ Erreur lors du scraping de {team_name} (saison {season}): {e}")
            import traceback
            traceback.print_exc()

    seen = set()
    unique_matches = []
    for m in combined_matches:
        key = m["match_id"] if m["match_id"] else f"{m['home_team']}_{m['away_team']}_{m['date']}"
        if key not in seen:
            seen.add(key)
            unique_matches.append(m)

    print(f"\n✅ {len(unique_matches)} match(s) unique(s) scrapé(s) pour {team_name} (saisons demandées: {seasons})")

    unique_matches.sort(key=date_sort_key, reverse=True)

    return unique_matches


def compute_matchdays_for_team(matches, league_label):
    """
    Calcule la journée (matchday) de championnat pour chaque match,
    saison par saison. Les matchs hors championnat gardent
    matchday = None.
    """
    league_label_lower = (league_label or "").lower()

    matches_asc = sorted(matches, key=date_sort_key)

    counters = {}
    for m in matches_asc:
        season_key = m.get("season")
        competition = (m.get("competition") or "").lower()
        if league_label_lower and league_label_lower in competition:
            counters[season_key] = counters.get(season_key, 0) + 1
            m["matchday"] = counters[season_key]
        else:
            m["matchday"] = None

    return matches


def compute_team_result(match, team_id):
    """
    Détermine le résultat du match ("V", "N", "D") du point de vue de
    l'équipe team_id.
    """
    home_score = match.get("home_score")
    away_score = match.get("away_score")
    if home_score is None or away_score is None:
        return None

    is_home = match.get("home_team_id") == team_id
    is_away = match.get("away_team_id") == team_id
    if not is_home and not is_away:
        return None

    if home_score == away_score:
        if match.get("decided_by_penalties") and match.get("penalty_winner"):
            winner_is_home = match["penalty_winner"] == "home"
            if is_home:
                return "V" if winner_is_home else "D"
            return "D" if winner_is_home else "V"
        return "N"

    team_score = home_score if is_home else away_score
    opp_score = away_score if is_home else home_score
    return "V" if team_score > opp_score else "D"


def group_matches_by_season(matches):
    """Regroupe une liste de matchs par saison (récentes en premier)."""
    grouped = {}
    for m in matches:
        season_key = m.get("season") or "Unknown"
        grouped.setdefault(season_key, []).append(m)
    return grouped


# ===============================================================
# STATISTIQUES DE MATCH (structure Prism ESPN, avec fallbacks)
# ===============================================================

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


def extract_match_stats_prism(soup):
    """Extrait les statistiques du match depuis la structure Prism ESPN."""
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
        print(f"  ⚠️ Erreur stats prism : {e}")

    return stats


# ===============================================================
# MI-TEMPS / 2NDE MI-TEMPS
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
# VAINQUEUR AUX TIRS AU BUT
# ===============================================================

def extract_penalty_winner(soup, home_team_id, away_team_id):
    """
    Détecte le vainqueur d'un match décidé aux tirs au but via l'icône
    triangle affichée à côté du score gagnant.
    """
    try:
        icon = soup.find("svg", attrs={"data-icon": "arrows-triangleLeft"})
        if not icon:
            return None

        node = icon
        for _ in range(15):
            node = node.parent
            if node is None or not hasattr(node, "find_all"):
                break

            links = node.find_all("a", href=re.compile(r"/soccer/team/_/id/\d+/"))
            hrefs = {l.get("href", "") for l in links}

            has_home = any(f"/id/{home_team_id}/" in h for h in hrefs) if home_team_id else False
            has_away = any(f"/id/{away_team_id}/" in h for h in hrefs) if away_team_id else False

            if has_home and has_away:
                return None
            if has_home:
                return "home"
            if has_away:
                return "away"

        return None
    except Exception as e:
        print(f"  ⚠️ Erreur détection vainqueur tirs au but : {e}")
        return None


# ===============================================================
# COTES (Moneyline)
# ===============================================================

def us_to_decimal(val):
    """Convertit une cote américaine en cote décimale."""
    if not val:
        return None
    try:
        n = int(val.replace("+", "").strip())
        return round(1 + (n / 100), 2) if n > 0 else round(1 + (100 / abs(n)), 2)
    except Exception:
        return None


def extract_ml_odds(soup):
    """Extrait les cotes 1X2 (Moneyline) depuis la page du match."""
    try:
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
            except Exception:
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


# ===============================================================
# ROUND (numéro de round de coupe, séparé de matchday)
# ===============================================================

ROUND_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}


def normalize_round_label(round_text):
    """
    Convertit un libellé de round ESPN brut en nombre entier.
    """
    if not round_text:
        return None

    text = round_text.strip().lower()

    m = re.search(r"round of (\d+)", text)
    if m:
        return int(m.group(1))

    if "quarter-final" in text or "quarterfinal" in text:
        return 8
    if "semi-final" in text or "semifinal" in text:
        return 4
    if "winner" in text or "champion" in text:
        return 1
    if "final" in text:
        return 2

    m = re.search(
        r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+round",
        text,
    )
    if m:
        n = ROUND_ORDINALS.get(m.group(1))
        if n:
            return n

    return 0


def extract_round_info(soup):
    """Extrait le libellé "Compétition, Round" affiché sur la page du match."""
    try:
        el = soup.select_one("div.uUds.htRtm.pmgYE.WHJnO.qTCQv span")
        if not el:
            el = soup.select_one("div.uUds span")
        if el:
            return el.get_text(strip=True)
    except Exception as e:
        print(f"  ⚠️ Erreur extraction round : {e}")
    return None


def extract_round_label(round_text):
    """Isole et normalise la partie "round" d'un libellé complet."""
    if not round_text:
        return None
    parts = round_text.split(",")
    raw_label = parts[-1].strip() if parts else None
    return normalize_round_label(raw_label)


# ===============================================================
# BILAN D'ÉQUIPE (W-D-L) SUR LA PAGE DU MATCH — pour matchday à venir
# ===============================================================

def extract_team_games_played(soup, team_id):
    """
    Extrait, sur la page d'un match, le nombre de matchs déjà joués par
    une équipe (team_id) à partir de son bilan affiché "W-D-L" (ex:
    "0-0-0"), situé dans le bloc d'en-tête de l'équipe (sélecteur
    data-testid="prism-linkbase" pointant vers /soccer/team/_/id/{id}/).
    Retourne le nombre total de matchs (W+D+L), ou None si introuvable.
    """
    if not team_id:
        return None
    try:
        links = soup.find_all("a", href=re.compile(rf"/soccer/team/_/id/{team_id}/"))
        for link in links:
            node = link
            for _ in range(8):
                node = node.parent
                if node is None or not hasattr(node, "find_all"):
                    break
                for span in node.find_all("span"):
                    text = span.get_text(strip=True)
                    m = re.match(r"^(\d+)-(\d+)-(\d+)$", text)
                    if m:
                        w, d, l = (int(x) for x in m.groups())
                        return w + d + l
        return None
    except Exception as e:
        print(f"  ⚠️ Erreur extraction bilan équipe ({team_id}) : {e}")
        return None


def compute_upcoming_matchday(soup, home_team_id, away_team_id):
    """
    Calcule le matchday du prochain match de championnat : nombre de
    matchs déjà joués par chaque équipe (via son bilan W-D-L sur la
    page du match), puis matchday = max(des deux) + 1 — même logique
    "+1 au plus élevé" que pour l'historique des matchs déjà joués.
    Retourne None si ni l'une ni l'autre équipe n'a de bilan exploitable.
    """
    home_games = extract_team_games_played(soup, home_team_id)
    away_games = extract_team_games_played(soup, away_team_id)

    candidates = [g for g in (home_games, away_games) if g is not None]
    if not candidates:
        return None
    return max(candidates) + 1


def get_match_details_selenium(driver, game_id, home_team_id=None, away_team_id=None, decided_by_penalties=False):
    """
    Charge la page du match via Selenium et retourne
    (stats, odds, round_label, penalty_winner, has_full_stats).
    """
    url = f"https://www.espn.com/soccer/match/_/gameId/{game_id}"
    try:
        driver.get(url)
        WebDriverWait(driver, 12).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "section[data-testid='prism-LayoutCard']")
            )
        )
    except TimeoutException:
        pass
    except WebDriverException as e:
        print(f"    ⚠️  WebDriver erreur ({game_id}) : {e}")
        return {}, {"home": None, "away": None, "draw": None}, None, None, False

    soup = BeautifulSoup(driver.page_source, "html.parser")

    ml = extract_ml_odds(soup)
    odds = {
        "home": ml["home"] if ml else None,
        "away": ml["away"] if ml else None,
        "draw": ml["draw"] if ml else None,
    }

    round_label = extract_round_label(extract_round_info(soup))

    penalty_winner = None
    if decided_by_penalties:
        penalty_winner = extract_penalty_winner(soup, home_team_id, away_team_id)

    stats = extract_match_stats_prism(soup)
    if not stats:
        try:
            stats_section = driver.find_element(
                By.CSS_SELECTOR, "section[data-testid='prism-LayoutCard']"
            )
            rows = stats_section.find_elements(By.CSS_SELECTOR, "div.LOSQp")
            for row in rows:
                try:
                    name_tag = row.find_element(By.CSS_SELECTOR, "span.OkRBU")
                    values = row.find_elements(By.CSS_SELECTOR, "span.bLeWt")
                    if name_tag and len(values) >= 2:
                        stats[name_tag.text.strip()] = {
                            "home": values[0].text.strip(),
                            "away": values[1].text.strip(),
                        }
                except NoSuchElementException:
                    continue
            time.sleep(0.6)
        except NoSuchElementException:
            pass
        except Exception as e:
            print(f"    ⚠️  Erreur stats selenium ({game_id}) : {e}")

    has_full_stats = len(stats) > 0

    try:
        halftime, second_half = extract_match_timeline_halftime(soup)
        if halftime is not None:
            stats["Score 1ère mi-temps"] = {"home": halftime["home"], "away": halftime["away"]}
        if second_half is not None:
            stats["Score 2nde mi-temps"] = {"home": second_half["home"], "away": second_half["away"]}
    except Exception as e:
        print(f"    ⚠️  Erreur injection mi-temps ({game_id}) : {e}")

    stats = finalize_stats(stats)

    return stats, odds, round_label, penalty_winner, has_full_stats


def enrich_matches_with_stats_and_odds(driver, all_matches_by_team, only_match_ids=None):
    """
    Phase d'enrichissement : visite chaque match unique une seule fois
    pour récupérer stats, cotes, round et vainqueur aux pens.
    """
    game_meta = {}
    for matches in all_matches_by_team.values():
        for m in matches:
            gid = m.get("match_id")
            if not gid or gid in game_meta:
                continue
            if only_match_ids is not None and gid not in only_match_ids:
                continue
            game_meta[gid] = {
                "home_team_id": m.get("home_team_id"),
                "away_team_id": m.get("away_team_id"),
                "decided_by_penalties": m.get("decided_by_penalties", False),
            }

    unique_game_ids = list(game_meta.keys())
    total = len(unique_game_ids)
    print("\n" + "=" * 60)
    print(f"🔄 PHASE D'ENRICHISSEMENT — Statistiques, mi-temps, cotes, rounds & pens ({total} nouveau(x) match(s))")
    print("=" * 60)

    stats_by_game_id = {}
    odds_by_game_id = {}
    round_by_game_id = {}
    penalty_winner_by_game_id = {}
    has_full_stats_by_game_id = {}

    for idx, gid in enumerate(unique_game_ids, 1):
        meta = game_meta[gid]
        print(f"\n  [{idx}/{total}] gameId={gid}")
        try:
            stats, odds, round_label, penalty_winner, has_full_stats = get_match_details_selenium(
                driver, gid,
                home_team_id=meta["home_team_id"],
                away_team_id=meta["away_team_id"],
                decided_by_penalties=meta["decided_by_penalties"],
            )
        except Exception as e:
            print(f"    ⚠️ Erreur stats/cotes/round/pens gameId={gid}: {e}")
            stats = {}
            odds = {"home": None, "away": None, "draw": None}
            round_label = None
            penalty_winner = None
            has_full_stats = False

        stats_by_game_id[gid] = stats
        odds_by_game_id[gid] = odds
        round_by_game_id[gid] = round_label
        penalty_winner_by_game_id[gid] = penalty_winner
        has_full_stats_by_game_id[gid] = has_full_stats

        odds_str = (
            f"💰 {odds['home']}/{odds['draw']}/{odds['away']}"
            if odds.get("home") is not None
            else "ℹ️ pas de cotes"
        )
        round_str = f"🔁 round {round_label}" if round_label is not None else "🔁 pas de round"
        pens_str = f"🥅 pens: {penalty_winner}" if meta["decided_by_penalties"] else ""
        full_str = "✅ stats complètes" if has_full_stats else "⚠️ stats partielles"
        print(f"    📊 {len(stats)} statistique(s)  |  {full_str}  |  {odds_str}  |  {round_str}  {pens_str}")
        time.sleep(0.8)

    for matches in all_matches_by_team.values():
        for m in matches:
            gid = m.get("match_id")
            if not gid:
                continue
            if gid in stats_by_game_id:
                m["stats"] = stats_by_game_id[gid]
            if gid in odds_by_game_id:
                m["odds"] = odds_by_game_id[gid]
            if gid in has_full_stats_by_game_id:
                m["has_full_stats"] = has_full_stats_by_game_id[gid]
            if m.get("matchday") is None and round_by_game_id.get(gid) is not None:
                m["round"] = round_by_game_id[gid]
            if m.get("decided_by_penalties"):
                m["penalty_winner"] = penalty_winner_by_game_id.get(gid)

    print("\n  ✅ Injection des statistiques, mi-temps, cotes, rounds et tirs au but terminée")


# ===============================================================
# PROCHAIN MATCH — PAR MATCH (chaînage chronologique)
# ===============================================================

def build_next_game_from_match(next_match, team_id):
    """
    Construit l'objet next_game à partir d'un match déjà connu qui
    suit chronologiquement celui pour lequel on calcule next_game.
    """
    is_home = next_match.get("home_team_id") == team_id
    opponent = next_match.get("away_team") if is_home else next_match.get("home_team")
    opponent_id = next_match.get("away_team_id") if is_home else next_match.get("home_team_id")

    competition = next_match.get("competition")
    context = simplify_competition_label(competition)

    return {
        "context": context,
        "matchday": next_match.get("matchday"),
        "round": next_match.get("round"),
        "opponent": opponent,
        "opponent_id": opponent_id,
        "home_or_away": "home" if is_home else "away",
        "date": next_match.get("date"),
        "competition": competition,
        "match_url": next_match.get("match_url"),
        "game_id": next_match.get("match_id"),
    }


def extract_next_game_row(row):
    """
    Parse une ligne <tr> de la page fixtures ESPN, structure réelle :
      [0] Date (data-testid="date")
      [1] Équipe locale (data-testid="localTeam")
      [2] Score/match (data-testid="score", 3 <a>: logo, "v", logo)
      [3] Équipe away (data-testid="awayTeam")
      [4] Heure (<a> avec href gameId)
      [5] Compétition (<span>)
      [6] TV (vide)
    """
    cells = row.find_all("td")
    if len(cells) < 6:
        return None

    date_el = cells[0].select_one('[data-testid="date"]')
    date_text = date_el.get_text(strip=True) if date_el else None

    local_container = cells[1].select_one('[data-testid="localTeam"]') or cells[1]
    home_links = local_container.find_all("a")
    home_href = home_links[0].get("href") if home_links else ""
    home_id_m = re.search(r"/id/(\d+)/", home_href)
    home_team_id = home_id_m.group(1) if home_id_m else None
    home_team_name = team_name_from_href(home_href) if home_href else None

    away_container = cells[3].select_one('[data-testid="awayTeam"]') or cells[3]
    away_links = away_container.find_all("a")
    away_href = away_links[0].get("href") if away_links else ""
    away_id_m = re.search(r"/id/(\d+)/", away_href)
    away_team_id = away_id_m.group(1) if away_id_m else None
    away_team_name = team_name_from_href(away_href) if away_href else None

    match_url = None
    game_id = None
    score_container = cells[2].select_one('[data-testid="score"]') or cells[2]
    score_links = score_container.find_all("a")
    for link in score_links:
        href = link.get("href", "")
        if "/soccer/match/_/gameId/" in href:
            match_url = fix_url(href)
            gid_m = re.search(r"/gameId/(\d+)", match_url)
            game_id = gid_m.group(1) if gid_m else None
            break
    if not game_id:
        # Repli : colonne "TIME" (cells[4]) contient aussi un lien vers le match
        time_link = cells[4].find("a", href=re.compile(r"/soccer/match/_/gameId/\d+")) if len(cells) > 4 else None
        if time_link:
            match_url = fix_url(time_link.get("href"))
            gid_m = re.search(r"/gameId/(\d+)", match_url)
            game_id = gid_m.group(1) if gid_m else None

    competition = ""
    if len(cells) > 5:
        comp_span = cells[5].find("span")
        if comp_span:
            competition = comp_span.get_text(strip=True)

    return {
        "date": date_text,
        "home_team": home_team_name,
        "home_team_id": home_team_id,
        "away_team": away_team_name,
        "away_team_id": away_team_id,
        "competition": competition,
        "match_url": match_url,
        "match_id": game_id,
    }


def fetch_next_game_from_fixtures(driver, team_id, team_name, league_label):
    """
    Récupère le vrai prochain match à venir depuis la page fixtures
    ESPN, puis va chercher sur la page du match lui-même :
      - si championnat : le matchday, déduit du bilan W-D-L des deux
        équipes (max des deux + 1)
      - sinon (coupe) : le round, via le libellé "Compétition, Round"
    Retourne un dict au schéma next_game, ou None si indisponible.
    """
    slug = build_team_slug(team_name)
    url = f"https://www.espn.com/soccer/team/fixtures/_/id/{team_id}/{slug}"
    print(f"\n📅 Récupération du prochain match — {url}")

    try:
        driver.get(url)
        time.sleep(3)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.ResponsiveTable"))
        )
    except TimeoutException:
        print(f"    ⚠️ Timeout fixtures pour {team_name}")
    except Exception as e:
        print(f"    ⚠️ Erreur accès fixtures {team_name}: {e}")
        return None

    soup = BeautifulSoup(driver.page_source, "html.parser")

    tables = soup.select("div.ResponsiveTable")
    if not tables:
        print("    ⚠️ Aucune table de fixtures trouvée")
        return None

    row_info = None
    for table in tables:
        rows = table.select("tr.Table__TR")
        for r in rows:
            info = extract_next_game_row(r)
            if info and (info.get("home_team_id") or info.get("away_team_id")):
                row_info = info
                break
        if row_info:
            break

    if not row_info:
        print("    ⚠️ Aucune ligne de prochain match exploitable")
        return None

    competition = row_info.get("competition") or ""
    is_league_match = league_label.lower() in competition.lower()

    matchday = None
    round_val = None

    if row_info.get("match_id"):
        try:
            driver.get(f"https://www.espn.com/soccer/match/_/gameId/{row_info['match_id']}")
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(1)
            match_soup = BeautifulSoup(driver.page_source, "html.parser")

            if is_league_match:
                matchday = compute_upcoming_matchday(
                    match_soup, row_info.get("home_team_id"), row_info.get("away_team_id")
                )
                print(f"    ✅ Prochain match (championnat) — matchday calculé (bilan W-D-L +1): {matchday}")
            else:
                round_val = extract_round_label(extract_round_info(match_soup))
                print(f"    ✅ Prochain match (coupe) — round: {round_val}")
        except Exception as e:
            print(f"    ⚠️ Erreur récupération matchday/round prochain match : {e}")
    else:
        print("    ⚠️ Aucun gameId identifiable pour le prochain match")

    is_home = row_info.get("home_team_id") == team_id
    opponent = row_info.get("away_team") if is_home else row_info.get("home_team")
    opponent_id = row_info.get("away_team_id") if is_home else row_info.get("home_team_id")

    return {
        "context": simplify_competition_label(competition) or None,
        "matchday": matchday,
        "round": round_val,
        "opponent": opponent,
        "opponent_id": opponent_id,
        "home_or_away": "home" if is_home else "away",
        "date": row_info.get("date"),
        "competition": competition or None,
        "match_url": row_info.get("match_url"),
        "game_id": row_info.get("match_id"),
    }


def apply_next_game_chain(driver, matches, team_id, team_name, league_label):
    """
    Pour chaque match de l'équipe (triés chronologiquement), injecte
    dans son champ "next_game" les infos du match immédiatement
    suivant (chronologique). Pour le tout dernier match connu, le
    "prochain match" est le futur match réel, récupéré depuis la page
    fixtures ESPN (avec matchday/round calculé sur la page du match).
    """
    matches_asc = sorted(matches, key=date_sort_key)

    for i in range(len(matches_asc) - 1):
        current = matches_asc[i]
        following = matches_asc[i + 1]
        current["next_game"] = build_next_game_from_match(following, team_id)

    if matches_asc:
        most_recent = matches_asc[-1]
        most_recent["next_game"] = fetch_next_game_from_fixtures(driver, team_id, team_name, league_label)

    return matches_asc


# ===============================================================
# SORTIE JSON — ordre des clés propre et lisible
# ===============================================================

MATCH_KEY_ORDER = [
    "date", "season", "matchday", "round", "competition",
    "home_team", "home_team_id", "home_logo_url", "home_score",
    "away_team", "away_team_id", "away_logo_url", "away_score",
    "result", "decided_by_penalties", "penalty_winner", "team_result",
    "odds", "has_full_stats", "stats", "next_game", "match_id", "match_url",
]

TEAM_KEY_ORDER = [
    "team_name", "team_id", "logo", "league_id", "league_name",
    "country", "total_matches", "scraped_at", "matches_by_season",
]


def clean_match(m):
    """Réordonne les clés d'un match selon MATCH_KEY_ORDER."""
    return {k: m.get(k) for k in MATCH_KEY_ORDER}


def clean_team_output(team_output):
    """Réordonne les clés d'une équipe selon TEAM_KEY_ORDER."""
    cleaned = {k: team_output.get(k) for k in TEAM_KEY_ORDER}
    cleaned["matches_by_season"] = {
        season: [clean_match(m) for m in season_matches]
        for season, season_matches in cleaned["matches_by_season"].items()
    }
    return cleaned


def build_leagues_processed_from_output(output_data):
    """
    Reconstruit "leagues_processed" à partir des équipes réellement
    présentes dans output_data (cumul de tous les runs GitHub Actions),
    au lieu de se limiter à "selected_leagues" (la plage
    LEAGUE_INDEX_START/END du run courant uniquement).

    Avant ce correctif, "leagues_processed" ne listait que la ligue
    traitée lors du dernier run, alors que "teams" contenait
    l'historique cumulé de plusieurs ligues différentes — d'où
    l'incohérence entre les deux champs. Ici, la liste est dérivée
    directement des couples (country, league_name) réellement présents
    dans les équipes, donc toujours synchronisée avec "teams".
    """
    leagues_seen = {}
    for team_entry in output_data:
        key = (team_entry.get("country"), team_entry.get("league_name"))
        if all(key) and key not in leagues_seen:
            leagues_seen[key] = {
                "country": team_entry.get("country"),
                "league_name": team_entry.get("league_name"),
            }
    return sorted(leagues_seen.values(), key=lambda lg: (lg["country"], lg["league_name"]))


def scrape_with_selenium():
    driver = None

    try:
        data = fetch_teams_json()

        all_leagues = list_all_leagues(data)
        print(f"\n📚 {len(all_leagues)} ligue(s) disponible(s) au total :")
        for i, lg in enumerate(all_leagues, 1):
            print(f"   [{i}] {lg['country']} — {lg['league_name']}")

        selected_leagues = select_leagues_by_range(all_leagues, LEAGUE_INDEX_START, LEAGUE_INDEX_END)
        if not selected_leagues:
            print(f"❌ Aucune ligue sélectionnée pour la plage [{LEAGUE_INDEX_START}, {LEAGUE_INDEX_END}].")
            return []

        print(f"\n✅ Plage sélectionnée [{LEAGUE_INDEX_START}, {LEAGUE_INDEX_END}] → {len(selected_leagues)} ligue(s) :")
        for lg in selected_leagues:
            print(f"   - {lg['country']} — {lg['league_name']}")

        existing_teams_by_id = load_existing_data()

        print("\n🚀 Démarrage du navigateur (headless)...")
        driver = setup_driver()
        print("✅ Navigateur démarré")

        matches_by_team = {}
        team_meta = {}
        new_match_ids_global = set()

        # ── Boucle sur chaque ligue sélectionnée, puis chaque équipe de la ligue ──
        for league in selected_leagues:
            league_country = league["country"]
            league_name = league["league_name"]
            league_label = target_league_label(league_name, league_country)

            print("\n" + "#" * 60)
            print(f"🏆 LIGUE: {league_country} — {league_name} (libellé ESPN: {league_label})")
            print("#" * 60)

            teams = fetch_teams_for_league(data, league_country, league_name)
            if not teams:
                print(f"⚠️ Aucune équipe trouvée pour {league_name}, ligue ignorée.")
                continue

            for team in teams:
                team_name = team.get("team", "")
                team_id = team.get("team_id", "")

                existing_entry = existing_teams_by_id.get(team_id)
                is_tracked = existing_entry is not None

                print("\n" + "=" * 60)
                print(f"⚽ ÉQUIPE: {team_name} (id={team_id}) — {league_name}")
                if is_tracked:
                    print(f"🔁 Équipe déjà trackée — mise à jour saison en cours uniquement ({format_season(END_SEASON)})")
                    seasons_to_scrape = [END_SEASON]
                else:
                    print(f"🆕 Équipe jamais trackée — scraping complet depuis {format_season(START_SEASON)}")
                    seasons_to_scrape = list(range(START_SEASON, END_SEASON + 1))
                print("=" * 60)

                newly_scraped = scrape_team_results_for_seasons(driver, team_name, team_id, seasons_to_scrape)
                newly_scraped = compute_matchdays_for_team(newly_scraped, league_label)

                existing_matches_flat = flatten_existing_matches(existing_entry) if is_tracked else []

                merged_matches, new_match_ids = merge_matches(existing_matches_flat, newly_scraped)
                merged_matches.sort(key=date_sort_key, reverse=True)

                print(f"\n📦 {team_name}: {len(merged_matches)} match(s) au total, {len(new_match_ids)} nouveau(x)")

                matches_by_team[team_id] = merged_matches
                # On mémorise le pays/la ligue avec l'équipe pour la suite du traitement
                team_meta[team_id] = {**team, "_league_country": league_country, "_league_label": league_label}
                new_match_ids_global |= new_match_ids

        if new_match_ids_global:
            enrich_matches_with_stats_and_odds(driver, matches_by_team, only_match_ids=new_match_ids_global)
        else:
            print("\nℹ️ Aucun nouveau match à enrichir")

        newly_processed_by_id = {}

        for team_id, unique_matches in matches_by_team.items():
            team = team_meta[team_id]
            team_name = team.get("team", "")
            team_country = team.get("_league_country", "")
            league_label = team.get("_league_label", "")

            for m in unique_matches:
                m["team_result"] = compute_team_result(m, team_id)

            # ── Chaînage next_game (match suivant chronologique par match) ──
            unique_matches = apply_next_game_chain(driver, unique_matches, team_id, team_name, league_label)
            unique_matches.sort(key=date_sort_key, reverse=True)

            team_output = {
                "team_name": team_name,
                "team_id": team_id,
                "logo": team.get("logo", build_logo_url(team_id)),
                "league_id": team.get("league_id", ""),
                "league_name": team.get("league_name", ""),
                "country": team_country,
                "total_matches": len(unique_matches),
                "scraped_at": datetime.now().isoformat(),
                "matches_by_season": group_matches_by_season(unique_matches),
            }

            newly_processed_by_id[team_id] = clean_team_output(team_output)

            competitions = {}
            for m in unique_matches:
                competitions[m["competition"]] = competitions.get(m["competition"], 0) + 1
            print(f"\n📊 Statistiques par compétition ({team_name}):")
            for comp, count in sorted(competitions.items(), key=lambda x: x[1], reverse=True):
                print(f"   {comp}: {count} match(s)")

        # ── Fusion avec les équipes déjà trackées non retraitées cette exécution ──
        final_teams_by_id = dict(existing_teams_by_id)
        final_teams_by_id.update(newly_processed_by_id)
        output_data = list(final_teams_by_id.values())

        # ── leagues_processed est désormais dérivé des équipes réellement
        # présentes dans output_data (cumul de tous les runs), et non plus
        # de "selected_leagues" (plage du run courant uniquement). Corrige
        # l'incohérence où le champ ne listait qu'une seule ligue alors que
        # "teams" en contenait plusieurs.
        leagues_processed_all = build_leagues_processed_from_output(output_data)

        final_output = {
            "leagues_processed": leagues_processed_all,
            "nb_teams": len(output_data),
            "scraped_at": datetime.now().isoformat(),
            "teams": output_data,
        }

        with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(
                final_output,
                f,
                ensure_ascii=False,
                indent=2,
                separators=(",", ": "),
            )

        print(f"\n💾 {OUTPUT_JSON_PATH} sauvegardé ({len(output_data)} équipe(s) au total)")

        return list(newly_processed_by_id.values())

    except Exception as e:
        print(f"❌ Erreur globale: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if driver:
            print("\n🧹 Fermeture du navigateur…")
            driver.quit()


def main():
    print("=" * 60)
    print("⚽ ESPN SCRAPER — TRACKING INCRÉMENTAL (PLAGE DE LIGUES)")
    print(f"📆 Plage de ligues sélectionnée: [{LEAGUE_INDEX_START}, {LEAGUE_INDEX_END}]")
    print("📆 Scraping complet si jamais trackée, sinon mise à jour saison en cours + next_game chaîné par match")
    print("=" * 60)

    reset_output_directories()

    results = scrape_with_selenium()

    if results:
        total_matches = sum(t["total_matches"] for t in results)
        print(f"\n✅ {len(results)} équipe(s) traitée(s) cette exécution, {total_matches} match(s) au total")

        for team_output in results:
            print(f"\n📋 {team_output['team_name']} — {team_output['total_matches']} matchs")
            for season_key, season_matches in team_output["matches_by_season"].items():
                print(f"\n  📆 Saison {season_key} — {len(season_matches)} match(s)")
                for i, m in enumerate(season_matches[:3]):
                    ng = m.get("next_game")
                    ng_str = (
                        f"→ prochain: {ng.get('opponent')} ({ng.get('home_or_away')}) "
                        f"[{ng.get('context')} — MD/R {ng.get('matchday') or ng.get('round')}]"
                        if ng else "→ prochain: -"
                    )
                    print(
                        f"    {i+1}. [{m['date']}] "
                        f"{m['home_team']} {m['home_score']}-{m['away_score']} {m['away_team']}  "
                        f"({m['team_result']})  {ng_str}"
                    )
    else:
        print("\n❌ Aucune donnée récupérée")


if __name__ == "__main__":
    main()