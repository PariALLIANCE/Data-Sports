from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json
import time
import re
from datetime import datetime
import os
import sys

def setup_driver():
    """Configure et retourne le driver Chrome pour GitHub Actions"""
    chrome_options = Options()
    
    # Options essentielles pour GitHub Actions
    chrome_options.add_argument("--headless=new")  # Mode headless moderne
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--lang=en-US,en")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # User-Agent réaliste
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Désactiver les logs inutiles
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    
    # Utiliser WebDriver Manager
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Masquer l'utilisation de Selenium
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Définir des timeouts
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(10)
    
    return driver

def wait_for_element(driver, by, selector, timeout=30):
    """Attend qu'un élément soit présent"""
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    except TimeoutException:
        return None

def extract_match_info(match_row, month):
    """Extrait les informations d'un match"""
    try:
        cells = match_row.find_elements(By.TAG_NAME, 'td')
        if len(cells) < 6:
            return None
        
        # Date
        date_element = cells[0].find_element(By.CLASS_NAME, 'matchTeams') if cells[0].find_elements(By.CLASS_NAME, 'matchTeams') else None
        date = date_element.text.strip() if date_element else ""
        
        # Équipe domicile
        home_abbr_element = cells[1].find_element(By.CLASS_NAME, 'Table__Team') if cells[1].find_elements(By.CLASS_NAME, 'Table__Team') else None
        home_abbr = home_abbr_element.text.strip() if home_abbr_element else ""
        
        # Score et équipes
        score_cell = cells[2]
        score_links = score_cell.find_elements(By.TAG_NAME, 'a')
        images = score_cell.find_elements(By.TAG_NAME, 'img')
        
        home_team = ""
        away_team = ""
        home_score = ""
        away_score = ""
        home_team_id = ""
        away_team_id = ""
        home_logo = ""
        away_logo = ""
        match_url = ""
        match_id = ""
        result = ""
        competition = ""
        
        if len(score_links) >= 3:
            home_link = score_links[0]
            home_team = home_link.text.strip()
            home_url = home_link.get_attribute('href') or ""
            home_team_id = home_url.split('/id/')[-1] if '/id/' in home_url else ""
            
            score_link = score_links[1]
            score_text = score_link.text.strip()
            match_url = score_link.get_attribute('href') or ""
            match_id = match_url.split('/gameId/')[-1] if '/gameId/' in match_url else ""
            
            score_match = re.search(r'(\d+)\s*[-:]\s*(\d+)', score_text)
            if score_match:
                home_score = score_match.group(1)
                away_score = score_match.group(2)
            else:
                score_parts = score_text.split(' - ')
                if len(score_parts) == 2:
                    home_score = score_parts[0].strip()
                    away_score = score_parts[1].strip()
                elif 'FT' in score_text:
                    result = 'FT'
                elif 'Pens' in score_text:
                    result = 'FT-Pens'
            
            away_link = score_links[2]
            away_team = away_link.text.strip()
            away_url = away_link.get_attribute('href') or ""
            away_team_id = away_url.split('/id/')[-1] if '/id/' in away_url else ""
        
        if len(images) >= 2:
            home_logo = images[0].get_attribute('src') or ""
            away_logo = images[1].get_attribute('src') or ""
        
        away_abbr_element = cells[3].find_element(By.CLASS_NAME, 'Table__Team') if cells[3].find_elements(By.CLASS_NAME, 'Table__Team') else None
        away_abbr = away_abbr_element.text.strip() if away_abbr_element else ""
        
        result_elements = cells[4].find_elements(By.TAG_NAME, 'span')
        for elem in result_elements:
            if 'FT' in elem.text or 'Pens' in elem.text:
                result = elem.text.strip()
                break
        
        competition_elements = cells[5].find_elements(By.TAG_NAME, 'span')
        if competition_elements:
            competition = competition_elements[-1].text.strip()
        
        # Nettoyer les URLs
        if home_logo and not home_logo.startswith('http'):
            if home_logo.startswith('//'):
                home_logo = f"https:{home_logo}"
            elif home_logo.startswith('/'):
                home_logo = f"https://a.espncdn.com{home_logo}"
        
        if away_logo and not away_logo.startswith('http'):
            if away_logo.startswith('//'):
                away_logo = f"https:{away_logo}"
            elif away_logo.startswith('/'):
                away_logo = f"https://a.espncdn.com{away_logo}"
        
        if match_url and not match_url.startswith('http'):
            if match_url.startswith('/'):
                match_url = f"https://www.espn.com{match_url}"
            else:
                match_url = f"https://www.espn.com/{match_url}"
        
        # Standardiser les compétitions
        competition_mapping = {
            'Brazilian Serie A': 'BRA.1',
            'Brazilian Serie B': 'BRA.2',
            'Brazilian Serie C': 'BRA.3',
            'CONMEBOL Libertadores': 'CONMEBOL.LIBERTADORES',
            'CONMEBOL Sudamericana': 'CONMEBOL.SUDAMERICANA',
            'Copa do Brasil': 'BRA.COPA_DO_BRAZIL',
            'Copa do Nordeste': 'BRA.COPA_DO_NORDESTE'
        }
        
        for key, value in competition_mapping.items():
            if key in competition:
                competition = value
                break
        
        return {
            'date': date,
            'month': month,
            'home_team': home_team,
            'home_abbreviation': home_abbr,
            'home_team_id': home_team_id,
            'home_score': home_score,
            'home_logo_url': home_logo,
            'away_team': away_team,
            'away_abbreviation': away_abbr,
            'away_team_id': away_team_id,
            'away_score': away_score,
            'away_logo_url': away_logo,
            'match_url': match_url,
            'match_id': match_id,
            'result': result,
            'competition': competition,
            'season': '2025'
        }
        
    except Exception as e:
        print(f"⚠️ Erreur extraction: {str(e)[:100]}")
        return None

def scrape_with_selenium():
    """Scrape les données avec Selenium"""
    driver = None
    all_matches = []
    
    try:
        print("🚀 Démarrage du navigateur (headless)...")
        driver = setup_driver()
        print("✅ Navigateur démarré")
        
        url = "https://www.espn.com/soccer/team/results/_/id/6272/season/2025"
        print(f"🌐 Accès: {url}")
        
        # Charger la page
        driver.get(url)
        print("⏳ Attente du chargement initial...")
        time.sleep(5)
        
        # Attendre que le contenu soit chargé
        print("⏳ Attente des éléments...")
        try:
            # Attendre que le body soit chargé
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Faire défiler la page pour charger tout le contenu
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
            # Essayer d'attendre les tableaux
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "ResponsiveTable"))
            )
        except TimeoutException:
            print("⚠️ Timeout: certains éléments peuvent ne pas être chargés")
        
        # Sauvegarder le HTML pour débogage
        with open('page_source.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("💾 HTML sauvegardé dans 'page_source.html'")
        
        # Chercher les tableaux avec différents sélecteurs
        result_tables = []
        
        # Essayer différents sélecteurs
        selectors = [
            "div.ResponsiveTable.Table__results-mobile",
            "div.ResponsiveTable",
            "table.Table",
            "div.Results div.ResponsiveTable"
        ]
        
        for selector in selectors:
            tables = driver.find_elements(By.CSS_SELECTOR, selector)
            if tables:
                print(f"✅ Trouvé {len(tables)} tableaux avec: {selector}")
                result_tables = tables
                break
        
        if not result_tables:
            # Chercher manuellement
            print("🔍 Recherche manuelle des tableaux...")
            all_divs = driver.find_elements(By.TAG_NAME, "div")
            for div in all_divs:
                classes = div.get_attribute("class") or ""
                if "Table" in classes and "results" in classes.lower():
                    result_tables.append(div)
                    print(f"✅ Trouvé un tableau avec classes: {classes}")
        
        print(f"📊 {len(result_tables)} tableaux trouvés")
        
        if not result_tables:
            print("❌ Aucun tableau trouvé. Vérification du contenu...")
            # Vérifier si la page contient du texte
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "Fortaleza" in body_text:
                print("✅ La page contient 'Fortaleza' mais les tableaux ne sont pas chargés")
            else:
                print("⚠️ La page ne contient pas de données Fortaleza")
            
            # Sauvegarder une capture d'écran
            driver.save_screenshot("page_screenshot.png")
            print("💾 Capture d'écran sauvegardée")
            return []
        
        for table in result_tables:
            # Récupérer le titre du mois
            month_element = table.find_element(By.CLASS_NAME, "Table__Title") if table.find_elements(By.CLASS_NAME, "Table__Title") else None
            month = month_element.text.strip() if month_element else "Unknown"
            print(f"📅 Traitement: {month}")
            
            # Récupérer toutes les lignes
            rows = table.find_elements(By.CSS_SELECTOR, "tr.Table__TR.Table__TR--sm.Table__even")
            print(f"   {len(rows)} matchs trouvés")
            
            for row in rows:
                match_data = extract_match_info(row, month)
                if match_data:
                    all_matches.append(match_data)
        
        # Filtrer les doublons
        unique_matches = []
        seen = set()
        for match in all_matches:
            key = f"{match['match_id']}_{match['date']}"
            if key not in seen and match['match_id']:
                seen.add(key)
                unique_matches.append(match)
        
        print(f"✅ {len(unique_matches)} matchs uniques")
        
        # Sauvegarder
        output = {
            'team_name': 'Fortaleza',
            'team_id': '6272',
            'season': '2025',
            'total_matches': len(unique_matches),
            'matches': unique_matches,
            'scraped_at': datetime.now().isoformat()
        }
        
        with open('newdb.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print("💾 newdb.json sauvegardé")
        return unique_matches
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        
        # Sauvegarder le HTML en cas d'erreur
        try:
            if driver:
                with open('error_page.html', 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                driver.save_screenshot("error_screenshot.png")
                print("💾 Page HTML et screenshot sauvegardés pour débogage")
        except:
            pass
        
        return []
    finally:
        if driver:
            print("🧹 Fermeture du navigateur...")
            driver.quit()

def main():
    print("=" * 60)
    print("⚽ ESPN SCRAPER - FORTALEZA RESULTS (GitHub Actions)")
    print("=" * 60)
    
    results = scrape_with_selenium()
    
    if results:
        print(f"\n✅ {len(results)} matchs récupérés")
        competitions = {}
        for match in results:
            comp = match['competition']
            competitions[comp] = competitions.get(comp, 0) + 1
        
        print("\n📈 Statistiques:")
        for comp, count in sorted(competitions.items(), key=lambda x: x[1], reverse=True):
            print(f"  {comp}: {count} matchs")
    else:
        print("\n❌ Aucune donnée récupérée")
        # Ne pas échouer en exit 1 pour éviter de bloquer le workflow
        # sys.exit(1)

if __name__ == "__main__":
    main()