import json
import os
import re
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

TARGET_URL = "https://www.espn.com/soccer/team/results/_/id/6272/season/2025"
OUTPUT_FILE = "data/football/results.json"

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
window.chrome = { runtime: {} };
"""


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--lang=en-US")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Masquer navigator.webdriver
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": STEALTH_JS},
    )

    return driver


def scrape_espn_results():
    driver = build_driver()

    try:
        print(f"→ Chargement de {TARGET_URL}")
        driver.get(TARGET_URL)

        # Pause initiale pour laisser le JS s'exécuter
        time.sleep(6)

        # Scroll progressif pour déclencher le lazy-load
        for _ in range(6):
            driver.execute_script("window.scrollBy(0, 600)")
            time.sleep(1)

        driver.execute_script("window.scrollTo(0, 0)")
        time.sleep(2)

        # Attendre le tableau
        try:
            WebDriverWait(driver, 45).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".Table__results-mobile"))
            )
        except Exception:
            os.makedirs("data/football", exist_ok=True)
            driver.save_screenshot("data/football/debug_screenshot.png")
            with open("data/football/debug_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("❌ Sélecteur introuvable — screenshot et HTML sauvegardés pour debug")
            raise

        matches = []

        month_blocks = driver.find_elements(By.CSS_SELECTOR, ".Table__results-mobile")
        print(f"→ {len(month_blocks)} bloc(s) mensuel(s) trouvé(s)")

        for block in month_blocks:
            # Titre du bloc mensuel
            try:
                month_label = block.find_element(By.CSS_SELECTOR, ".Table__Title").text
            except Exception:
                month_label = "Unknown"

            rows = block.find_elements(By.CSS_SELECTOR, "tbody.Table__TBODY tr.Table__TR--sm")

            for row in rows:
                try:
                    match = parse_row(row, month_label)
                    if match:
                        matches.append(match)
                        print(
                            f"  ✓ {match['date']} | {match['home_team']} "
                            f"{match['home_score']}-{match['away_score']} "
                            f"{match['away_team']} | {match['competition']}"
                        )
                except Exception as e:
                    print(f"  ✗ Erreur sur une ligne : {e}")

    finally:
        driver.quit()

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(matches)} match(s) exporté(s) dans '{OUTPUT_FILE}'")
    return matches


def parse_row(row, month_label: str) -> dict | None:
    cells = row.find_elements(By.CSS_SELECTOR, "td.Table__TD")
    if len(cells) < 6:
        return None

    # ── DATE ──────────────────────────────────────────────────────────────────
    try:
        raw_date = cells[0].find_element(By.CSS_SELECTOR, "[data-testid='date']").text.strip()
    except Exception:
        raw_date = ""

    year_match = re.search(r"\d{4}", month_label)
    year = year_match.group(0) if year_match else str(datetime.now().year)
    date_str = f"{raw_date}, {year}"

    # ── ÉQUIPES ───────────────────────────────────────────────────────────────
    try:
        home_el = cells[1].find_element(By.CSS_SELECTOR, "[data-testid='formattedTeam']")
        home_href = home_el.get_attribute("href") or ""
    except Exception:
        home_href = ""

    try:
        away_el = cells[3].find_element(By.CSS_SELECTOR, "[data-testid='formattedTeam']")
        away_href = away_el.get_attribute("href") or ""
    except Exception:
        away_href = ""

    home_name = _name_from_href(home_href)
    away_name = _name_from_href(away_href)
    home_id   = _id_from_href(home_href)
    away_id   = _id_from_href(away_href)

    # ── CELLULE SCORE ─────────────────────────────────────────────────────────
    home_logo_url = ""
    away_logo_url = ""
    home_score    = ""
    away_score    = ""
    match_url     = ""

    try:
        score_cell  = cells[2].find_element(By.CSS_SELECTOR, "[data-testid='score']")
        score_links = score_cell.find_elements(By.CSS_SELECTOR, "a.AnchorLink")

        if len(score_links) >= 3:
            # Logo équipe locale
            try:
                home_logo_url = score_links[0].find_element(By.TAG_NAME, "img").get_attribute("src") or ""
            except Exception:
                pass

            # Score + URL du match
            score_text = score_links[1].text.strip()
            rel_url    = score_links[1].get_attribute("href") or ""
            match_url  = _absolute(rel_url)
            home_score, away_score = _parse_score(score_text)

            # Logo équipe extérieure
            try:
                away_logo_url = score_links[2].find_element(By.TAG_NAME, "img").get_attribute("src") or ""
            except Exception:
                pass
    except Exception:
        pass

    # ── RÉSULTAT (FT / AET / PEN …) ──────────────────────────────────────────
    try:
        result_status = cells[4].find_element(By.CSS_SELECTOR, "[data-testid='result'] a").text.strip()
    except Exception:
        result_status = ""

    # ── COMPÉTITION ───────────────────────────────────────────────────────────
    try:
        competition = cells[5].find_element(By.TAG_NAME, "span").text.strip()
    except Exception:
        competition = ""

    return {
        "date":          date_str,
        "month_block":   month_label,
        "home_team":     home_name,
        "home_id":       home_id,
        "home_score":    home_score,
        "away_score":    away_score,
        "away_team":     away_name,
        "away_id":       away_id,
        "result_status": result_status,
        "competition":   competition,
        "home_logo_url": home_logo_url,
        "away_logo_url": away_logo_url,
        "match_url":     match_url,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _id_from_href(href: str) -> str:
    if not href:
        return ""
    m = re.search(r"/id/(\d+)/", href)
    return m.group(1) if m else ""


def _name_from_href(href: str) -> str:
    if not href:
        return ""
    parts = href.rstrip("/").split("/")
    return parts[-1].replace("-", " ").title() if parts else ""


def _absolute(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return f"https://www.espn.com{href}"


def _parse_score(score_text: str) -> tuple[str, str]:
    m = re.search(r"(\d+)\s*-\s*(\d+)", score_text)
    if m:
        return m.group(1), m.group(2)
    return "", ""


# ── Point d'entrée ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    scrape_espn_results()