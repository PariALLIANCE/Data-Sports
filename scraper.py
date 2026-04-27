from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import sys

def setup_driver_for_github():
    """Configurer ChromeDriver pour GitHub Actions"""
    chrome_options = Options()
    
    # Configuration pour GitHub Actions (headless est obligatoire)
    chrome_options.add_argument("--headless=new")  # Nouveau mode headless
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")  # Désactiver GPU (important pour CI)
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Éviter les erreurs de détection
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # User agent réaliste
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Service avec logs pour debug
    service = Service(
        ChromeDriverManager().install(),
        service_log_path='/dev/null' if sys.platform != 'win32' else 'NUL'
    )
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def get_premier_league_table_github():
    """Version optimisée pour GitHub Actions"""
    driver = setup_driver_for_github()
    
    try:
        url = "https://www.espn.com/soccer/table/_/league/ENG.1"
        print(f"Chargement de {url}...")
        driver.get(url)
        
        # Attendre le chargement
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ResponsiveTable")))
        
        # Extraire les données
        table_data = []
        
        # Méthode robuste pour GitHub
        team_elements = driver.find_elements(By.CSS_SELECTOR, "span.hide-mobile a")
        team_names = [elem.text.strip() for elem in team_elements]
        
        position_elements = driver.find_elements(By.CSS_SELECTOR, "span.team-position")
        positions = [elem.text.strip() for elem in position_elements]
        
        # Extraire les stats
        stat_cells = driver.find_elements(By.CSS_SELECTOR, "td.Table__TD span.stat-cell")
        
        # Grouper par 8 stats
        stats_by_team = []
        for i in range(0, len(stat_cells), 8):
            team_stats = stat_cells[i:i+8]
            if len(team_stats) == 8:
                stats_by_team.append([stat.text.strip() for stat in team_stats])
        
        # Fusionner les données
        for i in range(min(len(team_names), len(stats_by_team))):
            table_data.append({
                'Pos': positions[i] if i < len(positions) else str(i+1),
                'Team': team_names[i],
                'GP': stats_by_team[i][0],
                'W': stats_by_team[i][1],
                'D': stats_by_team[i][2],
                'L': stats_by_team[i][3],
                'F': stats_by_team[i][4],
                'A': stats_by_team[i][5],
                'GD': stats_by_team[i][6],
                'P': stats_by_team[i][7]
            })
        
        return table_data
        
    except Exception as e:
        print(f"Erreur: {e}")
        # Sauvegarder la source pour debug
        with open('page_source.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        return None
    finally:
        driver.quit()