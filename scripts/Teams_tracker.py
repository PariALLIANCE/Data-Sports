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
TARGET_COUNTRY = "England"
TARGET_LEAGUE = "England_Premier_League"
NB_TEAMS = 1  # ← une seule équipe désormais

START_SEASON = 2023
END_SEASON = datetime.now().year  # saison actuelle incluse

# ── Chemins de sortie / nettoyage ───────────────────────────────
LEAGUES_DIR = os.path.join("data", "football", "leagues")
DATASET_TMP_DIR = "dataset_tmp"
OUTPUT_JSON_PATH = os.path.join(LEAGUES_DIR, "data_teams.json")


def reset_output_directories():
    """
    Supprime puis recrée le dossier data/football/leagues (destination
    finale du JSON), et supprime le dossier dataset_tmp s'il existe
    (nettoyage des fichiers temporaires d'une exécution précédente).
    """
    # ── Suppression + recréation de data/football/leagues ──────────
    if os.path.isdir(LEAGUES_DIR):
        print(f"🗑️  Suppression du dossier existant: {LEAGUES_DIR}")
        shutil.rmtree(LEAGUES_DIR)
    os.makedirs(LEAGUES_DIR, exist_ok=True)
    print(f"📁 Dossier recréé: {LEAGUES_DIR}")

    # ── Suppression de dataset_tmp ──────────────────────────────────
    if os.path.isdir(DATASET_TMP_DIR):
        print(f"🗑️  Suppression du dossier temporaire: {DATASET_TMP_DIR}")
        shutil.rmtree(DATASET_TMP_DIR)
    else:
        print(f"ℹ️  Aucun dossier temporaire {DATASET_TMP_DIR} à supprimer")


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


# ── Acronymes de clubs à mettre en majuscules (compatibilité de noms) ──
KNOWN_TEAM_ACRONYMS = {
    "afc", "fc", "cf", "fk", "sc", "ac", "ca", "cd", "us", "as",
    "ud", "sv", "vfb", "vfl", "tsv", "bsc", "rc", "rcd", "cfc",
}


def normalize_team_name(name):
    """
    Met en majuscules les acronymes connus au sein d'un nom d'équipe,
    pour assurer la compatibilité avec les libellés officiels (ex:
    "Afc Bournemouth" → "AFC Bournemouth", "Fc Barcelona" → "FC Barcelona").
    Les autres mots conservent leur casse Title (déjà appliquée en amont).
    """
    if not name:
        return name
    words = name.split(" ")
    normalized_words = [
        w.upper() if w.lower() in KNOWN_TEAM_ACRONYMS else w
        for w in words
    ]
    return " ".join(normalized_words)


def team_name_from_href(href):
    """Extrait le nom lisible depuis l'URL de l'équipe ESPN.
    Ex: /soccer/team/_/id/6086/botafogo → Botafogo
    Ex: /soccer/team/_/id/349/afc-bournemouth → AFC Bournemouth
    """
    if not href:
        return ""
    slug = href.rstrip("/").split("/")[-1]
    raw_name = slug.replace("-", " ").title()
    return normalize_team_name(raw_name)


def build_logo_url(team_id):
    """Construit l'URL du logo ESPN à partir de l'ID d'équipe."""
    if not team_id:
        return ""
    return f"https://a.espncdn.com/i/teamlogos/soccer/500/{team_id}.png"


def fetch_target_teams():
    """
    Récupère le fichier football_teams.json depuis GitHub, et retourne
    la (les) NB_TEAMS première(s) équipe(s) de TARGET_COUNTRY / TARGET_LEAGUE.
    """
    print(f"🌐 Téléchargement de {TEAMS_JSON_URL}")
    req = urllib.request.Request(TEAMS_JSON_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    country_teams = data.get(TARGET_COUNTRY, [])
    league_teams = [t for t in country_teams if t.get("league_name") == TARGET_LEAGUE]

    selected = league_teams[:NB_TEAMS]

    print(f"📋 {len(league_teams)} équipe(s) trouvée(s) pour {TARGET_LEAGUE}")
    print(f"✅ {len(selected)} équipe(s) sélectionnée(s):")
    for t in selected:
        print(f"   - {t['team']} (id={t['team_id']})")

    return selected


MONTH_ORDER = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


def format_season(season):
    """
    Convertit une saison ESPN (année de départ, ex: 2022) en libellé
    "YYYY/YYYY+1". Ex: 2022 → "2022/2023", 2025 → "2025/2026".
    """
    season = int(season)
    return f"{season}/{season + 1}"


def target_league_label():
    """
    Dérive le libellé de compétition ESPN correspondant à TARGET_LEAGUE
    (ex: "England_Premier_League" → "Premier League"). Utilisé pour
    repérer les matchs de championnat lors du calcul de la journée.
    """
    parts = TARGET_LEAGUE.split("_")
    if len(parts) > 1 and parts[0] == TARGET_COUNTRY:
        parts = parts[1:]
    return " ".join(parts)


def build_iso_date(date_text, month_text, year_str):
    """
    Construit une date ISO (YYYY-MM-DD) à partir des champs bruts ESPN :
    - date_text  : texte du jour (contient le numéro du jour du mois)
    - month_text : texte du bloc mensuel (ex. "August, 2022"), utilisé
      pour déterminer le mois
    - year_str   : année réelle du match (déjà résolue en amont)
    Retourne None si la date ne peut pas être reconstituée.
    """
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
    """
    Clé de tri chronologique basée sur le champ "date" ISO (YYYY-MM-DD).
    Retourne (0, 0, 0) si la date est absente ou invalide.
    """
    d = m.get("date")
    if not d:
        return (0, 0, 0)
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        return (dt.year, dt.month, dt.day)
    except (ValueError, TypeError):
        return (0, 0, 0)


def extract_match_info(match_row, month, season):
    """
    Structure réelle ESPN (6 <td>) :
      [0] Date   → <div data-testid="date">
      [1] Équipe locale  → <div data-testid="localTeam"><a href="/soccer/team/_/id/ID/slug">
      [2] Score + logos  → <span data-testid="score">
                              <a href="/soccer/match/_/gameId/ID/...">X - Y</a>
                           </span>
      [3] Équipe away    → <div data-testid="awayTeam"><a href="/soccer/team/_/id/ID/slug">
      [4] Résultat       → <span data-testid="result"><a>FT</a>
      [5] Compétition    → <span>...</span>

    `season` correspond à la saison interrogée sur ESPN (paramètre d'URL),
    utilisée comme valeur de repli si l'année n'est pas détectable dans le texte.
    """
    try:
        cells = match_row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 6:
            return None

        # ── [0] DATE ──────────────────────────────────────────────────
        date_els = cells[0].find_elements(By.CSS_SELECTOR, '[data-testid="date"]')
        date = date_els[0].text.strip() if date_els else ""

        # ── [1] ÉQUIPE LOCALE ─────────────────────────────────────────
        local_links = cells[1].find_elements(By.TAG_NAME, "a")
        if not local_links:
            return None
        local_href = local_links[0].get_attribute("href") or ""
        local_id_m = re.search(r"/id/(\d+)/", local_href)
        local_team_id = local_id_m.group(1) if local_id_m else ""
        local_team_name = team_name_from_href(local_href)

        # ── [2] SCORE ─────────────────────────────────────────────────
        score_links = cells[2].find_elements(By.TAG_NAME, "a")

        home_score_raw = ""
        away_score_raw = ""
        match_url = ""
        match_id = ""

        # score_links[0] = lien logo local, [1] = lien score/match, [2] = lien logo away
        if len(score_links) >= 3:
            score_text = score_links[1].text.strip()
            match_url = fix_url(score_links[1].get_attribute("href") or "")
            mid_m = re.search(r"/gameId/(\d+)", match_url)
            match_id = mid_m.group(1) if mid_m else ""

            score_m = re.search(r"(\d+)\s*[-:]\s*(\d+)", score_text)
            if score_m:
                home_score_raw = score_m.group(1)
                away_score_raw = score_m.group(2)

        # ── [3] ÉQUIPE AWAY ───────────────────────────────────────────
        away_links = cells[3].find_elements(By.TAG_NAME, "a")
        if not away_links:
            return None
        away_href = away_links[0].get_attribute("href") or ""
        away_id_m = re.search(r"/id/(\d+)/", away_href)
        away_team_id = away_id_m.group(1) if away_id_m else ""
        away_team_name = team_name_from_href(away_href)

        # ── [4] RÉSULTAT ──────────────────────────────────────────────
        # On garde le libellé brut ESPN tel quel ("FT" ou "FT-Pens").
        result_raw = ""
        result_els = cells[4].find_elements(By.CSS_SELECTOR, '[data-testid="result"]')
        if result_els:
            result_raw = result_els[0].text.strip()
        else:
            result_links = cells[4].find_elements(By.TAG_NAME, "a")
            if result_links:
                result_raw = result_links[0].text.strip()

        # ── DÉTECTION TIRS AU BUT (à partir du même libellé brut) ───
        decided_by_penalties = bool(re.search(r"pens", result_raw, re.IGNORECASE))

        # ── [5] COMPÉTITION ───────────────────────────────────────────
        competition = ""
        comp_spans = cells[5].find_elements(By.TAG_NAME, "span")
        if comp_spans:
            competition = comp_spans[-1].text.strip()

        # ── ANNÉE RÉELLE DU MATCH ────────────────────────────────────
        # Le bloc "month" ressemble parfois à "August, 2022". On essaie d'en
        # extraire l'année réelle, sinon on retombe sur la saison interrogée.
        year_m = re.search(r"(\d{4})", month)
        match_year = year_m.group(1) if year_m else str(season)

        # ── DATE ISO ────────────────────────────────────────────────
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
            "result": result_raw,  # ← garde "FT" ou "FT-Pens" tel quel
            "decided_by_penalties": decided_by_penalties,
            "penalty_winner": None,  # ← rempli lors de l'enrichissement si decided_by_penalties
            "team_result": None,     # ← rempli plus tard (V/N/D du point de vue de l'équipe scrapée)
            "competition": competition,
            "season": format_season(season),
            "matchday": None,  # ← journée de championnat uniquement (None pour les coupes)
            "round": None,     # ← round de coupe uniquement (None pour le championnat)
            "odds": {"home": None, "away": None, "draw": None},  # ← rempli lors de l'enrichissement
            "has_full_stats": False,  # ← rempli lors de l'enrichissement
            "stats": {},  # ← rempli plus tard lors de la phase d'enrichissement
        }

    except Exception as e:
        print(f"⚠️ Erreur extraction: {str(e)[:120]}")
        return None


def scrape_team_results_for_season(driver, team_name, team_id, season):
    """
    Scrape les résultats d'une équipe ESPN donnée (team_id) pour UNE saison.
    Retourne la liste des matchs (non dédupliqués entre saisons).
    """
    all_matches = []

    url = f"https://www.espn.com/soccer/team/results/_/id/{team_id}/season/{season}"
    print(f"\n🌐 Accès: {url}")
    driver.get(url)

    print("⏳ Attente du chargement initial (5s)...")
    time.sleep(5)

    # Scroll pour déclencher le lazy-load
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

    # ── Récupérer tous les blocs mensuels ─────────────────────────
    result_tables = driver.find_elements(
        By.CSS_SELECTOR, "div.ResponsiveTable.Table__results-mobile"
    )

    if not result_tables:
        result_tables = driver.find_elements(By.CSS_SELECTOR, "div.ResponsiveTable")

    print(f"📊 {len(result_tables)} bloc(s) mensuel(s) trouvé(s) pour la saison {season}")

    if not result_tables:
        print(f"❌ Aucun tableau trouvé pour la saison {season}.")
        return []

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
                all_matches.append(match_data)
                print(
                    f"   ✅ {match_data['home_team']} {match_data['home_score']}"
                    f" - {match_data['away_score']} {match_data['away_team']}"
                    f"  [{match_data['competition']}]"
                )
            else:
                print("   ⚠️ Ligne ignorée (extraction échouée)")

    return all_matches


def compute_matchdays_for_team(matches):
    """
    Calcule la journée (matchday) de championnat pour chaque match d'une
    équipe, en se basant sur l'ordre chronologique croissant (via
    date_sort_key) des matchs de championnat (compétition == ligue
    ciblée), saison par saison. Les matchs hors championnat (coupes,
    C1, etc.) gardent matchday = None : leur numéro de round sera
    renseigné séparément dans le champ "round" lors de l'enrichissement.
    """
    league_label = target_league_label().lower()

    matches_asc = sorted(matches, key=date_sort_key)

    counters = {}  # saison (ex: "2022/2023") → compteur de journées
    for m in matches_asc:
        season_key = m.get("season")
        competition = (m.get("competition") or "").lower()
        if league_label in competition:
            counters[season_key] = counters.get(season_key, 0) + 1
            m["matchday"] = counters[season_key]
        else:
            m["matchday"] = None

    return matches


def compute_team_result(match, team_id):
    """
    Détermine le résultat du match ("V", "N", "D") du point de vue de
    l'équipe team_id (celle dont on scrape les résultats). Si le score
    est à égalité mais que le match a été décidé aux tirs au but, le
    résultat retenu suit le vainqueur des penalties (V ou D) plutôt
    qu'un match nul.
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


def scrape_team_results_all_seasons(driver, team_name, team_id):
    """
    Scrape les résultats d'une équipe ESPN pour toutes les saisons de
    START_SEASON à END_SEASON, déduplique sur l'ensemble des saisons,
    trie du plus récent au plus ancien, puis calcule la journée de
    championnat de chaque match.
    """
    combined_matches = []

    for season in range(START_SEASON, END_SEASON + 1):
        print(f"\n📆 Saison {season} — {team_name}")
        try:
            season_matches = scrape_team_results_for_season(driver, team_name, team_id, season)
        except Exception as e:
            print(f"❌ Erreur lors du scraping de {team_name} (saison {season}): {e}")
            import traceback
            traceback.print_exc()
            season_matches = []

        combined_matches.extend(season_matches)

    # ── Dédoublonnage sur l'ensemble des saisons ───────────────────
    seen = set()
    unique_matches = []
    for m in combined_matches:
        key = m["match_id"] if m["match_id"] else f"{m['home_team']}_{m['away_team']}_{m['date']}"
        if key not in seen:
            seen.add(key)
            unique_matches.append(m)

    print(
        f"\n✅ {len(unique_matches)} matchs uniques pour {team_name} "
        f"(sur {len(combined_matches)} extraits, saisons {format_season(START_SEASON)}-{format_season(END_SEASON)})"
    )

    # ── Tri : du plus récent au plus ancien ─────────────────────────
    unique_matches.sort(key=date_sort_key, reverse=True)

    # ── Calcul des journées de championnat (matchday) ──────────────
    unique_matches = compute_matchdays_for_team(unique_matches)

    return unique_matches


def group_matches_by_season(matches):
    """
    Regroupe une liste de matchs (déjà triée du plus récent au plus
    ancien) par saison, sous forme de dict ordonné :
      {"2024/2025": [...matchs...], "2023/2024": [...matchs...]}
    Les saisons les plus récentes apparaissent en premier (l'ordre
    d'insertion suit l'ordre de la liste d'entrée), et les matchs de
    chaque saison conservent leur tri du plus récent au plus ancien.
    """
    grouped = {}
    for m in matches:
        season_key = m.get("season") or "Unknown"
        grouped.setdefault(season_key, []).append(m)
    return grouped


# ===============================================================
# STATISTIQUES DE MATCH (structure Prism ESPN, avec fallbacks)
# ===============================================================

def to_int_stat(value):
    """
    Convertit une valeur de statistique brute en entier lorsque cela
    est possible : gère les nombres simples ("12" → 12), les
    pourcentages ("55%" → 55), et les espaces parasites. Toute valeur
    qui n'est pas purement numérique (ex: ratios "5 of 12", horaires,
    textes libres) est retournée inchangée (str).
    """
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace(",", "").strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    # Valeurs décimales éventuelles (rares en stats de match) → arrondi entier
    if re.fullmatch(r"-?\d+\.\d+", text):
        return int(round(float(text)))
    return value


def finalize_stats(stats):
    """
    Passe finale de nettoyage sur le dict de statistiques d'un match :
    convertit systématiquement chaque valeur "home"/"away" en int via
    to_int_stat, quel que soit le libellé de la statistique.
    """
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
    """
    Extrait les statistiques du match depuis la nouvelle structure
    Prism d'ESPN (section data-testid="prism-LayoutCard" contenant "stat"
    dans son titre h2).
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
        print(f"  ⚠️ Erreur stats prism : {e}")

    return stats


def extract_match_stats(soup):
    """
    Extrait les statistiques du match avec plusieurs méthodes de repli,
    pour couvrir les différentes versions de l'UI ESPN.
    """
    # Méthode 1 : nouvelle UI Prism
    stats = extract_match_stats_prism(soup)
    if stats:
        return stats

    # Méthode 2 : StatCellContent (ancienne UI)
    try:
        stat_rows = soup.select("div.StatCellContent")
        if stat_rows:
            values = [el.get_text(strip=True) for el in stat_rows]
            i = 0
            while i + 2 < len(values):
                home_val = values[i]
                label = values[i + 1]
                away_val = values[i + 2]
                if label and not label.replace(" ", "").isdigit():
                    stats[label] = {"home": home_val, "away": away_val}
                    i += 3
                else:
                    i += 1
            if stats:
                return stats
    except Exception:
        pass

    # Méthode 3 : GameStat
    try:
        game_stat_rows = soup.select("div.GameStat")
        if game_stat_rows:
            for row in game_stat_rows:
                cols = row.select("div")
                texts = [c.get_text(strip=True) for c in cols if c.get_text(strip=True)]
                if len(texts) >= 3:
                    stats[texts[1]] = {"home": texts[0], "away": texts[2]}
            if stats:
                return stats
    except Exception:
        pass

    return {}


# ===============================================================
# MI-TEMPS / 2NDE MI-TEMPS (structure "Match Timeline" Prism ESPN)
# ===============================================================

def extract_match_timeline_halftime(soup):
    """
    Extrait le score à la mi-temps et à la 2nde mi-temps depuis la
    section "Match Timeline" de la page match ESPN, en comptant les
    icônes de but ("soccer-goal02") positionnées sur la frise
    chronologique, avant/après le marqueur "HT" (mi-temps), pour
    l'équipe locale (1re ligne d'icônes) et l'équipe visiteuse (2e
    ligne d'icônes).

    Retourne un tuple (halftime, second_half), chacun un dict
    {"home": int, "away": int} représentant le nombre de buts marqués
    pendant cette période, ou (None, None) si la frise est absente ou
    n'a pas pu être interprétée.
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

        # ── Repérage du marqueur "HT" sur la frise ──────────────────
        ht_percent = None
        for span in section.find_all("span"):
            if span.get_text(strip=True).upper() == "HT":
                style = span.get("style", "")
                m = re.search(r"left:\s*([\d.]+)%", style)
                if m:
                    ht_percent = float(m.group(1))
                break
        if ht_percent is None:
            ht_percent = 50.0  # repli raisonnable si le marqueur est introuvable

        # ── Repérage des deux lignes d'icônes (locale puis visiteuse) ──
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

        halftime = {"home": home_ht, "away": away_ht}
        second_half = {"home": home_2h, "away": away_2h}
        return halftime, second_half

    except Exception as e:
        print(f"  ⚠️ Erreur extraction mi-temps (timeline) : {e}")
        return None, None


# ===============================================================
# VAINQUEUR AUX TIRS AU BUT (icône triangle à côté du score)
# ===============================================================

def extract_penalty_winner(soup, home_team_id, away_team_id):
    """
    Détecte le vainqueur d'un match décidé aux tirs au but ("-Pens") en
    repérant la petite icône triangle ("arrows-triangleLeft") affichée
    à côté du score de l'équipe gagnante sur la page du match.

    Remonte depuis l'icône jusqu'au plus petit ancêtre contenant un
    lien vers UNE SEULE des deux équipes (home ou away) ; si l'ancêtre
    contient les deux (portée trop large / ambiguë), la détection est
    abandonnée plutôt que de risquer une mauvaise attribution.

    Retourne "home", "away" ou None si l'icône ou l'équipe associée
    n'a pas pu être identifiée avec certitude.
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
                return None  # portée ambiguë, on ne devine pas
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
    """
    Convertit une cote américaine (ex: "-150", "+120") en cote décimale.
    """
    if not val:
        return None
    try:
        n = int(val.replace("+", "").strip())
        return round(1 + (n / 100), 2) if n > 0 else round(1 + (100 / abs(n)), 2)
    except Exception:
        return None


def extract_ml_odds(soup):
    """
    Extrait les cotes 1X2 (Moneyline) depuis la page du match, si elles
    sont disponibles (généralement absentes pour les matchs déjà joués
    depuis longtemps).
    """
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
    Convertit un libellé de round ESPN brut en nombre entier, selon le
    mapping demandé :
      "Round of 32"                → 32
      "Round of 16"                 → 16
      "Quarter-finals" / "Quarterfinals" → 8
      "Semi-finals" / "Semifinals"          → 4
      "Final"                                → 2
      "Winner" / "Champion"                    → 1
      "Third Round", "Fourth Round",
      "Fifth Round"... ("Nth Round")             → N
      libellé non reconnu                          → 0

    Retourne None si round_text est vide.
    """
    if not round_text:
        return None

    text = round_text.strip().lower()

    # "Round of N" → N
    m = re.search(r"round of (\d+)", text)
    if m:
        return int(m.group(1))

    # Étapes à élimination directe nommées (avec ou sans trait d'union)
    if "quarter-final" in text or "quarterfinal" in text:
        return 8
    if "semi-final" in text or "semifinal" in text:
        return 4
    if "winner" in text or "champion" in text:
        return 1
    if "final" in text:
        return 2

    # "Nth Round" (ex: "Third Round", "Fifth Round") → N
    m = re.search(
        r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+round",
        text,
    )
    if m:
        n = ROUND_ORDINALS.get(m.group(1))
        if n:
            return n

    # Repli générique pour tout libellé non reconnu (playoffs, poules, etc.)
    return 0


def extract_round_info(soup):
    """
    Extrait le libellé "Compétition, Round" affiché sur la page du match
    (ex: "Copa Do Brazil, Fifth Round"), utilisé pour renseigner le
    numéro de round des matchs qui ne font pas partie du championnat
    ciblé (coupes, compétitions continentales, etc.).
    """
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
    """
    Isole la partie "round" du libellé complet (ex: "Copa Do Brazil,
    Fifth Round" → "Fifth Round"), puis la normalise en nombre entier
    via normalize_round_label (ex: "Fifth Round" → 5,
    "Round of 32" → 32, "Final" → 2). Retourne None si absent.
    """
    if not round_text:
        return None
    parts = round_text.split(",")
    raw_label = parts[-1].strip() if parts else None
    return normalize_round_label(raw_label)


def get_match_details_selenium(driver, game_id, home_team_id=None, away_team_id=None, decided_by_penalties=False):
    """
    Charge la page du match via Selenium (gameId) et retourne un tuple
    (stats, odds, round_label, penalty_winner, has_full_stats) :
      - stats           : dict des statistiques du match (Prism en
        priorité, fallback CSS sinon), toutes les valeurs numériques
        converties en int, incluant les scores de mi-temps
      - odds            : dict des cotes 1X2 {"home", "away", "draw"}
      - round_label     : nombre entier de round (32, 16, 8, 4, 2, 1, 0…)
      - penalty_winner  : "home"/"away"/None, rempli uniquement si
        decided_by_penalties est True
      - has_full_stats  : True si des statistiques détaillées (tirs,
        possession, corners…) ont été trouvées ; False si seules les
        données de mi-temps ont pu être extraites (ou aucune donnée)
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

    # ── Cotes ────────────────────────────────────────────────────
    ml = extract_ml_odds(soup)
    odds = {
        "home": ml["home"] if ml else None,
        "away": ml["away"] if ml else None,
        "draw": ml["draw"] if ml else None,
    }

    # ── Round (numéro de coupe, déjà normalisé en nombre) ───────────
    round_label = extract_round_label(extract_round_info(soup))

    # ── Vainqueur aux tirs au but (uniquement si nécessaire) ────────
    penalty_winner = None
    if decided_by_penalties:
        penalty_winner = extract_penalty_winner(soup, home_team_id, away_team_id)

    # ── Statistiques (méthode Prism en priorité) ───────────────────
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

    # ── Flag : stats détaillées trouvées avant l'ajout de la mi-temps ──
    has_full_stats = len(stats) > 0

    # ── Mi-temps / 2nde mi-temps (frise "Match Timeline") ───────────
    try:
        halftime, second_half = extract_match_timeline_halftime(soup)
        if halftime is not None:
            stats["Score 1ère mi-temps"] = {"home": halftime["home"], "away": halftime["away"]}
        if second_half is not None:
            stats["Score 2nde mi-temps"] = {"home": second_half["home"], "away": second_half["away"]}
    except Exception as e:
        print(f"    ⚠️  Erreur injection mi-temps ({game_id}) : {e}")

    # ── Nettoyage final (toutes les valeurs numériques en int) ──────
    stats = finalize_stats(stats)

    return stats, odds, round_label, penalty_winner, has_full_stats


def enrich_matches_with_stats_and_odds(driver, all_matches_by_team):
    """
    Phase d'enrichissement : visite chaque match unique (par match_id)
    une seule fois pour récupérer ses statistiques (dont mi-temps, en
    int), ses cotes, son numéro de round et, si le match a été décidé
    aux tirs au but, le vainqueur des penalties. Injecte ensuite le
    résultat dans toutes les occurrences correspondantes. Le champ
    "matchday" n'est jamais modifié ici : le round de coupe est injecté
    dans le nouveau champ "round".
    """
    # ── Construction des métadonnées par match unique ───────────────
    game_meta = {}
    for matches in all_matches_by_team.values():
        for m in matches:
            gid = m.get("match_id")
            if gid and gid not in game_meta:
                game_meta[gid] = {
                    "home_team_id": m.get("home_team_id"),
                    "away_team_id": m.get("away_team_id"),
                    "decided_by_penalties": m.get("decided_by_penalties", False),
                }

    unique_game_ids = list(game_meta.keys())
    total = len(unique_game_ids)
    print("\n" + "=" * 60)
    print(f"🔄 PHASE D'ENRICHISSEMENT — Statistiques, mi-temps, cotes, rounds & pens ({total} match(s) unique(s))")
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

    # ── Injection dans tous les matchs ──────────────────────────────
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
            # Le round de coupe ne va JAMAIS dans matchday : champ séparé.
            if m.get("matchday") is None and round_by_game_id.get(gid) is not None:
                m["round"] = round_by_game_id[gid]
            if m.get("decided_by_penalties"):
                m["penalty_winner"] = penalty_winner_by_game_id.get(gid)

    print("\n  ✅ Injection des statistiques, mi-temps, cotes, rounds et tirs au but terminée")


# ===============================================================
# SORTIE JSON — ordre des clés propre et lisible
# ===============================================================

MATCH_KEY_ORDER = [
    "date", "season", "matchday", "round", "competition",
    "home_team", "home_team_id", "home_logo_url", "home_score",
    "away_team", "away_team_id", "away_logo_url", "away_score",
    "result", "decided_by_penalties", "penalty_winner", "team_result",
    "odds", "has_full_stats", "stats", "match_id", "match_url",
]

TEAM_KEY_ORDER = [
    "team_name", "team_id", "logo", "league_id", "league_name",
    "country", "total_matches", "scraped_at", "matches_by_season",
]


def clean_match(m):
    """Réordonne les clés d'un match selon MATCH_KEY_ORDER pour un JSON lisible."""
    return {k: m.get(k) for k in MATCH_KEY_ORDER}


def clean_team_output(team_output):
    """Réordonne les clés d'une équipe selon TEAM_KEY_ORDER pour un JSON lisible."""
    cleaned = {k: team_output.get(k) for k in TEAM_KEY_ORDER}
    cleaned["matches_by_season"] = {
        season: [clean_match(m) for m in season_matches]
        for season, season_matches in cleaned["matches_by_season"].items()
    }
    return cleaned


def scrape_with_selenium():
    driver = None
    output_data = []

    try:
        teams = fetch_target_teams()
        if not teams:
            print("❌ Aucune équipe sélectionnée. Vérifiez TARGET_COUNTRY/TARGET_LEAGUE.")
            return []

        print("\n🚀 Démarrage du navigateur (headless)...")
        driver = setup_driver()
        print("✅ Navigateur démarré")

        matches_by_team = {}  # team_id -> liste de matchs (pour la phase d'enrichissement)
        team_meta = {}        # team_id -> métadonnées de l'équipe

        for team in teams:
            team_name = team.get("team", "")
            team_id = team.get("team_id", "")

            print("\n" + "=" * 60)
            print(f"⚽ ÉQUIPE: {team_name} (id={team_id})")
            print(f"📆 Saisons: {format_season(START_SEASON)} → {format_season(END_SEASON)}")
            print("=" * 60)

            unique_matches = scrape_team_results_all_seasons(driver, team_name, team_id)

            matches_by_team[team_id] = unique_matches
            team_meta[team_id] = team

        # ── Phase d'enrichissement : statistiques, mi-temps, cotes, rounds, pens ──
        enrich_matches_with_stats_and_odds(driver, matches_by_team)

        # ── Construction de la sortie finale (matchs structurés par saison) ──
        for team_id, unique_matches in matches_by_team.items():
            team = team_meta[team_id]
            team_name = team.get("team", "")

            # ── Résultat (V/N/D) du point de vue de l'équipe scrapée ────
            for m in unique_matches:
                m["team_result"] = compute_team_result(m, team_id)

            team_output = {
                "team_name": team_name,
                "team_id": team_id,
                "logo": team.get("logo", build_logo_url(team_id)),
                "league_id": team.get("league_id", ""),
                "league_name": team.get("league_name", ""),
                "country": TARGET_COUNTRY,
                "total_matches": len(unique_matches),
                "scraped_at": datetime.now().isoformat(),
                "matches_by_season": group_matches_by_season(unique_matches),
            }

            output_data.append(clean_team_output(team_output))

            # ── Stats par compétition pour cette équipe ────────────
            competitions: dict[str, int] = {}
            for m in unique_matches:
                competitions[m["competition"]] = competitions.get(m["competition"], 0) + 1

            print(f"\n📊 Statistiques par compétition ({team_name}):")
            for comp, count in sorted(competitions.items(), key=lambda x: x[1], reverse=True):
                print(f"   {comp}: {count} match(s)")

        # ── Sauvegarde JSON globale (propre, indentée, clés ordonnées) ──
        final_output = {
            "country": TARGET_COUNTRY,
            "league_name": TARGET_LEAGUE,
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

        print(f"\n💾 {OUTPUT_JSON_PATH} sauvegardé")

        return output_data

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
    print("⚽ ESPN SCRAPER — PREMIER LEAGUE (1 ÉQUIPE)")
    print(f"📆 Saisons {format_season(START_SEASON)} à {format_season(END_SEASON)}, stats entièrement en int, matchday/round séparés, has_full_stats, structuré par saison")
    print("=" * 60)

    reset_output_directories()

    results = scrape_with_selenium()

    if results:
        total_matches = sum(t["total_matches"] for t in results)
        print(f"\n✅ {len(results)} équipe(s) traitée(s), {total_matches} matchs récupérés au total")

        for team_output in results:
            print(f"\n📋 {team_output['team_name']} — {team_output['total_matches']} matchs")
            for season_key, season_matches in team_output["matches_by_season"].items():
                print(f"\n  📆 Saison {season_key} — {len(season_matches)} match(s)")
                for i, m in enumerate(season_matches[:5]):
                    print(
                        f"    {i+1}. [{m['date']}] "
                        f"{m['home_team']} "
                        f"{m['home_score']}-{m['away_score']} "
                        f"{m['away_team']}  ({m['team_result']})  [{m['result']}]"
                    )
                    print(f"         🏆 {m['competition']}  |  🔗 {m['match_url']}")
                    journee = m['matchday'] if m['matchday'] is not None else "-"
                    round_val = m['round'] if m['round'] is not None else "-"
                    stats_flag = "✅" if m['has_full_stats'] else "⚠️"
                    ht = m['stats'].get("Score 1ère mi-temps", "-")
                    pens = f" | 🥅 pens: {m['penalty_winner']}" if m['decided_by_penalties'] else ""
                    print(
                        f"         📊 {stats_flag} {len(m['stats'])} statistique(s)  |  "
                        f"📅 Journée {journee}  |  🔁 Round {round_val}  |  ⏱️ MT {ht}  |  💰 {m['odds']}{pens}"
                    )
    else:
        print("\n❌ Aucune donnée récupérée")


if __name__ == "__main__":
    main()
