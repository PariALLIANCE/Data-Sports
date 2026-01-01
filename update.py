import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta, timezone
import re
import time
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
}

# === DOSSIER DE SORTIE ===
OUTPUT_DIR = "data/football/leagues"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === LIGUES (LIMITÉES) ===
LEAGUES = {
    "Premier League": {
        "id": "eng.1",
        "json": "England_Premier_League.json"
    },
    "LaLiga": {
        "id": "esp.1",
        "json": "Spain_Laliga.json"
    },
    "Bundesliga": {
        "id": "ger.1",
        "json": "Germany_Bundesliga.json"
    },
    "Argentina - Primera Nacional": {
        "id": "arg.2",
        "json": "Argentina_Primera_Nacional.json"
    },
    "Austria - Bundesliga": {
        "id": "aut.1",
        "json": "Austria_Bundesliga.json"
    },
    "Belgium - Jupiler Pro League": {
        "id": "bel.1",
        "json": "Belgium_Jupiler_Pro_League.json"
    }
}


# === DATES : AVANT-HIER & HIER ===
dates_to_fetch = [
    (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y%m%d"),
    (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y%m%d"),
]

# =============================
# 🔍 STATS PAR GAMEID
# =============================

def get_match_stats(game_id):
    url = f"https://africa.espn.com/football/match/_/gameId/{game_id}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"
    }

    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        stats_section = soup.find("section", {"data-testid": "prism-LayoutCard"})
        if not stats_section:
            return {}

        stats = {}
        for row in stats_section.find_all("div", class_="LOSQp"):
            name_tag = row.find("span", class_="OkRBU")
            values = row.find_all("span", class_="bLeWt")
            if name_tag and len(values) >= 2:
                stats[name_tag.text.strip()] = {
                    "home": values[0].text.strip(),
                    "away": values[1].text.strip()
                }

        time.sleep(0.6)
        return stats

    except Exception:
        return {}

# =============================
# UTILS JSON
# =============================

def load_existing_matches(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {m["gameId"]: m for m in data if "gameId" in m}
    except Exception:
        return {}

# =============================
# SCRAPING INCRÉMENTAL
# =============================

for league_name, league in LEAGUES.items():
    print(f"\n🏆 {league_name}")
    BASE_URL = f"https://www.espn.com/soccer/schedule/_/date/{{date}}/league/{league['id']}"
    json_path = os.path.join(OUTPUT_DIR, league["json"])

    matches = load_existing_matches(json_path)
    new_count = 0
    stats_updated = 0

    for date_str in dates_to_fetch:
        print(f"📅 {date_str}")

        try:
            res = requests.get(BASE_URL.format(date=date_str), headers=HEADERS, timeout=15)
            soup = BeautifulSoup(res.content, "html.parser")
        except Exception:
            continue

        for table in soup.select("div.ResponsiveTable"):
            date_title = table.select_one("div.Table__Title")
            date_text = date_title.text.strip() if date_title else date_str

            for row in table.select("tbody > tr.Table__TR"):
                teams = row.select("span.Table__Team a.AnchorLink:last-child")
                score_tag = row.select_one("a.AnchorLink.at")

                if len(teams) != 2 or not score_tag:
                    continue

                score = score_tag.text.strip()
                if score.lower() == "v":
                    continue

                match_id = re.search(r"gameId/(\d+)", score_tag["href"])
                if not match_id:
                    continue

                game_id = match_id.group(1)

                # === MATCH EXISTANT : enrichissement stats uniquement ===
                if game_id in matches:
                    if not matches[game_id].get("stats"):
                        stats = get_match_stats(game_id)
                        if stats:
                            matches[game_id]["stats"] = stats
                            stats_updated += 1
                    continue

                # === NOUVEAU MATCH ===
                stats = get_match_stats(game_id)

                matches[game_id] = {
                    "gameId": game_id,
                    "date": date_text,
                    "team1": teams[0].text.strip(),
                    "team2": teams[1].text.strip(),
                    "score": score,
                    "title": f"{teams[0].text.strip()} VS {teams[1].text.strip()}",
                    "match_url": "https://www.espn.com" + score_tag["href"],
                    "stats": stats
                }
                new_count += 1

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(list(matches.values()), f, indent=2, ensure_ascii=False)

    print(f"💾 {league_name} : {len(matches)} matchs | +{new_count} | stats MAJ {stats_updated}")