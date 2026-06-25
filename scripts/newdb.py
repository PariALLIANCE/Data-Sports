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

def clean_team_id(team_id):
    """Nettoie l'ID de l'équipe pour ne garder que le nombre"""
    if not team_id:
        return ""
    # Si l'ID contient un slash, ne garder que la partie avant
    if '/' in team_id:
        team_id = team_id.split('/')[0]
    # Si l'ID contient des lettres, ne garder que les chiffres
    match = re.search(r'(\d+)', team_id)
    return match.group(1) if match else team_id

def clean_match_id(match_id):
    """Nettoie l'ID du match pour ne garder que le nombre"""
    if not match_id:
        return ""
    # Si l'ID contient un slash, ne garder que la partie avant
    if '/' in match_id:
        match_id = match_id.split('/')[0]
    # Si l'ID contient des lettres, ne garder que les chiffres
    match = re.search(r'(\d+)', match_id)
    return match.group(1) if match else match_id

def extract_match_info(match_row, month):
    """Extrait les informations d'un match"""
    try:
        cells = match_row.find_elements(By.TAG_NAME, 'td')
        if len(cells) < 6:
            return None
        
        # Date
        date_element = cells[0].find_element(By.CLASS_NAME, 'matchTeams') if cells[0].find_elements(By.CLASS_NAME, 'matchTeams') else None
        date = date_element.text.strip() if date_element else ""
        
        # Score et équipes (cellule 2)
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
            # Équipe domicile
            home_link = score_links[0]
            home_team = home_link.text.strip()
            home_url = home_link.get_attribute('href') or ""
            # Extraire l'ID de l'équipe depuis l'URL
            home_id_match = re.search(r'/id/(\d+)/', home_url)
            home_team_id = home_id_match.group(1) if home_id_match else ""
            
            # Score
            score_link = score_links[1]
            score_text = score_link.text.strip()
            match_url = score_link.get_attribute('href') or ""
            # Extraire l'ID du match
            match_id_match = re.search(r'/gameId/(\d+)', match_url)
            match_id = match_id_match.group(1) if match_id_match else ""
            
            # Extraire le score
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
            
            # Équipe extérieure
            away_link = score_links[2]
            away_team = away_link.text.strip()
            away_url = away_link.get_attribute('href') or ""
            away_id_match = re.search(r'/id/(\d+)/', away_url)
            away_team_id = away_id_match.group(1) if away_id_match else ""
        
        # Logos
        if len(images) >= 2:
            home_logo = images[0].get_attribute('src') or ""
            away_logo = images[1].get_attribute('src') or ""
        
        # Résultat
        result_elements = cells[4].find_elements(By.TAG_NAME, 'span')
        for elem in result_elements:
            if 'FT' in elem.text or 'Pens' in elem.text:
                result = elem.text.strip()
                break
        
        # Compétition (garder le nom complet)
        competition_elements = cells[5].find_elements(By.TAG_NAME, 'span')
        if competition_elements:
            competition = competition_elements[-1].text.strip()
        
        # Nettoyer les URLs des logos
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
        
        # Nettoyer l'URL du match
        if match_url and not match_url.startswith('http'):
            if match_url.startswith('/'):
                match_url = f"https://www.espn.com{match_url}"
            else:
                match_url = f"https://www.espn.com/{match_url}"
        
        return {
            'date': date,
            'month': month,
            'home_team': home_team,
            'home_team_id': home_team_id,
            'home_score': home_score,
            'home_logo_url': home_logo,
            'away_team': away_team,
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
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Faire défiler la page pour charger tout le contenu
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "ResponsiveTable"))
            )
        except TimeoutException:
            print("⚠️ Timeout: certains éléments peuvent ne pas être chargés")
        
        # Chercher les tableaux avec différents sélecteurs
        result_tables = []
        
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
            print("🔍 Recherche manuelle des tableaux...")
            all_divs = driver.find_elements(By.TAG_NAME, "div")
            for div in all_divs:
                classes = div.get_attribute("class") or ""
                if "Table" in classes and "results" in classes.lower():
                    result_tables.append(div)
                    print(f"✅ Trouvé un tableau avec classes: {classes}")
        
        print(f"📊 {len(result_tables)} tableaux trouvés")
        
        if not result_tables:
            print("❌ Aucun tableau trouvé.")
            return []
        
        for table in result_tables:
            month_element = table.find_element(By.CLASS_NAME, "Table__Title") if table.find_elements(By.CLASS_NAME, "Table__Title") else None
            month = month_element.text.strip() if month_element else "Unknown"
            print(f"📅 Traitement: {month}")
            
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
        
        print("\n📈 Statistiques par compétition:")
        for comp, count in sorted(competitions.items(), key=lambda x: x[1], reverse=True):
            print(f"  {comp}: {count} matchs")
    else:
        print("\n❌ Aucune donnée récupérée")

if __name__ == "__main__":
    main()