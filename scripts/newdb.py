from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
import json
import time
import re
from datetime import datetime

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


def extract_match_info(match_row, month):
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

        return {
            "date": date,
            "month": month,
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
            "season": "2025",
        }

    except Exception as e:
        print(f"⚠️ Erreur extraction: {str(e)[:120]}")
        return None


def scrape_with_selenium():
    driver = None
    all_matches = []

    try:
        print("🚀 Démarrage du navigateur (headless)...")
        driver = setup_driver()
        print("✅ Navigateur démarré")

        url = "https://www.espn.com/soccer/team/results/_/id/6272/season/2025"
        print(f"🌐 Accès: {url}")
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

        print(f"📊 {len(result_tables)} bloc(s) mensuel(s) trouvé(s)")

        if not result_tables:
            print("❌ Aucun tableau trouvé. Vérifiez le sélecteur ou le chargement JS.")
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
                match_data = extract_match_info(row, month)
                if match_data:
                    all_matches.append(match_data)
                    print(
                        f"   ✅ {match_data['home_team']} {match_data['home_score']}"
                        f" - {match_data['away_score']} {match_data['away_team']}"
                        f"  [{match_data['competition']}]"
                    )
                else:
                    print("   ⚠️ Ligne ignorée (extraction échouée)")

        # ── Dédoublonnage ─────────────────────────────────────────────
        seen = set()
        unique_matches = []
        for m in all_matches:
            key = f"{m['match_id']}_{m['date']}"
            if key not in seen and m["match_id"]:
                seen.add(key)
                unique_matches.append(m)

        print(f"\n✅ {len(unique_matches)} matchs uniques (sur {len(all_matches)} extraits)")

        # ── Tri : du plus récent au plus ancien ───────────────────────
        MONTH_ORDER = {
            "January": 1, "February": 2, "March": 3, "April": 4,
            "May": 5, "June": 6, "July": 7, "August": 8,
            "September": 9, "October": 10, "November": 11, "December": 12,
        }

        def sort_key(m):
            month_str = m["month"].split(",")[0].strip()
            month_num = MONTH_ORDER.get(month_str, 0)
            day_m = re.search(r"(\d+)", m["date"])
            day = int(day_m.group(1)) if day_m else 0
            return (month_num, day)

        unique_matches.sort(key=sort_key, reverse=True)

        # ── Sauvegarde JSON ───────────────────────────────────────────
        output = {
            "team_name": "Fortaleza",
            "team_id": "6272",
            "season": "2025",
            "total_matches": len(unique_matches),
            "scraped_at": datetime.now().isoformat(),
            "matches": unique_matches,
        }

        with open("newdb.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print("💾 newdb.json sauvegardé")

        # ── Stats par compétition ─────────────────────────────────────
        competitions: dict[str, int] = {}
        for m in unique_matches:
            competitions[m["competition"]] = competitions.get(m["competition"], 0) + 1

        print("\n📊 Statistiques par compétition:")
        for comp, count in sorted(competitions.items(), key=lambda x: x[1], reverse=True):
            print(f"   {comp}: {count} match(s)")

        return unique_matches

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
    print("⚽ ESPN SCRAPER — FORTALEZA RESULTS")
    print("=" * 60)

    results = scrape_with_selenium()

    if results:
        print(f"\n✅ {len(results)} matchs récupérés au total")
        print("\n📋 Aperçu des 5 premiers matchs:")
        for i, m in enumerate(results[:5]):
            print(
                f"  {i+1}. [{m['date']} — {m['month']}] "
                f"{m['home_team']} "
                f"{m['home_score']}-{m['away_score']} "
                f"{m['away_team']}"
            )
            print(f"       🏆 {m['competition']}  |  🔗 {m['match_url']}")
    else:
        print("\n❌ Aucune donnée récupérée")


if __name__ == "__main__":
    main()