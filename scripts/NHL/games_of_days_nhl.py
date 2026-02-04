import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os

# ================= CONFIG =================
BASE_URL = "https://www.espn.com/nhl/schedule/_/date/"
OUTPUT_PATH = "data/hockey/games_of_day_nhl.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ==========================================

def get_today_url():
    today = datetime.now().strftime("%Y%m%d")
    return BASE_URL + today, today


def clean_text(text):
    return text.replace("\n", "").strip()


def get_games_of_day():
    url, today_str = get_today_url()
    res = requests.get(url, headers=HEADERS, timeout=15)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    games = []

    # Tables contenant les matchs à venir (TIME)
    tables = soup.select("table.Table")

    for table in tables:
        headers = [th.get_text(strip=True).lower() for th in table.select("thead th")]

        # On garde uniquement les tables avec colonne TIME
        if "time" not in headers:
            continue

        rows = table.select("tbody tr")

        for row in rows:
            teams = row.select(".Table__Team a[href*='/nhl/team']")
            if len(teams) < 2:
                continue

            # Équipes
            away_team = clean_text(teams[0].get_text())
            home_team = clean_text(teams[1].get_text())

            away_url = "https://www.espn.com" + teams[0]["href"]
            home_url = "https://www.espn.com" + teams[1]["href"]

            # Logos
            logos = row.select("img.team__logo")
            away_logo = logos[0]["src"] if len(logos) > 0 else None
            home_logo = logos[1]["src"] if len(logos) > 1 else None

            # Heure + lien du match
            time_cell = row.select_one("td.date__col a")
            if not time_cell:
                continue

            match_time = clean_text(time_cell.get_text())
            match_url = "https://www.espn.com" + time_cell["href"]

            game = {
                "date": today_str,
                "time": match_time,
                "match": f"{away_team} v {home_team}",
                "score": "v",
                "away": {
                    "name": away_team,
                    "url": away_url,
                    "logo": away_logo
                },
                "home": {
                    "name": home_team,
                    "url": home_url,
                    "logo": home_logo
                },
                "match_url": match_url
            }

            games.append(game)

    return {
        "source": "ESPN",
        "league": "NHL",
        "date": today_str,
        "games_count": len(games),
        "games": games
    }


def save_json(data):
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    data = get_games_of_day()
    save_json(data)
    print(f"✅ {data['games_count']} matchs NHL à venir enregistrés dans {OUTPUT_PATH}")