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
  "Argentina_Primera_Nacional": {"id": "arg.2", "json": "Argentina_Primera_Nacional.json"},
  "Austria_Bundesliga": {"id": "aut.1", "json": "Austria_Bundesliga.json"},
  "Belgium_Jupiler_Pro_League": {"id": "bel.1", "json": "Belgium_Jupiler_Pro_League.json"},
  "Brazil_Serie_A": {"id": "bra.1", "json": "Brazil_Serie_A.json"},
  "Brazil_Serie_B": {"id": "bra.2", "json": "Brazil_Serie_B.json"},
  "Chile_Primera_Division": {"id": "chi.1", "json": "Chile_Primera_Division.json"},
  "China_Super_League": {"id": "chn.1", "json": "China_Super_League.json"},
  "Colombia_Primera_A": {"id": "col.1", "json": "Colombia_Primera_A.json"},
  "England_National_League": {"id": "eng.5", "json": "England_National_League.json"},
  "England_Premier_League": {"id": "eng.1", "json": "England_Premier_League.json"},
  "FIFA_Club_World_Cup": {"id": "fifa.cwc", "json": "FIFA_Club_World_Cup.json"},
  "France_Ligue_1": {"id": "fra.1", "json": "France_Ligue_1.json"},
  "Germany_Bundesliga": {"id": "ger.1", "json": "Germany_Bundesliga.json"},
  "Greece_Super_League_1": {"id": "gre.1", "json": "Greece_Super_League_1.json"},
  "Italy_Serie_A": {"id": "ita.1", "json": "Italy_Serie_A.json"},
  "Japan_J1_League": {"id": "jpn.1", "json": "Japan_J1_League.json"},
  "Mexico_Liga_MX": {"id": "mex.1", "json": "Mexico_Liga_MX.json"},
  "Netherlands_Eredivisie": {"id": "ned.1", "json": "Netherlands_Eredivisie.json"},
  "Paraguay_Division_Profesional": {"id": "par.1", "json": "Paraguay_Division_Profesional.json"},
  "Peru_Primera_Division": {"id": "per.1", "json": "Peru_Primera_Division.json"},
  "Portugal_Primeira_Liga": {"id": "por.1", "json": "Portugal_Primeira_Liga.json"},
  "Romania_Liga_I": {"id": "rou.1", "json": "Romania_Liga_I.json"},
  "Russia_Premier_League": {"id": "rus.1", "json": "Russia_Premier_League.json"},
  "Saudi_Arabia_Pro_League": {"id": "ksa.1", "json": "Saudi_Arabia_Pro_League.json"},
  "Spain_Laliga": {"id": "esp.1", "json": "Spain_Laliga.json"},
  "Sweden_Allsvenskan": {"id": "swe.1", "json": "Sweden_Allsvenskan.json"},
  "Switzerland_Super_League": {"id": "sui.1", "json": "Switzerland_Super_League.json"},
  "Turkey_Super_Lig": {"id": "tur.1", "json": "Turkey_Super_Lig.json"},
  "UEFA_Champions_League": {"id": "uefa.champions", "json": "UEFA_Champions_League.json"},
  "UEFA_Europa_League": {"id": "uefa.europa", "json": "UEFA_Europa_League.json"},
  "USA_Major_League_Soccer": {"id": "usa.1", "json": "USA_Major_League_Soccer.json"},
  "Venezuela_Primera_Division": {"id": "ven.1", "json": "Venezuela_Primera_Division.json"}
}

# === DATES : AVANT-HIER & HIER ===
now = datetime.now(timezone.utc)
target_dates = {
    (now - timedelta(days=2)).strftime("%Y%m%d"),
    (now - timedelta(days=1)).strftime("%Y%m%d"),
}
dates_to_fetch = sorted(target_dates)

# =============================
# UTILS
# =============================

def parse_date_formats(date_str):
    """Tente de parser une date ESPN en objet date pour comparaison."""
    for fmt in ("%A, %B %d, %Y", "%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y%m%d")
        except:
            continue
    return None

def is_target_date(date_str):
    normalized = parse_date_formats(date_str)
    return normalized in target_dates

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
# COTES ESPN
# =============================

def us_to_decimal(odds_str):
    if not odds_str:
        return None
    try:
        val = int(odds_str.replace("+", "").strip())
        return round(1 + (val / 100), 2) if val > 0 else round(1 + (100 / abs(val)), 2)
    except:
        return None

def is_valid_us_odds(val):
    if not val:
        return False
    try:
        int(val.replace("+", "").replace("-", ""))
        return True
    except:
        return False

def extract_odds(match_url):
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
    BASE_URL = f"https://www.espn.com/soccer/schedule/_/date/{{date}}/league/{league['id']}"
    json_path = os.path.join(OUTPUT_DIR, league["json"])

    matches = load_existing_matches(json_path)

    # ── Étape 1 : supprimer les matchs hier/avant-hier sans cotes ──────────
    removed = [
        gid for gid, m in matches.items()
        if is_target_date(m.get("date", "")) and not m.get("odds")
    ]
    for gid in removed:
        del matches[gid]
    if removed:
        print(f"  🗑️  {len(removed)} match(s) sans cotes supprimé(s) et re-scrapés")

    new_count    = 0
    stats_updated = 0

    # ── Étape 2 : re-scraper hier et avant-hier ────────────────────────────
    for date_str in dates_to_fetch:
        print(f"  📅 {date_str}")

        try:
            res = requests.get(BASE_URL.format(date=date_str), headers=HEADERS, timeout=15)
            soup = BeautifulSoup(res.content, "html.parser")
        except Exception:
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

                match_id = re.search(r"gameId/(\d+)", score_tag["href"])
                if not match_id:
                    continue

                game_id   = match_id.group(1)
                match_url = "https://www.espn.com" + score_tag["href"]

                # ── Match existant : enrichir stats si manquantes ──────────
                if game_id in matches:
                    if not matches[game_id].get("stats"):
                        stats = get_match_stats(game_id)
                        if stats:
                            matches[game_id]["stats"] = stats
                            stats_updated += 1
                    continue

                # ── Nouveau match : stats + cotes ──────────────────────────
                stats = get_match_stats(game_id)
                odds  = extract_odds(match_url)
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

    # ── Sauvegarde atomique ────────────────────────────────────────────────
    tmp_path = json_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(list(matches.values()), f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, json_path)

    print(f"  💾 {league_name} : {len(matches)} matchs | +{new_count} nouveaux | stats MAJ {stats_updated}")
