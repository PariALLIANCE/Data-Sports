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

LEAGUES = {
    "FA_Cup": {"id": "eng.fa", "json": "FA_Cup.json"},
    "EFL_Cup": {"id": "eng.league_cup", "json": "EFL_Cup.json"},
    "Copa_del_Rey": {"id": "esp.copa_del_rey", "json": "Copa_del_Rey.json"},
    "DFB_Pokal": {"id": "ger.dfb_pokal", "json": "DFB_Pokal.json"},
    "Coppa_Italia": {"id": "ita.coppa_italia", "json": "Coppa_Italia.json"},
    "Coupe_de_France": {"id": "fra.coupe_de_france", "json": "Coupe_de_France.json"},
    "KNVB_Cup": {"id": "ned.cup", "json": "KNVB_Cup.json"},
    "Taca_de_Portugal": {"id": "por.taca.portugal", "json": "Taca_de_Portugal.json"},
    "Kings_Cup_Saudi": {"id": "ksa.kings.cup", "json": "Kings_Cup_Saudi.json"}
}

# === DATES : 1er janvier 2023 → aujourd'hui ===
START_DATE = datetime(2023, 1, 1, tzinfo=timezone.utc)
END_DATE   = datetime.now(timezone.utc)

# =============================
# UTILS
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
# STATS
# =============================

def get_match_stats(game_id):
    url = f"https://www.espn.com/soccer/match/_/gameId/{game_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
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
            values   = row.find_all("span", class_="bLeWt")
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
# COTES ESPN
# =============================

def us_to_decimal(odds_str):
    if not odds_str:
        return None
    try:
        val = int(odds_str.replace("+", "").strip())
        return round(1 + (val / 100), 2) if val > 0 else round(1 + (100 / abs(val)), 2)
    except Exception:
        return None

def is_valid_us_odds(val):
    if not val:
        return False
    try:
        int(val.replace("+", "").replace("-", ""))
        return True
    except Exception:
        return False

def extract_odds(game_id):
    match_url = f"https://www.espn.com/soccer/match/_/gameId/{game_id}"
    try:
        res = requests.get(match_url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        cells = soup.find_all("div", {"data-testid": "OddsCell"})

        if len(cells) < 7:
            return None

        home_us = cells[0].get_text(strip=True) or None
        away_us = cells[3].get_text(strip=True) or None
        draw_us = cells[6].get_text(strip=True) or None

        if not all(is_valid_us_odds(v) for v in [home_us, away_us, draw_us]):
            return None

        return {
            "home": us_to_decimal(home_us),
            "away": us_to_decimal(away_us),
            "draw": us_to_decimal(draw_us),
        }
    except Exception as e:
        print(f"    ⚠️  Erreur cotes : {e}")
        return None

# =============================
# SCRAPING PAR LIGUE
# =============================

for league_name, league in LEAGUES.items():
    print(f"\n🏆 {league_name}")

    BASE_URL  = "https://www.espn.com/soccer/schedule/_/date/{date}/league/" + league["id"]
    json_path = os.path.join(OUTPUT_DIR, league["json"])
    matches   = load_existing_matches(json_path)

    new_count     = 0
    stats_updated = 0

    current_date = START_DATE
    while current_date <= END_DATE:
        date_str = current_date.strftime("%Y%m%d")
        print(f"  📅 {date_str}")

        try:
            res  = requests.get(BASE_URL.format(date=date_str), headers=HEADERS, timeout=15)
            soup = BeautifulSoup(res.content, "html.parser")
        except Exception as e:
            print(f"    ⚠️  Erreur requête : {e}")
            current_date += timedelta(days=1)
            continue

        for table in soup.select("div.ResponsiveTable"):
            date_title = table.select_one("div.Table__Title")
            date_text  = date_title.text.strip() if date_title else date_str

            for row in table.select("tbody > tr.Table__TR"):
                teams     = row.select("span.Table__Team a.AnchorLink:last-child")
                score_tag = row.select_one("a.AnchorLink.at")

                if len(teams) != 2 or not score_tag:
                    continue

                score = score_tag.text.strip()
                if score.lower() == "v":
                    continue

                match_href = score_tag.get("href", "")
                match_id   = re.search(r"gameId/(\d+)", match_href)
                if not match_id:
                    continue

                game_id   = match_id.group(1)
                match_url = (
                    "https://www.espn.com" + match_href
                    if match_href.startswith("/")
                    else match_href
                )

                # ── Match existant : enrichir stats/cotes si manquantes ────
                if game_id in matches:
                    if not matches[game_id].get("stats"):
                        stats = get_match_stats(game_id)
                        if stats:
                            matches[game_id]["stats"] = stats
                            stats_updated += 1
                    if not matches[game_id].get("odds"):
                        odds = extract_odds(game_id)
                        if odds:
                            matches[game_id]["odds"] = odds
                    continue

                # ── Nouveau match : stats + cotes ──────────────────────────
                stats = get_match_stats(game_id)
                odds  = extract_odds(game_id)
                time.sleep(1)

                match_data = {
                    "gameId":    game_id,
                    "date":      date_text,
                    "team1":     teams[0].text.strip(),
                    "team2":     teams[1].text.strip(),
                    "score":     score,
                    "title":     f"{teams[0].text.strip()} VS {teams[1].text.strip()}",
                    "match_url": match_url,
                    "stats":     stats,
                }
                if odds:
                    match_data["odds"] = odds

                matches[game_id] = match_data
                new_count += 1

                status = f"{odds['home']} / {odds['draw']} / {odds['away']}" if odds else "pas de cotes"
                print(f"    ✅ {teams[0].text.strip()} vs {teams[1].text.strip()} → {status}")

        current_date += timedelta(days=1)
        time.sleep(1)

    # ── Sauvegarde atomique ────────────────────────────────────────────────
    tmp_path = json_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(list(matches.values()), f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, json_path)

    print(f"  💾 {league_name} : {len(matches)} matchs | +{new_count} nouveaux | stats MAJ {stats_updated}")