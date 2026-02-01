import os
import json
import re
import time
import requests
from bs4 import BeautifulSoup

# -------------------- CONFIG --------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9"
}

# FOOTBALL
FOOTBALL_BASE_URL = "https://www.espn.com/soccer/teams/_/league/"
FOOTBALL_LOGO_URL = "https://a.espncdn.com/i/teamlogos/soccer/500/{team_id}.png"
FOOTBALL_OUTPUT_DIR = "data/football/teams"
FOOTBALL_OUTPUT_FILE = "football_teams.json"

FOOTBALL_LEAGUES = {
  "England_Premier_League": { "id": "eng.1" },
  "Spain_Laliga": { "id": "esp.1" },
  "Germany_Bundesliga": { "id": "ger.1" },
  "Argentina_Primera_Nacional": { "id": "arg.2" },
  "Austria_Bundesliga": { "id": "aut.1" },
  "Belgium_Jupiler_Pro_League": { "id": "bel.1" },
  "Brazil_Serie_A": { "id": "bra.1" },
  "Brazil_Serie_B": { "id": "bra.2" },
  "Chile_Primera_Division": { "id": "chi.1" },
  "China_Super_League": { "id": "chn.1" },
  "Colombia_Primera_A": { "id": "col.1" },
  "England_National_League": { "id": "eng.5" },
  "France_Ligue_1": { "id": "fra.1" },
  "Greece_Super_League_1": { "id": "gre.1" },
  "Italy_Serie_A": { "id": "ita.1" },
  "Japan_J1_League": { "id": "jpn.1" },
  "Mexico_Liga_MX": { "id": "mex.1" },
  "Netherlands_Eredivisie": { "id": "ned.1" },
  "Paraguay_Division_Profesional": { "id": "par.1" },
  "Peru_Primera_Division": { "id": "per.1" },
  "Portugal_Primeira_Liga": { "id": "por.1" },
  "Romania_Liga_I": { "id": "rou.1" },
  "Russia_Premier_League": { "id": "rus.1" },
  "Saudi_Arabia_Pro_League": { "id": "ksa.1" },
  "Sweden_Allsvenskan": { "id": "swe.1" },
  "Switzerland_Super_League": { "id": "sui.1" },
  "Turkey_Super_Lig": { "id": "tur.1" },
  "USA_Major_League_Soccer": { "id": "usa.1" },
  "Venezuela_Primera_Division": { "id": "ven.1" },
  "UEFA_Champions_League": { "id": "uefa.champions" },
  "UEFA_Europa_League": { "id": "uefa.europa" },
  "FIFA_Club_World_Cup": { "id": "fifa.cwc" }
}
    # Ajoute ici d'autres ligues si nécessaire

# HOCKEY NHL
NHL_URL = "https://www.espn.com/nhl/teams"
NHL_OUTPUT_FILE = "data/hockey/teams/hockey_NHL_teams.json"

# -------------------- FONCTIONS --------------------
def get_football_teams_for_league(league_id):
    """Récupère les équipes d'une ligue de football ESPN."""
    url = FOOTBALL_BASE_URL + league_id
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    teams = []

    sections = soup.select("section.TeamLinks")
    for section in sections:
        name_tag = section.select_one("h2")
        link_tag = section.select_one("a[href*='/soccer/team/_/id/']")
        if not (name_tag and link_tag):
            continue

        team_name = name_tag.get_text(strip=True)
        match = re.search(r"/id/(\d+)", link_tag["href"])
        if not match:
            continue

        team_id = match.group(1)
        logo_url = FOOTBALL_LOGO_URL.format(team_id=team_id)
        teams.append({"team": team_name, "team_id": team_id, "logo": logo_url})

    return teams

def scrape_football_teams():
    """Scrape toutes les ligues de football et sauvegarde dans JSON."""
    all_leagues_data = {}
    for league_name, league_info in FOOTBALL_LEAGUES.items():
        league_id = league_info["id"]
        print(f"🏆 Football : Scraping {league_name} ({league_id})")
        try:
            teams = get_football_teams_for_league(league_id)
            all_leagues_data[league_name] = teams
            print(f"   → {len(teams)} équipes récupérées")
        except Exception as e:
            print(f"❌ Erreur pour {league_name} : {e}")
            all_leagues_data[league_name] = []
        time.sleep(1)

    os.makedirs(FOOTBALL_OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(FOOTBALL_OUTPUT_DIR, FOOTBALL_OUTPUT_FILE)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_leagues_data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Fichier football généré / écrasé : {output_path}")

def extract_nhl_team_id(href):
    """Extrait le team_id depuis l'URL NHL ESPN."""
    parts = href.strip("/").split("/")
    if "name" in parts:
        return parts[parts.index("name") + 1]
    return None

def scrape_nhl_teams():
    """Scrape toutes les équipes NHL et sauvegarde dans JSON."""
    response = requests.get(NHL_URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    teams = []
    for section in soup.select("section.TeamLinks"):
        link = section.find("a", href=True)
        name_tag = section.find("h2")
        if not (link and name_tag):
            continue
        team_id = extract_nhl_team_id(link["href"])
        if not team_id:
            continue
        logo_url = f"https://a.espncdn.com/i/teamlogos/nhl/500/{team_id}.png"
        teams.append({"team": name_tag.text.strip(), "team_id": team_id, "logo": logo_url})

    os.makedirs(os.path.dirname(NHL_OUTPUT_FILE), exist_ok=True)
    with open(NHL_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"NHL": teams}, f, indent=2, ensure_ascii=False)
    print(f"✅ {len(teams)} équipes NHL sauvegardées dans {NHL_OUTPUT_FILE}")

# -------------------- MAIN --------------------
if __name__ == "__main__":
    print("=== DÉBUT DU SCRAPING FOOTBALL ===")
    scrape_football_teams()
    print("\n=== DÉBUT DU SCRAPING NHL ===")
    scrape_nhl_teams()