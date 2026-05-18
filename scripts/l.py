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

OUTPUT_DIR = "data/football/leagues"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === LIGUES ===
LEAGUES = {
    "FA_Cup": {
        "id": "eng.fa",
        "json": "FA_Cup.json"
    }
}

# URL résultats africa.espn
BASE_URL = "https://africa.espn.com/football/results/_/date/{date}/league/{league}"

# === PÉRIODE : 30 jours test ===
START_DATE = datetime(2023, 1, 1, tzinfo=timezone.utc)
END_DATE = datetime(2023, 1, 30, tzinfo=timezone.utc)

# =============================
# 🔍 STATS PAR GAMEID
# =============================

def get_match_stats(game_id):
    url = f"https://africa.espn.com/football/match/_/gameId/{game_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"
    }

    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")

        stats_section = soup.find("section", {"data-testid": "prism-LayoutCard"})
        if not stats_section:
            print(f"  ⚠️ Pas de section stats pour gameId {game_id}")
            return {}

        stats = {}
        stat_rows = stats_section.find_all("div", class_="LOSQp")

        if not stat_rows:
            print(f"  ⚠️ Pas de lignes stats pour gameId {game_id}")

        for row in stat_rows:
            name_tag = row.find("span", class_="OkRBU")
            values = row.find_all("span", class_="bLeWt")

            if name_tag and len(values) >= 2:
                stats[name_tag.text.strip()] = {
                    "home": values[0].text.strip(),
                    "away": values[1].text.strip()
                }

        time.sleep(0.8)
        return stats

    except Exception as e:
        print(f"❌ Erreur stats match {game_id} : {e}")
        return {}

# =============================
# SCRAPING
# =============================

for league_name, league_info in LEAGUES.items():
    print(f"\n🏆 Traitement {league_name}")
    all_matches = {}

    current_date = START_DATE
    while current_date <= END_DATE:
        date_str = current_date.strftime("%Y%m%d")
        url = BASE_URL.format(date=date_str, league=league_info["id"])
        print(f"📅 {league_name} - {date_str} → {url}")

        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception as e:
            print(f"⚠️ Erreur réseau ({date_str}) : {e}")
            current_date += timedelta(days=1)
            continue

        tables = soup.select("div.ResponsiveTable")
        print(f"  → {len(tables)} table(s) trouvée(s)")

        # Debug : aperçu HTML si aucune table
        if not tables:
            print(f"  ⚠️ HTML reçu (500 premiers chars) :\n{res.text[:500]}\n")

        for table in tables:
            date_title_tag = table.select_one("div.Table__Title")
            date_text = date_title_tag.text.strip() if date_title_tag else date_str

            rows = table.select("tbody > tr.Table__TR")
            print(f"  → {len(rows)} ligne(s) dans la table")

            for row in rows:
                try:
                    teams = row.select("span.Table__Team a.AnchorLink:last-child")
                    score_tag = row.select_one("a.AnchorLink.at")

                    if len(teams) != 2 or not score_tag:
                        continue

                    team1 = teams[0].text.strip()
                    team2 = teams[1].text.strip()
                    score = score_tag.text.strip()

                    if score.lower() == "v":
                        continue

                    match_url = score_tag["href"]
                    match_id_match = re.search(r"gameId/(\d+)", match_url)
                    if not match_id_match:
                        continue

                    game_id = match_id_match.group(1)
                    print(f"  ✅ Match trouvé : {team1} vs {team2} | Score : {score} | gameId : {game_id}")

                    stats = get_match_stats(game_id)
                    print(f"  📊 Stats : {stats if stats else 'vides'}")

                    if game_id in all_matches:
                        if not all_matches[game_id].get("stats") and stats:
                            all_matches[game_id]["stats"] = stats
                        continue

                    all_matches[game_id] = {
                        "gameId": game_id,
                        "date": date_text,
                        "team1": team1,
                        "team2": team2,
                        "score": score,
                        "title": f"{team1} VS {team2}",
                        "match_url": "https://africa.espn.com" + match_url,
                        "stats": stats
                    }

                except Exception as e:
                    print(f"⚠️ Parsing ({date_str}) : {e}")

        current_date += timedelta(days=1)
        time.sleep(1)

    output_path = os.path.join(OUTPUT_DIR, league_info["json"])
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(list(all_matches.values()), f, indent=2, ensure_ascii=False)

    print(f"\n💾 {output_path} généré : {len(all_matches)} matchs")
    if all_matches:
        print("📋 Aperçu premier match :")
        print(json.dumps(list(all_matches.values())[0], indent=2, ensure_ascii=False))