import requests from bs4 import BeautifulSoup import json from datetime import datetime, timezone import re import os import time

HEADERS = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0" }

=== DOSSIER DE SORTIE ===

OUTPUT_DIR = "data/football" os.makedirs(OUTPUT_DIR, exist_ok=True) OUTPUT_FILE = os.path.join(OUTPUT_DIR, "games_of_day.json")

=== LIGUES LIMITÉES ===

LEAGUES = { "Premier League": "eng.1", "LaLiga": "esp.1", "Bundesliga": "ger.1", "Argentina - Primera Nacional": "arg.2", "Austria - Bundesliga": "aut.1", "Belgium - Jupiler Pro League": "bel.1" }

=== DATE DU JOUR ===

today_str = datetime.now(timezone.utc).strftime("%Y%m%d")

=== CONTENEUR DES MATCHS DU JOUR ===

games_of_day = {}

BASE_URL = "https://www.espn.com/soccer/schedule/_/date/{date}/league/{league}"

for league_name, league_code in LEAGUES.items(): print(f"📅 Récupération {league_name} ({today_str})")
try:       res = requests.get(BASE_URL.format(date=today_str, league=league_code), headers=HEADERS, timeout=15)       soup = BeautifulSoup(res.content, "html.parser")   except Exception as e:       print(f"⚠️ Erreur réseau {league_name}: {e}")       continue    for table in soup.select("div.ResponsiveTable"):       date_title = table.select_one("div.Table__Title")       date_text = date_title.text.strip() if date_title else today_str        for row in table.select("tbody > tr.Table__TR"):           teams = row.select("span.Table__Team a.AnchorLink:last-child")           score_tag = row.select_one("a.AnchorLink.at")            if len(teams) != 2 or not score_tag:               continue            score = score_tag.text.strip()            # ⚡ Match non joué uniquement           if score.lower() != "v":               continue            match_id = re.search(r"gameId/(\d+)", score_tag["href"])           if not match_id:               continue            game_id = match_id.group(1)            games_of_day[game_id] = {               "gameId": game_id,               "date": date_text,               "league": league_name,               "team1": teams[0].text.strip(),               "team2": teams[1].text.strip(),               "score": score,               "match_url": "https://www.espn.com" + score_tag["href"]           }            time.sleep(0.5)  # Respect du site   

=== ÉCRITURE DU JSON ===

with open(OUTPUT_FILE, "w", encoding="utf-8") as f: json.dump(list(games_of_day.values()), f, indent=2, ensure_ascii=False)

print(f"\n💾 {len(games_of_day)} matchs du jour sauvegardés dans {OUTPUT_FILE}")