import json
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

LEAGUES = {
    "England_Premier_League": "eng.1",
    "Spain_Laliga": "esp.1",
    "Germany_Bundesliga": "ger.1",
    "Argentina_Primera_Nacional": "arg.2",
    "Austria_Bundesliga": "aut.1",
    "Belgium_Jupiler_Pro_League": "bel.1",
    "Brazil_Serie_A": "bra.1",
    "Brazil_Serie_B": "bra.2",
    "Chile_Primera_Division": "chi.1",
    "China_Super_League": "chn.1",
    "Colombia_Primera_A": "col.1",
    "England_National_League": "eng.5",
    "France_Ligue_1": "fra.1",
    "Greece_Super_League_1": "gre.1",
    "Italy_Serie_A": "ita.1",
    "Japan_J1_League": "jpn.1",
    "Mexico_Liga_MX": "mex.1",
    "Netherlands_Eredivisie": "ned.1",
    "Paraguay_Division_Profesional": "par.1",
    "Peru_Primera_Division": "per.1",
    "Portugal_Primeira_Liga": "por.1",
    "Romania_Liga_I": "rou.1",
    "Russia_Premier_League": "rus.1",
    "Saudi_Arabia_Pro_League": "ksa.1",
    "Sweden_Allsvenskan": "swe.1",
    "Switzerland_Super_League": "sui.1",
    "Turkey_Super_Lig": "tur.1",
    "USA_Major_League_Soccer": "usa.1",
    "Venezuela_Primera_Division": "ven.1",
    "UEFA_Champions_League": "uefa.champions",
    "UEFA_Europa_League": "uefa.europa",
    "FIFA_Club_World_Cup": "fifa.cwc"
}

BASE_DIR = "data/football/standings"
os.makedirs(BASE_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(BASE_DIR, "Standings.json")

def setup_driver():
    """Configure Chrome en mode headless pour GitHub Actions / CI"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    chrome_options.add_argument(f"user-agent={user_agent}")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def fetch_standings_with_selenium(league_id):
    """Charge la page ESPN et extrait les standings avec Selenium"""
    url = f"https://www.espn.com/soccer/standings/_/league/{league_id}"
    driver = setup_driver()
    
    try:
        driver.get(url)
        # Attendre que le tableau des positions apparaisse
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.Table--fixed-left")))
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".Table__Scroller table")))
        
        # Récupérer les lignes des équipes (partie gauche avec noms)
        team_rows = driver.find_elements(By.CSS_SELECTOR, "table.Table--fixed-left tbody tr")
        # Récupérer les lignes des statistiques (partie droite)
        stats_rows = driver.find_elements(By.CSS_SELECTOR, ".Table__Scroller table tbody tr")
        
        standings = []
        for i in range(min(len(team_rows), len(stats_rows))):
            team_row = team_rows[i]
            stat_row = stats_rows[i]
            
            # Position
            pos_elem = team_row.find_element(By.CSS_SELECTOR, "span.team-position")
            position = int(pos_elem.text.strip())
            
            # Nom de l'équipe
            name_elem = team_row.find_element(By.CSS_SELECTOR, ".hide-mobile a")
            name = name_elem.text.strip()
            
            # Statistiques
            stat_cells = stat_row.find_elements(By.CSS_SELECTOR, "td span.stat-cell")
            if len(stat_cells) < 8:
                continue
            
            values = [cell.text.strip() for cell in stat_cells[:8]]
            gp, w, d, l, f, a, gd, p = values
            
            # Gérer le signe + du GD
            if gd.startswith('+'):
                gd = gd[1:]
            
            standings.append({
                "position": position,
                "name": name,
                "stats": {
                    "GP": int(gp),
                    "W": int(w),
                    "D": int(d),
                    "L": int(l),
                    "F": int(f),
                    "A": int(a),
                    "GD": int(gd),
                    "P": int(p)
                }
            })
        return standings
    except Exception as e:
        print(f"  Erreur Selenium : {e}")
        # Sauvegarder la source pour debug
        with open(f"debug_{league_id}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        return []
    finally:
        driver.quit()

def scrape_all_leagues():
    all_data = {}
    for league_name, league_id in LEAGUES.items():
        try:
            print(f"🔹 Scraping {league_name}...")
            standings = fetch_standings_with_selenium(league_id)
            all_data[league_name] = standings
            print(f"✔ {len(standings)} équipes enregistrées pour {league_name}\n")
            time.sleep(2)  # Pause pour éviter la surcharge
        except Exception as e:
            print(f"❌ Erreur pour {league_name}: {e}")
    
    # Sauvegarde finale
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)
    print(f"\n✅ Tous les classements enregistrés dans {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_all_leagues()