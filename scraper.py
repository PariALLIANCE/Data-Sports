import os
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

def setup_driver():
    """Configuration spécifique pour GitHub Actions"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--window-size=1920,1080")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def scrape_table():
    driver = setup_driver()
    
    try:
        print("🌐 Chargement de la page ESPN...")
        driver.get("https://www.espn.com/soccer/table/_/league/ENG.1")
        
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ResponsiveTable")))
        
        print("📊 Extraction des données...")
        
        # Extraction avec vérifications
        teams = [elem.text.strip() for elem in driver.find_elements(By.CSS_SELECTOR, "span.hide-mobile a")]
        positions = [elem.text.strip() for elem in driver.find_elements(By.CSS_SELECTOR, "span.team-position")]
        
        if not teams:
            print("⚠️ Aucune équipe trouvée, tentative avec sélecteur alternatif...")
            teams = [elem.text.strip() for elem in driver.find_elements(By.CSS_SELECTOR, ".team-link .hide-mobile a")]
        
        stats_cells = driver.find_elements(By.CSS_SELECTOR, "td.Table__TD span.stat-cell")
        
        if not stats_cells:
            print("⚠️ Aucune statistique trouvée")
            return None
        
        # Grouper par 8 stats
        stats_data = []
        for i in range(0, len(stats_cells), 8):
            team_stats = stats_cells[i:i+8]
            if len(team_stats) == 8:
                stats_data.append([cell.text.strip() for cell in team_stats])
        
        print(f"✅ Trouvé: {len(teams)} équipes, {len(stats_data)} lignes de stats")
        
        # Vérifier la cohérence
        if len(teams) != len(stats_data):
            print(f"⚠️ Incohérence: {len(teams)} équipes vs {len(stats_data)} lignes de stats")
            min_len = min(len(teams), len(stats_data))
            teams = teams[:min_len]
            stats_data = stats_data[:min_len]
        
        # Construction du tableau
        table = []
        for i, team in enumerate(teams):
            if i < len(stats_data):
                row = {
                    'position': positions[i] if i < len(positions) else i+1,
                    'team': team,
                    'GP': stats_data[i][0] if len(stats_data[i]) > 0 else '',
                    'W': stats_data[i][1] if len(stats_data[i]) > 1 else '',
                    'D': stats_data[i][2] if len(stats_data[i]) > 2 else '',
                    'L': stats_data[i][3] if len(stats_data[i]) > 3 else '',
                    'F': stats_data[i][4] if len(stats_data[i]) > 4 else '',
                    'A': stats_data[i][5] if len(stats_data[i]) > 5 else '',
                    'GD': stats_data[i][6] if len(stats_data[i]) > 6 else '',
                    'P': stats_data[i][7] if len(stats_data[i]) > 7 else ''
                }
                table.append(row)
        
        return table
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        
        # Sauvegarder la page source pour debug
        try:
            with open('page_source.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print("📄 Page source sauvegardée dans page_source.html")
        except:
            pass
        
        return None
    finally:
        driver.quit()

def save_csv(table, filename='premier_league_2025-2026.csv'):
    if not table:
        print("❌ Aucune donnée à sauvegarder")
        return False
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            headers = ['position', 'team', 'GP', 'W', 'D', 'L', 'F', 'A', 'GD', 'P']
            f.write(','.join(headers) + '\n')
            
            for row in table:
                line = ','.join([str(row.get(h, '')) for h in headers])
                f.write(line + '\n')
        
        # Vérifier que le fichier a été créé
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            print(f"✅ Fichier {filename} créé ({file_size} octets)")
            return True
        else:
            print(f"❌ Le fichier {filename} n'a pas été créé")
            return False
            
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        return False

def display_top5(table):
    """Afficher les 5 premières équipes"""
    if not table:
        return
    
    print("\n📈 Top 5 du classement:")
    print("-" * 50)
    for team in table[:5]:
        print(f"  {team['position']}. {team['team']:<25} {team['P']} pts")
    print("-" * 50)

if __name__ == "__main__":
    print("🚀 Début du scraping Premier League...")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 Répertoire de travail: {os.getcwd()}")
    
    table = scrape_table()
    
    if table and len(table) > 0:
        print(f"\n✅ {len(table)} équipes récupérées avec succès")
        display_top5(table)
        
        if save_csv(table):
            print("\n🎉 Script terminé avec succès!")
            sys.exit(0)
        else:
            print("\n❌ Échec de la sauvegarde du CSV")
            sys.exit(1)
    else:
        print("\n❌ Échec du scraping - aucune donnée récupérée")
        sys.exit(1)