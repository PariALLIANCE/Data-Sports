import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta, timezone
import re
import time
import os
import copy
from collections import defaultdict

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
}

OUTPUT_DIR     = "data/football/leagues"
STANDINGS_PATH = "data/football/standings/Standings.json"
os.makedirs(OUTPUT_DIR, exist_ok=True)

LEAGUES = {
  "Argentina_Primera_Nacional":    {"id": "arg.2",              "json": "Argentina_Primera_Nacional.json"},
  "Austria_Bundesliga":            {"id": "aut.1",              "json": "Austria_Bundesliga.json"},
  "Belgium_Jupiler_Pro_League":    {"id": "bel.1",              "json": "Belgium_Jupiler_Pro_League.json"},
  "Brazil_Serie_A":                {"id": "bra.1",              "json": "Brazil_Serie_A.json"},
  "Brazil_Serie_B":                {"id": "bra.2",              "json": "Brazil_Serie_B.json"},
  "Chile_Primera_Division":        {"id": "chi.1",              "json": "Chile_Primera_Division.json"},
  "China_Super_League":            {"id": "chn.1",              "json": "China_Super_League.json"},
  "Colombia_Primera_A":            {"id": "col.1",              "json": "Colombia_Primera_A.json"},
  "England_National_League":       {"id": "eng.5",              "json": "England_National_League.json"},
  "England_Premier_League":        {"id": "eng.1",              "json": "England_Premier_League.json"},
  "FIFA_Club_World_Cup":           {"id": "fifa.cwc",           "json": "FIFA_Club_World_Cup.json"},
  "France_Ligue_1":                {"id": "fra.1",              "json": "France_Ligue_1.json"},
  "Germany_Bundesliga":            {"id": "ger.1",              "json": "Germany_Bundesliga.json"},
  "Greece_Super_League_1":         {"id": "gre.1",              "json": "Greece_Super_League_1.json"},
  "Italy_Serie_A":                 {"id": "ita.1",              "json": "Italy_Serie_A.json"},
  "Japan_J1_League":               {"id": "jpn.1",              "json": "Japan_J1_League.json"},
  "Mexico_Liga_MX":                {"id": "mex.1",              "json": "Mexico_Liga_MX.json"},
  "Netherlands_Eredivisie":        {"id": "ned.1",              "json": "Netherlands_Eredivisie.json"},
  "Paraguay_Division_Profesional": {"id": "par.1",              "json": "Paraguay_Division_Profesional.json"},
  "Peru_Primera_Division":         {"id": "per.1",              "json": "Peru_Primera_Division.json"},
  "Portugal_Primeira_Liga":        {"id": "por.1",              "json": "Portugal_Primeira_Liga.json"},
  "Romania_Liga_I":                {"id": "rou.1",              "json": "Romania_Liga_I.json"},
  "Russia_Premier_League":         {"id": "rus.1",              "json": "Russia_Premier_League.json"},
  "Saudi_Arabia_Pro_League":       {"id": "ksa.1",              "json": "Saudi_Arabia_Pro_League.json"},
  "Spain_Laliga":                  {"id": "esp.1",              "json": "Spain_Laliga.json"},
  "Sweden_Allsvenskan":            {"id": "swe.1",              "json": "Sweden_Allsvenskan.json"},
  "Switzerland_Super_League":      {"id": "sui.1",              "json": "Switzerland_Super_League.json"},
  "Turkey_Super_Lig":              {"id": "tur.1",              "json": "Turkey_Super_Lig.json"},
  "UEFA_Champions_League":         {"id": "uefa.champions",     "json": "UEFA_Champions_League.json"},
  "UEFA_Europa_League":            {"id": "uefa.europa",        "json": "UEFA_Europa_League.json"},
  "USA_Major_League_Soccer":       {"id": "usa.1",              "json": "USA_Major_League_Soccer.json"},
  "Venezuela_Primera_Division":    {"id": "ven.1",              "json": "Venezuela_Primera_Division.json"},
  # ── Cups ──────────────────────────────────────────────────────────────
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

# Ligues exclues de l'enrichissement journée
CUPS_AND_INTL = {
    "FIFA_Club_World_Cup",
    "UEFA_Champions_League",
    "UEFA_Europa_League",
    "FA_Cup",
    "EFL_Cup",
    "Copa_del_Rey",
    "DFB_Pokal",
    "Coppa_Italia",
    "Coupe_de_France",
    "KNVB_Cup",
    "Taca_de_Portugal",
    "Kings_Cup_Saudi",
}

# ─────────────────────────────────────────────
# DATES : 10 DERNIERS JOURS
# ─────────────────────────────────────────────

now = datetime.now(timezone.utc)
target_dates = {
    (now - timedelta(days=i)).strftime("%Y%m%d")
    for i in range(1, 11)  # j-1 à j-10
}
dates_to_fetch = sorted(target_dates)  # du plus ancien au plus récent

# ─────────────────────────────────────────────
# PARSING DATES
# ─────────────────────────────────────────────

DATE_FORMATS = [
    "%A, %B %d, %Y",
    "%A, %d %B %Y",
    "%Y-%m-%d",
    "%Y%m%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
]

def parse_date(date_str: str) -> datetime | None:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None

def parse_date_formats(date_str):
    for fmt in ("%A, %B %d, %Y", "%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y%m%d")
        except Exception:
            continue
    return None

def is_target_date(date_str):
    normalized = parse_date_formats(date_str)
    return normalized in target_dates

# ─────────────────────────────────────────────
# LABEL SAISON
# ─────────────────────────────────────────────

def get_saison_label(saison_offset: int) -> str:
    current_year = datetime.now().year
    start = current_year - saison_offset - 1
    end   = current_year - saison_offset
    return f"{start}/{end}"

# ─────────────────────────────────────────────
# CHARGEMENT STANDINGS
# ─────────────────────────────────────────────

def load_standings():
    if not os.path.exists(STANDINGS_PATH):
        print(f"  [WARN] Standings introuvable : {STANDINGS_PATH}")
        return {}
    with open(STANDINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

standings_raw = load_standings()

# ─────────────────────────────────────────────
# ENRICHISSEMENT JOURNÉE
# ─────────────────────────────────────────────

def enrich_journee(matches_list: list, league_key: str) -> list:
    if league_key not in standings_raw:
        return matches_list

    standing       = standings_raw[league_key]
    TOTAL_JOURNEES = standing["total_journees"]

    gp_per_team = {
        entry["name"]: entry["stats"]["GP"]
        for entry in standing["standings"]
        if entry.get("stats", {}).get("GP") is not None
    }

    if not gp_per_team:
        return matches_list

    CURRENT_JOURNEE = max(gp_per_team.values())

    # Tri du plus récent au plus ancien
    def sort_key(m):
        d = parse_date(m.get("date", ""))
        return d if d else datetime.min

    matches_sorted = sorted(matches_list, key=sort_key, reverse=True)

    # Regroupement par équipe
    team_matches_order = defaultdict(list)
    for m in matches_sorted:
        t1 = m.get("team1")
        t2 = m.get("team2")
        if t1:
            team_matches_order[t1].append(m)
        if t2:
            team_matches_order[t2].append(m)

    # Attribution des journées par équipe
    match_journee = {}

    for team, team_matches in team_matches_order.items():
        journee       = gp_per_team.get(team, CURRENT_JOURNEE)
        saison_offset = 0

        for m in team_matches:
            game_id = m.get("gameId")
            if not game_id:
                journee -= 1
                if journee < 1:
                    saison_offset += 1
                    journee = TOTAL_JOURNEES
                continue

            if game_id not in match_journee:
                match_journee[game_id] = {}

            match_journee[game_id][f"journee_team_{team}"] = {
                "journee":       journee,
                "saison_offset": saison_offset
            }

            journee -= 1
            if journee < 1:
                saison_offset += 1
                journee = TOTAL_JOURNEES

    # Consolidation : une journée unique par match
    def consolidate(game_id, m):
        data = match_journee.get(game_id, {})
        t1   = m.get("team1")
        t2   = m.get("team2")

        key1 = f"journee_team_{t1}" if t1 else None
        key2 = f"journee_team_{t2}" if t2 else None

        if key1 and key1 in data:
            return data[key1]
        if key2 and key2 in data:
            return data[key2]

        values = list(data.values())
        if values:
            avg_j = round(sum(v["journee"] for v in values) / len(values))
            avg_s = round(sum(v["saison_offset"] for v in values) / len(values))
            return {"journee": avg_j, "saison_offset": avg_s}

        return {"journee": None, "saison_offset": None}

    # Appliquer uniquement sur les matchs sans journée
    enriched = []
    for m in matches_list:
        mc      = copy.deepcopy(m)
        game_id = mc.get("gameId")

        if mc.get("journee") is not None:
            enriched.append(mc)
            continue

        if game_id:
            result        = consolidate(game_id, mc)
            journee       = result["journee"]
            saison_offset = result["saison_offset"]

            mc["journee"]         = journee
            mc["saison_offset"]   = saison_offset
            mc["saison"]          = get_saison_label(saison_offset) if saison_offset is not None else None
            mc["saison_terminee"] = (CURRENT_JOURNEE >= TOTAL_JOURNEES)
        else:
            mc["journee"]         = None
            mc["saison_offset"]   = None
            mc["saison"]          = None
            mc["saison_terminee"] = None

        enriched.append(mc)

    return enriched

# ─────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────

def load_existing_matches(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {m["gameId"]: m for m in data if "gameId" in m}
    except Exception:
        return {}

# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────

def get_match_stats(game_id):
    url     = f"https://www.espn.com/soccer/match/_/gameId/{game_id}"
    headers = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
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
                    "away": values[1].text.strip()
                }

        time.sleep(0.6)
        return stats
    except Exception:
        return {}

# ─────────────────────────────────────────────
# COTES ESPN
# ─────────────────────────────────────────────

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
        res.encoding = "utf-8"
        soup  = BeautifulSoup(res.text, "html.parser")
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

# ─────────────────────────────────────────────
# BOUCLE PRINCIPALE
# ─────────────────────────────────────────────

for league_name, league in LEAGUES.items():
    print(f"\n🏆 {league_name}")

    BASE_URL  = "https://www.espn.com/soccer/schedule/_/date/{date}/league/" + league["id"]
    json_path = os.path.join(OUTPUT_DIR, league["json"])
    matches   = load_existing_matches(json_path)

    # ── Étape 1 : supprimer les matchs des 10 derniers jours sans cotes ───
    removed = [
        gid for gid, m in matches.items()
        if is_target_date(m.get("date", "")) and not m.get("odds")
    ]
    for gid in removed:
        del matches[gid]
    if removed:
        print(f"  🗑️  {len(removed)} match(s) sans cotes supprimé(s) et re-scrapés")

    new_count     = 0
    stats_updated = 0

    # ── Étape 2 : scraper les 10 derniers jours ───────────────────────────
    for date_str in dates_to_fetch:
        print(f"  📅 {date_str}")

        url = BASE_URL.format(date=date_str)
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception as e:
            print(f"    ⚠️  Erreur requête : {e}")
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

    # ── Étape 3 : enrichissement journée (ligues uniquement) ──────────────
    if league_name not in CUPS_AND_INTL:
        matches_list  = list(matches.values())
        enriched_list = enrich_journee(matches_list, league_name)
        matches       = {m["gameId"]: m for m in enriched_list if "gameId" in m}
        print(f"  📆 Journées mises à jour")

    # ── Sauvegarde atomique ────────────────────────────────────────────────
    tmp_path = json_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(list(matches.values()), f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, json_path)

    print(f"  💾 {league_name} : {len(matches)} matchs | +{new_count} nouveaux | stats MAJ {stats_updated}")