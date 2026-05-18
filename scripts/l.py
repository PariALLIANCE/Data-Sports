from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta, timezone
import re
import time
import os

OUTPUT_DIR = "data/football/leagues"
os.makedirs(OUTPUT_DIR, exist_ok=True)

LEAGUES = {
    "FA_Cup": {
        "id": "eng.fa",
        "json": "FA_Cup.json"
    }
}

BASE_URL = "https://africa.espn.com/football/results/_/date/{date}/league/{league}"

START_DATE = datetime(2023, 1, 1, tzinfo=timezone.utc)
END_DATE = datetime(2023, 1, 30, tzinfo=timezone.utc)

# =============================
# DRIVER SETUP
# =============================

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=fr-FR")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    return driver

# =============================
# STATS PAR GAMEID
# =============================

def get_match_stats(driver, game_id):
    url = f"https://africa.espn.com/football/match/_/gameId/{game_id}"
    try:
        driver.get(url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        stats_section = soup.find("section", {"data-testid": "prism-LayoutCard"})
        if not stats_section:
            print(f"  ⚠️ Pas de section stats pour gameId {game_id}")
            return {}

        stats = {}
        stat_rows = stats_section.find_all("div", class_="LOSQp")

        for row in stat_rows:
            name_tag = row.find("span", class_="OkRBU")
            values = row.find_all("span", class_="bLeWt")
            if name_tag and len(values) >= 2:
                stats[name_tag.text.strip()] = {
                    "home": values[0].text.strip(),
                    "away": values[1].text.strip()
                }

        return stats

    except Exception as e:
        print(f"❌ Erreur stats match {game_id} : {e}")
        return {}

# =============================
# SCRAPING
# =============================

driver = get_driver()

try:
    for league_name, league_info in LEAGUES.items():
        print(f"\n🏆 Traitement {league_name}")
        all_matches = {}

        # Charger données existantes
        output_path = os.path.join(OUTPUT_DIR, league_info["json"])
        existing_matches = {}
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8") as f:
                try:
                    existing_data = json.load(f)
                    existing_matches = {m["gameId"]: m for m in existing_data if "gameId" in m}
                    print(f"📂 {len(existing_matches)} matchs existants chargés")
                except json.JSONDecodeError:
                    print("⚠️ Fichier JSON corrompu, on repart de zéro")

        current_date = START_DATE
        while current_date <= END_DATE:
            date_str = current_date.strftime("%Y%m%d")
            url = BASE_URL.format(date=date_str, league=league_info["id"])
            print(f"📅 {league_name} - {date_str}")

            try:
                driver.get(url)

                # Attendre que les tables chargent
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.ResponsiveTable"))
                    )
                except:
                    print(f"  → 0 table(s) trouvée(s)")
                    current_date += timedelta(days=1)
                    continue

                soup = BeautifulSoup(driver.page_source, "html.parser")

            except Exception as e:
                print(f"⚠️ Erreur navigation ({date_str}) : {e}")
                current_date += timedelta(days=1)
                continue

            tables = soup.select("div.ResponsiveTable")
            print(f"  → {len(tables)} table(s) trouvée(s)")

            for table in tables:
                date_title_tag = table.select_one("div.Table__Title")
                date_text = date_title_tag.text.strip() if date_title_tag else date_str

                rows = table.select("tbody > tr.Table__TR")
                print(f"  → {len(rows)} ligne(s)")

                for row in rows:
                    try:
                        teams = row.select("span.Table__Team a.AnchorLink:last-child")
                        score_tag = row.select_one("a.AnchorLink.at")

                        if len(teams) != 2 or not score_tag:
                            continue

                        team1 = teams[0].text.strip()
                        team2 = teams[1].text.strip()
                        score = score_tag.text.strip()

                        if score.lower() == "v":
                            continue

                        match_url = score_tag["href"]
                        match_id_match = re.search(r"gameId/(\d+)", match_url)
                        if not match_id_match:
                            continue

                        game_id = match_id_match.group(1)
                        print(f"  ✅ {team1} vs {team2} | {score} | gameId: {game_id}")

                        stats = get_match_stats(driver, game_id)
                        print(f"  📊 Stats: {stats if stats else 'vides'}")

                        if game_id not in all_matches:
                            all_matches[game_id] = {
                                "gameId": game_id,
                                "date": date_text,
                                "team1": team1,
                                "team2": team2,
                                "score": score,
                                "title": f"{team1} VS {team2}",
                                "match_url": "https://africa.espn.com" + match_url,
                                "stats": stats
                            }
                        elif not all_matches[game_id].get("stats") and stats:
                            all_matches[game_id]["stats"] = stats

                    except Exception as e:
                        print(f"⚠️ Parsing ({date_str}) : {e}")

            current_date += timedelta(days=1)
            time.sleep(1.5)

        # Fusion + sauvegarde
        existing_matches.update(all_matches)
        if existing_matches:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(list(existing_matches.values()), f, indent=2, ensure_ascii=False)
            print(f"\n💾 {output_path} : {len(existing_matches)} matchs")
        else:
            print(f"⚠️ Aucune donnée — fichier non écrasé")

finally:
    driver.quit()
    print("\n🔒 Driver fermé")