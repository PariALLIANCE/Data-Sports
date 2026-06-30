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
import urllib.request
from datetime import datetime

TEAMS_JSON_URL = "https://raw.githubusercontent.com/PariALLIANCE/Data-Sports/main/data/football/teams/football_teams.json"
TARGET_COUNTRY = "England"
TARGET_LEAGUE = "England_Premier_League"
NB_TEAMS = 3

START_SEASON = 2022
END_SEASON = datetime.now().year  # saison actuelle incluse


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


def team_name_from_href(href):
    """Extrait le nom lisible depuis l'URL de l'équipe ESPN.
    Ex: /soccer/team/_/id/6086/botafogo → Botafogo
    """
    if not href:
        return ""
    slug = href.rstrip("/").split("/")[-1]
    return slug.replace("-", " ").title()


def build_logo_url(team_id):
    """Construit l'URL du logo ESPN à partir de l'ID d'équipe."""
    if not team_id:
        return ""
    return f"https://a.espncdn.com/i/teamlogos/soccer/500/{team_id}.png"


def fetch_target_teams():
    """
    Récupère le fichier football_teams.json depuis GitHub, et retourne
    les NB_TEAMS premières équipes de TARGET_COUNTRY / TARGET_LEAGUE.
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

        home_score = ""
        away_score = ""
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
                home_score = score_m.group(1)
                away_score = score_m.group(2)

        # ── [3] ÉQUIPE AWAY ───────────────────────────────────────────
        away_links = cells[3].find_elements(By.TAG_NAME, "a")
        if not away_links:
            return None
        away_href = away_links[0].get_attribute("href") or ""
        away_id_m = re.search(r"/id/(\d+)/", away_href)
        away_team_id = away_id_m.group(1) if away_id_m else ""
        away_team_name = team_name_from_href(away_href)

        # ── [4] RÉSULTAT ──────────────────────────────────────────────
        result = ""
        result_els = cells[4].find_elements(By.CSS_SELECTOR, '[data-testid="result"]')
        if result_els:
            result = result_els[0].text.strip()
        else:
            result_links = cells[4].find_elements(By.TAG_NAME, "a")
            if result_links:
                result = result_links[0].text.strip()

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

        return {
            "date": date,
            "month": month,
            "year": match_year,
            "home_team": local_team_name,
            "home_team_id": local_team_id,
            "home_logo_url": build_logo_url(local_team_id),
            "home_score": home_score,
            "away_score": away_score,
            "away_team": away_team_name,
            "away_team_id": away_team_id,
            "away_logo_url": build_logo_url(away_team_id),
            "match_url": match_url,
            "match_id": match_id,
            "result": result,
            "competition": competition,
            "season": str(season),
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


def scrape_team_results_all_seasons(driver, team_name, team_id):
    """
    Scrape les résultats d'une équipe ESPN pour toutes les saisons de
    START_SEASON à END_SEASON, déduplique sur l'ensemble des saisons,
    puis trie du plus récent au plus ancien.
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
        key = m["match_id"] if m["match_id"] else f"{m['home_team']}_{m['away_team']}_{m['date']}_{m['month']}"
        if key not in seen:
            seen.add(key)
            unique_matches.append(m)

    print(
        f"\n✅ {len(unique_matches)} matchs uniques pour {team_name} "
        f"(sur {len(combined_matches)} extraits, saisons {START_SEASON}-{END_SEASON})"
    )

    # ── Tri : du plus récent au plus ancien (année > mois > jour) ──
    def sort_key(m):
        year = int(m["year"]) if m["year"].isdigit() else 0
        month_str = m["month"].split(",")[0].strip()
        month_num = MONTH_ORDER.get(month_str, 0)
        day_m = re.search(r"(\d+)", m["date"])
        day = int(day_m.group(1)) if day_m else 0
        return (year, month_num, day)

    unique_matches.sort(key=sort_key, reverse=True)

    return unique_matches


# ===============================================================
# STATISTIQUES DE MATCH (structure Prism ESPN, avec fallbacks)
# ===============================================================

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


def get_match_stats_selenium(driver, game_id):
    """
    Charge la page du match via Selenium (gameId) et retourne les
    statistiques extraites (méthode Prism en priorité, puis fallback
    via sélecteurs CSS avancés).
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
        print(f"    ⚠️  WebDriver erreur stats ({game_id}) : {e}")
        return {}

    soup = BeautifulSoup(driver.page_source, "html.parser")
    stats = extract_match_stats_prism(soup)
    if stats:
        return stats

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
        return stats
    except NoSuchElementException:
        return {}
    except Exception as e:
        print(f"    ⚠️  Erreur stats selenium ({game_id}) : {e}")
        return {}


def enrich_matches_with_stats(driver, all_matches_by_team):
    """
    Phase d'enrichissement : visite chaque match unique (par match_id)
    une seule fois pour récupérer ses statistiques, puis injecte le
    résultat dans toutes les occurrences de ce match (au cas où deux
    équipes suivies se sont affrontées, le match apparaît deux fois).
    """
    # ── Construction de la liste des game_id uniques ───────────────
    unique_game_ids = []
    seen_ids = set()
    for matches in all_matches_by_team.values():
        for m in matches:
            gid = m.get("match_id")
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                unique_game_ids.append(gid)

    total = len(unique_game_ids)
    print("\n" + "=" * 60)
    print(f"🔄 PHASE D'ENRICHISSEMENT — Statistiques ({total} match(s) unique(s))")
    print("=" * 60)

    stats_by_game_id = {}
    for idx, gid in enumerate(unique_game_ids, 1):
        print(f"\n  [{idx}/{total}] gameId={gid}")
        try:
            stats = get_match_stats_selenium(driver, gid)
        except Exception as e:
            print(f"    ⚠️ Erreur stats gameId={gid}: {e}")
            stats = {}
        stats_by_game_id[gid] = stats
        print(f"    📊 {len(stats)} statistique(s) récupérée(s)")
        time.sleep(0.8)

    # ── Injection dans tous les matchs (toutes équipes confondues) ──
    for matches in all_matches_by_team.values():
        for m in matches:
            gid = m.get("match_id")
            if gid and gid in stats_by_game_id:
                m["stats"] = stats_by_game_id[gid]

    print("\n  ✅ Injection des statistiques terminée")


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
            print(f"📆 Saisons: {START_SEASON} → {END_SEASON}")
            print("=" * 60)

            unique_matches = scrape_team_results_all_seasons(driver, team_name, team_id)

            matches_by_team[team_id] = unique_matches
            team_meta[team_id] = team

        # ── Phase d'enrichissement : statistiques de chaque match ──
        enrich_matches_with_stats(driver, matches_by_team)

        # ── Construction de la sortie finale ────────────────────────
        for team_id, unique_matches in matches_by_team.items():
            team = team_meta[team_id]
            team_name = team.get("team", "")

            team_output = {
                "team_name": team_name,
                "team_id": team_id,
                "logo": team.get("logo", build_logo_url(team_id)),
                "league_id": team.get("league_id", ""),
                "league_name": team.get("league_name", ""),
                "country": TARGET_COUNTRY,
                "seasons": f"{START_SEASON}-{END_SEASON}",
                "total_matches": len(unique_matches),
                "scraped_at": datetime.now().isoformat(),
                "matches": unique_matches,
            }

            output_data.append(team_output)

            # ── Stats par compétition pour cette équipe ────────────
            competitions: dict[str, int] = {}
            for m in unique_matches:
                competitions[m["competition"]] = competitions.get(m["competition"], 0) + 1

            print(f"\n📊 Statistiques par compétition ({team_name}):")
            for comp, count in sorted(competitions.items(), key=lambda x: x[1], reverse=True):
                print(f"   {comp}: {count} match(s)")

        # ── Sauvegarde JSON globale ─────────────────────────────────
        final_output = {
            "country": TARGET_COUNTRY,
            "league_name": TARGET_LEAGUE,
            "seasons": f"{START_SEASON}-{END_SEASON}",
            "nb_teams": len(output_data),
            "scraped_at": datetime.now().isoformat(),
            "teams": output_data,
        }

        with open("newdb.json", "w", encoding="utf-8") as f:
            json.dump(final_output, f, ensure_ascii=False, indent=2)

        print("\n💾 newdb.json sauvegardé")

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
    print(f"⚽ ESPN SCRAPER — PREMIER LEAGUE ({NB_TEAMS} PREMIÈRES ÉQUIPES)")
    print(f"📆 Saisons {START_SEASON} à {END_SEASON}, sans doublons, avec statistiques")
    print("=" * 60)

    results = scrape_with_selenium()

    if results:
        total_matches = sum(len(t["matches"]) for t in results)
        print(f"\n✅ {len(results)} équipe(s) traitée(s), {total_matches} matchs récupérés au total")

        for team_output in results:
            print(f"\n📋 {team_output['team_name']} — {team_output['total_matches']} matchs")
            for i, m in enumerate(team_output["matches"][:5]):
                print(
                    f"  {i+1}. [{m['date']} — {m['month']}] "
                    f"{m['home_team']} "
                    f"{m['home_score']}-{m['away_score']} "
                    f"{m['away_team']}"
                )
                print(f"       🏆 {m['competition']}  |  🔗 {m['match_url']}")
                print(f"       📊 {len(m['stats'])} statistique(s)")
    else:
        print("\n❌ Aucune donnée récupérée")


if __name__ == "__main__":
    main()