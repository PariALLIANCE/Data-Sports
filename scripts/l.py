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
    "FA_Cup":           {"id": "eng.fa",              "json": "FA_Cup.json"},
    "EFL_Cup":          {"id": "eng.league_cup",      "json": "EFL_Cup.json"},
    "Copa_del_Rey":     {"id": "esp.copa_del_rey",    "json": "Copa_del_Rey.json"},
    "DFB_Pokal":        {"id": "ger.dfb_pokal",       "json": "DFB_Pokal.json"},
    "Coppa_Italia":     {"id": "ita.coppa_italia",    "json": "Coppa_Italia.json"},
    "Coupe_de_France":  {"id": "fra.coupe_de_france", "json": "Coupe_de_France.json"},
    "KNVB_Cup":         {"id": "ned.cup",             "json": "KNVB_Cup.json"},
    "Taca_de_Portugal": {"id": "por.taca.portugal",   "json": "Taca_de_Portugal.json"},
    "Kings_Cup_Saudi":  {"id": "ksa.kings.cup",       "json": "Kings_Cup_Saudi.json"},
}

# === PLAGE DE DATES : 01/01/2026 → aujourd'hui ===
now        = datetime.now(timezone.utc)
start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)

dates_to_fetch = []
current = start_date
while current <= now:
    dates_to_fetch.append(current.strftime("%Y%m%d"))
    current += timedelta(days=1)

print(f"📆 Plage : {dates_to_fetch[0]} → {dates_to_fetch[-1]} ({len(dates_to_fetch)} jours)\n")

# =============================
# UTILS
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

# =============================
# STATS
# =============================

def get_match_stats(game_id):
    url = f"https://www.espn.com/soccer/match/_/gameId/{game_id}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        res.encoding = "utf-8"
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
                    "away": values[1].text.strip(),
                }

        time.sleep(0.6)
        return stats
    except Exception:
        return {}

# =============================
# COTES ESPN
# =============================

def extract_odds(game_id):
    match_url = f"https://www.espn.com/soccer/match/_/gameId/{game_id}"
    try:
        res = requests.get(match_url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return None
        res.encoding = "utf-8"
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
    json_path = os.path.join(OUTPUT_DIR, league["json"])

    # ── Étape 1 : supprimer le JSON existant ──────────────────────────────
    if os.path.exists(json_path):
        os.remove(json_path)
        print(f"🗑️  JSON supprimé : {json_path}")

    print(f"\n🏆 {league_name} — scraping complet 01/01/2026 → aujourd'hui")

    BASE_URL = "https://www.espn.com/soccer/schedule/_/date/{date}/league/" + league["id"]

    matches   = {}
    new_count = 0

    # ── Étape 2 : parcourir toutes les dates ──────────────────────────────
    for date_str in dates_to_fetch:

        url = BASE_URL.format(date=date_str)
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception as e:
            print(f"    ⚠️  {date_str} — Erreur requête : {e}")
            continue

        tables = soup.select("div.ResponsiveTable")
        if not tables:
            continue

        print(f"  📅 {date_str} — {len(tables)} tableau(x) trouvé(s)")

        for table in tables:
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

                game_id = match_id.group(1)

                if game_id in matches:
                    continue

                match_url = (
                    "https://www.espn.com" + match_href
                    if match_href.startswith("/")
                    else match_href
                )

                print(f"    🔍 Scraping : {teams[0].text.strip()} vs {teams[1].text.strip()} (gameId: {game_id})")

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

                odds_str  = f"{odds['home']} / {odds['draw']} / {odds['away']}" if odds else "pas de cotes"
                stats_str = f"{len(stats)} stat(s)" if stats else "pas de stats"
                print(f"    ✅ {teams[0].text.strip()} {score} {teams[1].text.strip()} | cotes: {odds_str} | {stats_str}")

    # ── Sauvegarde atomique ────────────────────────────────────────────────
    if matches:
        tmp_path = json_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(list(matches.values()), f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, json_path)
        print(f"  💾 {league_name} : {new_count} matchs sauvegardés → {json_path}")
    else:
        print(f"  ⚠️  {league_name} : aucun match trouvé sur la période")

print("\n✅ Scraping complet terminé.")