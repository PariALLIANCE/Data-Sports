import json
from datetime import datetime, timezone
import re
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup, NavigableString
from webdriver_manager.chrome import ChromeDriverManager

# ===============================================================
# DRIVER
# ===============================================================

def make_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_argument("--lang=en-US")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    driver.implicitly_wait(10)
    return driver

def get_soup(driver, url, wait_selector=None, timeout=15):
    driver.get(url)
    if wait_selector:
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
            )
        except Exception:
            pass
    return BeautifulSoup(driver.page_source, "html.parser")

# ===============================================================
# CONSTANTES
# ===============================================================

BASE_URL = "https://www.espn.com/soccer/team/results/_/id/6272/season/2025"
OUTPUT_FILE = "newdb.json"
TEAM_ID = "6272"
TEAM_NAME = "Fortaleza"

# ===============================================================
# UTILITAIRES
# ===============================================================

def convert_date_to_iso(date_text):
    """Convertit une date ESPN en format ISO"""
    try:
        # Format: "Sun, Dec 7" -> on ajoute l'année
        if date_text:
            # Essayer différents formats
            formats = [
                "%a, %b %d",
                "%A, %B %d",
                "%a, %B %d",
                "%A, %b %d",
                "%b %d, %Y",
                "%B %d, %Y"
            ]
            for fmt in formats:
                try:
                    # Ajouter l'année si nécessaire
                    if "%Y" not in fmt:
                        date_text_with_year = f"{date_text}, 2025"
                        dt = datetime.strptime(date_text_with_year, f"{fmt}, %Y")
                    else:
                        dt = datetime.strptime(date_text, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
    except Exception:
        pass
    return date_text

def clean_competition(comp_text):
    """Standardise les noms des compétitions"""
    mapping = {
        'Brazilian Serie A': 'BRA.1',
        'Brazilian Serie B': 'BRA.2',
        'Brazilian Serie C': 'BRA.3',
        'CONMEBOL Libertadores': 'CONMEBOL.LIBERTADORES',
        'CONMEBOL Sudamericana': 'CONMEBOL.SUDAMERICANA',
        'Copa do Brasil': 'BRA.COPA_DO_BRAZIL',
        'Copa do Nordeste': 'BRA.COPA_DO_NORDESTE'
    }
    for key, value in mapping.items():
        if key in comp_text:
            return value
    return comp_text

def extract_team_id_from_url(url):
    """Extrait l'ID de l'équipe depuis une URL ESPN"""
    if not url:
        return None
    match = re.search(r'/id/(\d+)/', url)
    return match.group(1) if match else None

def build_team_url(team_id):
    """Construit l'URL de l'équipe"""
    if not team_id:
        return None
    return f"https://www.espn.com/soccer/team/_/id/{team_id}"

def clean_logo_url(logo_url):
    """Nettoie l'URL du logo"""
    if not logo_url:
        return None
    if logo_url.startswith('//'):
        return f"https:{logo_url}"
    if logo_url.startswith('/'):
        return f"https://a.espncdn.com{logo_url}"
    return logo_url

def extract_team_id_from_logo(logo_url):
    """Extrait l'ID de l'équipe depuis l'URL du logo"""
    if not logo_url:
        return None
    match = re.search(r'/(\d+)\.png', logo_url)
    return match.group(1) if match else None

def read_direct_text(tag):
    """Lit le texte direct d'une balise (sans les enfants)"""
    if not tag:
        return None
    parts = []
    for child in tag.children:
        if isinstance(child, NavigableString):
            t = str(child).strip()
            if t:
                parts.append(t)
    result = "".join(parts).strip()
    return result if result else None

# ===============================================================
# EXTRACTION DES MATCHS
# ===============================================================

def extract_match_info(row, month):
    """Extrait les informations d'un match depuis une ligne de tableau"""
    try:
        cells = row.find_all('td')
        if len(cells) < 6:
            return None
        
        # Date
        date_element = cells[0].find('div', class_='matchTeams')
        date = date_element.text.strip() if date_element else ""
        
        # Équipe domicile (abréviation)
        home_abbr_element = cells[1].find('a', class_='Table__Team')
        home_abbr = home_abbr_element.text.strip() if home_abbr_element else ""
        
        # Cellule du score
        score_cell = cells[2]
        score_links = score_cell.find_all('a')
        images = score_cell.find_all('img')
        
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
        
        if len(score_links) >= 3:
            # Équipe domicile
            home_link = score_links[0]
            home_team = home_link.text.strip()
            home_url = home_link.get('href') or ""
            home_team_id = extract_team_id_from_url(home_url)
            
            # Score
            score_link = score_links[1]
            score_text = score_link.text.strip()
            match_url = score_link.get('href') or ""
            
            # Extraction de l'ID du match
            match_id_match = re.search(r'/gameId/(\d+)', match_url)
            if match_id_match:
                match_id = match_id_match.group(1)
            
            # Extraire le score
            score_pattern = re.search(r'(\d+)\s*[-:]\s*(\d+)', score_text)
            if score_pattern:
                home_score = score_pattern.group(1)
                away_score = score_pattern.group(2)
            else:
                # Essayer avec un autre format
                parts = score_text.split(' - ')
                if len(parts) == 2:
                    home_score = parts[0].strip()
                    away_score = parts[1].strip()
                elif 'FT' in score_text:
                    result = 'FT'
                elif 'Pens' in score_text:
                    result = 'FT-Pens'
            
            # Équipe extérieure
            away_link = score_links[2]
            away_team = away_link.text.strip()
            away_url = away_link.get('href') or ""
            away_team_id = extract_team_id_from_url(away_url)
        
        # Logos
        if len(images) >= 2:
            home_logo = clean_logo_url(images[0].get('src'))
            away_logo = clean_logo_url(images[1].get('src'))
        
        # Si les IDs ne sont pas trouvés via les URLs, essayer via les logos
        if not home_team_id and home_logo:
            home_team_id = extract_team_id_from_logo(home_logo)
        if not away_team_id and away_logo:
            away_team_id = extract_team_id_from_logo(away_logo)
        
        # Équipe extérieure (abréviation)
        away_abbr_element = cells[3].find('a', class_='Table__Team')
        away_abbr = away_abbr_element.text.strip() if away_abbr_element else ""
        
        # Résultat
        result_elements = cells[4].find_all('span')
        for elem in result_elements:
            text = elem.text.strip()
            if 'FT' in text or 'Pens' in text:
                result = text
                break
        
        # Compétition
        competition_elements = cells[5].find_all('span')
        competition = ""
        if competition_elements:
            competition = competition_elements[-1].text.strip()
            competition = clean_competition(competition)
        
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
        print(f"  ⚠️ Erreur extraction match: {str(e)[:100]}")
        return None

# ===============================================================
# SCRAPING PRINCIPAL
# ===============================================================

def scrape_fortaleza_results():
    """Scrape les résultats de Fortaleza"""
    driver = None
    all_matches = []
    
    try:
        print("🚀 Démarrage du navigateur (headless)...")
        driver = make_driver()
        print("✅ Navigateur démarré")
        
        print(f"🌐 Accès: {BASE_URL}")
        
        # Charger la page
        soup = get_soup(
            driver,
            BASE_URL,
            wait_selector="div.ResponsiveTable",
            timeout=20
        )
        print("✅ Page chargée")
        
        # Sauvegarder le HTML pour débogage (optionnel)
        # with open('debug_page.html', 'w', encoding='utf-8') as f:
        #     f.write(str(soup))
        
        # Trouver tous les tableaux de résultats
        result_tables = soup.select("div.ResponsiveTable.Table__results-mobile")
        
        if not result_tables:
            # Essayer avec un sélecteur plus large
            result_tables = soup.select("div.ResponsiveTable")
            
        if not result_tables:
            print("❌ Aucun tableau de résultats trouvé")
            # Vérifier si la page contient du texte
            if "Fortaleza" in str(soup):
                print("   La page contient 'Fortaleza' mais les tableaux ne sont pas trouvés")
                # Sauvegarder pour débogage
                with open('error_page.html', 'w', encoding='utf-8') as f:
                    f.write(str(soup))
            return []
        
        print(f"📊 {len(result_tables)} tableaux trouvés")
        
        for table in result_tables:
            # Récupérer le titre du mois
            month_element = table.find('div', class_='Table__Title')
            month = month_element.text.strip() if month_element else "Unknown"
            print(f"📅 Traitement: {month}")
            
            # Récupérer toutes les lignes
            rows = table.select("tr.Table__TR.Table__TR--sm.Table__even")
            print(f"   {len(rows)} matchs trouvés")
            
            for row in rows:
                match_data = extract_match_info(row, month)
                if match_data:
                    all_matches.append(match_data)
        
        # Filtrer les doublons
        print("\n🔍 Filtrage des doublons...")
        unique_matches = []
        seen = set()
        for match in all_matches:
            key = f"{match['match_id']}_{match['date']}"
            if key not in seen and match['match_id']:
                seen.add(key)
                unique_matches.append(match)
        
        print(f"✅ {len(unique_matches)} matchs uniques")
        
        # Construire le résultat final
        output = {
            'team_name': TEAM_NAME,
            'team_id': TEAM_ID,
            'season': '2025',
            'total_matches': len(unique_matches),
            'matches': unique_matches,
            'scraped_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Sauvegarde atomique
        tmp_file = OUTPUT_FILE + ".tmp"
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, OUTPUT_FILE)
        
        print(f"💾 {len(unique_matches)} matchs sauvegardés → {OUTPUT_FILE}")
        
        # Afficher un aperçu
        if unique_matches:
            print("\n📊 Aperçu des 5 premiers matchs:")
            for i, match in enumerate(unique_matches[:5]):
                home = match['home_abbreviation'] or match['home_team']
                away = match['away_abbreviation'] or match['away_team']
                print(f"  {i+1}. {home} ({match['home_score']}) - ({match['away_score']}) {away}")
                print(f"     🏆 {match['competition']} | 📅 {match['date']}")
        
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

# ===============================================================
# MAIN
# ===============================================================

def main():
    print("=" * 60)
    print("⚽ ESPN SCRAPER - FORTALEZA RESULTS")
    print("=" * 60)
    
    results = scrape_fortaleza_results()
    
    if results:
        print(f"\n✅ Scraping terminé avec succès!")
        print(f"📊 Total: {len(results)} matchs")
        
        # Statistiques par compétition
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