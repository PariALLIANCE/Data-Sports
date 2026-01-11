import requests
from bs4 import BeautifulSoup
import json
import os
import time

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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Referer": "https://www.espn.com/",
    "Upgrade-Insecure-Requests": "1"
}

BASE_DIR = "data/football/standings"
os.makedirs(BASE_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(BASE_DIR, "Standings.json")

def fetch_page(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text

def parse_standings(html):
    soup = BeautifulSoup(html, "html.parser")
    teams_rows = soup.select("table.Table--fixed-left tbody tr")
    stats_rows = soup.select(".Table__Scroller table tbody tr")
    standings = []

    for i in range(min(len(teams_rows), len(stats_rows))):
        team_row = teams_rows[i]
        stat_row = stats_rows[i]

        team_div = team_row.select_one("div.team-link")
        if not team_div:
            continue

        # Position
        pos_tag = team_div.select_one(".team-position")
        position = int(pos_tag.text.strip()) if pos_tag else i + 1

        # Nom
        name_tag = team_div.select_one(".hide-mobile a")
        name = name_tag.text.strip() if name_tag else None

        # Stats
        tds = [td.text.strip() for td in stat_row.select("td")]
        if len(tds) < 8:
            continue

        gp, w, d, l, f, a, gd, p = tds[:8]

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
                "GD": int(gd.replace("+", "")),
                "P": int(p)
            }
        })
    return standings

def scrape_all_leagues():
    all_data = {}
    for league_name, league_id in LEAGUES.items():
        try:
            print(f"🔹 Scraping {league_name}...")
            url = f"https://www.espn.com/soccer/standings/_/league/{league_id}"
            html = fetch_page(url)
            data = parse_standings(html)
            all_data[league_name] = data
            print(f"✔ {len(data)} équipes enregistrées pour {league_name}\n")
            time.sleep(1)  # anti-block
        except Exception as e:
            print(f"❌ Erreur pour {league_name}: {e}")

    # Sauvegarde
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)
    print(f"\n✅ Tous les classements enregistrés dans {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_all_leagues()