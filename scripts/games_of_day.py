import json
from datetime import datetime, timezone
import re
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup, NavigableString

# ================= DRIVER SELENIUM =================
def make_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
    )
    options.add_argument("--lang=en-US")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    return driver

def get_soup(driver, url, wait_selector=None, timeout=15):
    driver.get(url)
    if wait_selector:
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
            )
        except Exception:
            pass
    return BeautifulSoup(driver.page_source, "html.parser")

# ================= DOSSIERS =================
BASE_DIR      = "data/football"
STANDINGS_DIR = os.path.join(BASE_DIR, "standings")
os.makedirs(BASE_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(BASE_DIR, "games_of_day.json")

# ================= LIGUES =================
LEAGUES = {
    "England_Premier_League":        "eng.1",
    "Spain_Laliga":                  "esp.1",
    "Germany_Bundesliga":            "ger.1",
    "Argentina_Primera_Nacional":    "arg.2",
    "Austria_Bundesliga":            "aut.1",
    "Belgium_Jupiler_Pro_League":    "bel.1",
    "Brazil_Serie_A":                "bra.1",
    "Brazil_Serie_B":                "bra.2",
    "Chile_Primera_Division":        "chi.1",
    "China_Super_League":            "chn.1",
    "Colombia_Primera_A":            "col.1",
    "England_National_League":       "eng.5",
    "France_Ligue_1":                "fra.1",
    "Greece_Super_League_1":         "gre.1",
    "Italy_Serie_A":                 "ita.1",
    "Japan_J1_League":               "jpn.1",
    "Mexico_Liga_MX":                "mex.1",
    "Netherlands_Eredivisie":        "ned.1",
    "Paraguay_Division_Profesional": "par.1",
    "Peru_Primera_Division":         "per.1",
    "Portugal_Primeira_Liga":        "por.1",
    "Romania_Liga_I":                "rou.1",
    "Russia_Premier_League":         "rus.1",
    "Saudi_Arabia_Pro_League":       "ksa.1",
    "Sweden_Allsvenskan":            "swe.1",
    "Switzerland_Super_League":      "sui.1",
    "Turkey_Super_Lig":              "tur.1",
    "USA_Major_League_Soccer":       "usa.1",
    "Venezuela_Primera_Division":    "ven.1",
    "UEFA_Champions_League":         "uefa.champions",
    "UEFA_Europa_League":            "uefa.europa",
    "FIFA_Club_World_Cup":           "fifa.cwc",
    "FA_Cup":                        "eng.fa",
    "EFL_Cup":                       "eng.league_cup",
    "Copa_del_Rey":                  "esp.copa_del_rey",
    "DFB_Pokal":                     "ger.dfb_pokal",
    "Coppa_Italia":                  "ita.coppa_italia",
    "Coupe_de_France":               "fra.coupe_de_france",
    "KNVB_Cup":                      "ned.cup",
    "Taca_de_Portugal":              "por.taca.portugal",
    "Kings_Cup_Saudi":               "ksa.kings.cup",
}

BASE_URL = "https://www.espn.com/soccer/schedule/_/date/{date}/league/{league}"

# ================= DATE =================
today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ================= UTILITAIRES =================
def convert_date_to_iso(date_text):
    try:
        return datetime.strptime(date_text, "%A, %B %d, %Y").strftime("%Y-%m-%d")
    except:
        return date_text

def convert_time_espn_to_ci(time_str):
    """
    Convertit l'heure ESPN (US Eastern Summer = UTC-4)
    en heure locale Côte d'Ivoire (UTC+0).
    Retourne une chaîne "HH:MM" en format 24h.
    ESPN affiche en format 12h avec AM/PM, ex: "2:30 PM", "10:00 AM".
    """
    if not time_str:
        return None
    try:
        # Nettoyage : supprimer espaces insécables, normaliser
        cleaned = time_str.strip().replace("\u202f", " ").replace("\xa0", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).upper()

        # Format 12h avec espace : "2:30 PM" → parse direct
        if "AM" in cleaned or "PM" in cleaned:
            if " " in cleaned:
                dt_eastern = datetime.strptime(cleaned, "%I:%M %p")
            else:
                dt_eastern = datetime.strptime(cleaned, "%I:%M%p")
            # Eastern Summer (UTC-4) → UTC+0 (CI) = +4h
            hour_ci = (dt_eastern.hour + 4) % 24
            return f"{hour_ci:02d}:{dt_eastern.minute:02d}"

        # Format 24h déjà (peu probable venant d'ESPN US mais fallback)
        dt = datetime.strptime(cleaned, "%H:%M")
        hour_ci = (dt.hour + 4) % 24
        return f"{hour_ci:02d}:{dt.minute:02d}"

    except Exception as e:
        print(f"  ⚠️ Erreur conversion heure '{time_str}': {e}")
        return time_str

def us_to_decimal(val):
    if not val:
        return None
    try:
        n = int(val.replace("+", "").strip())
        return round(1 + (n / 100), 2) if n > 0 else round(1 + (100 / abs(n)), 2)
    except:
        return None

def extract_team_id_from_logo(logo_url):
    if not logo_url:
        return None
    m = re.search(r"/(\d+)\.png", logo_url)
    return m.group(1) if m else None

def extract_team_id_from_team_url(team_url):
    if not team_url:
        return None
    m = re.search(r"/id/(\d+)/", team_url)
    return m.group(1) if m else None

def read_direct_text(tag):
    """
    Lit uniquement les NavigableString directs d'un tag,
    en ignorant tout contenu des sous-éléments (div, svg, etc.).
    Retourne la concaténation des textes directs nettoyés.
    Exemple :
      <div class="rbmla">2<div class="xtUup"><svg>...</svg></div></div>
      → "2"
    """
    if not tag:
        return None
    parts = []
    for child in tag.children:
        if isinstance(child, NavigableString):
            t = str(child).strip()
            if t:
                parts.append(t)
    result = "".join(parts).strip()
    return result if result else None

# ================= EXTRACTION LOGOS DEPUIS LA PAGE DU MATCH =================
def extract_logos_from_match_page(soup):
    imgs = soup.select('img[data-testid="prism-image"]')
    logo_home = imgs[0]["src"] if len(imgs) >= 1 else None
    logo_away = imgs[1]["src"] if len(imgs) >= 2 else None
    return logo_home, logo_away

# ================= EXTRACTION COTES ESPN =================
def extract_ml_odds(soup):
    try:
        cells = soup.find_all("div", {"data-testid": "OddsCell"})
        if len(cells) < 7:
            return None

        def read(cell):
            return cell.get_text(strip=True) or None

        def is_valid(val):
            if not val:
                return False
            try:
                int(val.replace("+", "").replace("-", ""))
                return True
            except:
                return False

        home_us = read(cells[0])
        away_us = read(cells[3])
        draw_us = read(cells[6])

        if not all(is_valid(v) for v in [home_us, away_us, draw_us]):
            return None

        return {
            "home": us_to_decimal(home_us),
            "away": us_to_decimal(away_us),
            "draw": us_to_decimal(draw_us),
        }
    except Exception as e:
        print(f"  ⚠️ Erreur cotes : {e}")
        return None

# ================= EXTRACTION STATS DU MATCH =================
def extract_match_stats(soup):
    stats = {}
    try:
        stat_rows = soup.select("div.StatCellContent")
        if stat_rows:
            values = [el.get_text(strip=True) for el in stat_rows]
            i = 0
            while i + 2 < len(values):
                home_val = values[i]
                label    = values[i + 1]
                away_val = values[i + 2]
                if label and not label.replace(" ", "").isdigit():
                    stats[label] = {"home": home_val, "away": away_val}
                    i += 3
                else:
                    i += 1
            if stats:
                return stats

        game_stat_rows = soup.select("div.GameStat")
        if game_stat_rows:
            for row in game_stat_rows:
                cols = row.select("div")
                texts = [c.get_text(strip=True) for c in cols if c.get_text(strip=True)]
                if len(texts) >= 3:
                    stats[texts[1]] = {"home": texts[0], "away": texts[2]}
            if stats:
                return stats

        gp_rows = soup.select("div.gamepackage-matchup-charts tr")
        if gp_rows:
            for row in gp_rows:
                cells = row.select("td")
                if len(cells) == 3:
                    home_val = cells[0].get_text(strip=True)
                    label    = cells[1].get_text(strip=True)
                    away_val = cells[2].get_text(strip=True)
                    if label:
                        stats[label] = {"home": home_val, "away": away_val}
            if stats:
                return stats

        rows = soup.select("tr[data-stat], div[data-stat]")
        for row in rows:
            label    = row.get("data-stat", "")
            children = row.select("td, div.value")
            if len(children) >= 2 and label:
                stats[label] = {
                    "home": children[0].get_text(strip=True),
                    "away": children[1].get_text(strip=True),
                }
        if stats:
            return stats

    except Exception as e:
        print(f"  ⚠️ Erreur stats : {e}")

    return {}

# ================= EXTRACTION H2H =================
def extract_h2h(soup):
    """
    Parse la section Head-To-Head ESPN (layout prism).

    Structure d'une ligne de match H2H :
    ┌─ div.rpjsZ.TzFuW.lSDCP  (ligne complète)
    │   ├─ a[data-game-link]  → URL du match
    │   └─ div.iEHPA.TzFuW   (contenu)
    │       ├─ div.RRvbN [0]  → score équipe GAUCHE (home du match du jour = NAU)
    │       │   └─ div.LiUVm  (perdant/nul) OU div.rbmla (gagnant)
    │       │       └─ NavigableString "1"   ← score brut, PAS get_text()
    │       │          [div.xtUup > svg]     ← sous-div à IGNORER
    │       ├─ div.vIQoV.QXDKT (métadonnées)
    │       │   ├─ div.LiUVm.PLrIT.KTwp.FuEs → compétition
    │       │   ├─ div.uMFIG                 → date "2/26/23"
    │       │   └─ span.LiUVm.FWLyZ         → venue "@ FOR"
    │       └─ div.RRvbN [1]  → score équipe DROITE (away = FOR)
    │           └─ div.rbmla  (gagnant avec flèche SVG)
    │               ├─ NavigableString "2"   ← score brut
    │               └─ div.xtUup > svg       ← à IGNORER
    """
    h2h_list = []
    try:
        # ── Localiser la section H2H ──
        section = None
        for sec in soup.find_all("section", {"data-testid": "prism-LayoutCard"}):
            h2_tag = sec.find("h2", {"data-testid": "prism-LayoutCardSlot"})
            if h2_tag and "head" in h2_tag.get_text(strip=True).lower():
                section = sec
                break

        if not section:
            print("  ℹ️  Section H2H introuvable")
            return h2h_list

        # ── Slugs des deux équipes depuis le header ──
        # <a href="/soccer/team/_/id/7633/nautico"> et <a href=".../6272/fortaleza">
        header_links = section.select("div.oimqG a[data-testid='prism-linkbase']")
        slug_left, slug_right = None, None
        id_left,   id_right   = None, None
        if len(header_links) >= 2:
            def parse_team_link(a_tag):
                href = a_tag.get("href", "")
                m_id   = re.search(r"/id/(\d+)/", href)
                m_slug = re.search(r"/id/\d+/([^/\?]+)$", href)
                return (m_id.group(1) if m_id else None,
                        m_slug.group(1) if m_slug else None)
            id_left,  slug_left  = parse_team_link(header_links[0])
            id_right, slug_right = parse_team_link(header_links[1])

        # ── Lignes de matchs H2H ──
        # Sélecteur précis : div direct enfant du conteneur principal
        # qui possède TOUTES ces classes : rpjsZ, TzFuW, lSDCP
        match_rows = section.select("div.rpjsZ.TzFuW.lSDCP")

        for row in match_rows:
            try:
                # ── URL & gameId ──
                link_tag   = row.select_one("a[data-game-link='true']")
                match_href = link_tag.get("href", "") if link_tag else ""
                match_url  = ("https://www.espn.com" + match_href) if match_href else None
                gid_m      = re.search(r"gameId/(\d+)", match_href)
                game_id_h2h = gid_m.group(1) if gid_m else None

                # ── Contenu principal ──
                content = row.select_one("div.iEHPA.TzFuW")
                if not content:
                    continue

                # ── Blocs de scores : exactement 2 div.RRvbN ──
                score_blocks = content.select("div.mLASH.RRvbN")
                if len(score_blocks) < 2:
                    # Fallback sans .mLASH
                    score_blocks = content.select("div.RRvbN")
                if len(score_blocks) < 2:
                    print(f"    ⚠️ H2H gameId={game_id_h2h} : score_blocks={len(score_blocks)}")
                    continue

                def extract_score(block):
                    """
                    Extrait le score depuis un bloc RRvbN.
                    L'inner div est LiUVm (perdant) ou rbmla (gagnant).
                    Le chiffre du score EST un NavigableString direct de l'inner div.
                    Le SVG winner est dans un sous-div xtUup → ignoré par read_direct_text().

                    Cas rencontrés dans le HTML :
                      <div class="mLASH LiUVm ...">1</div>              → score "1", pas gagnant
                      <div class="mLASH rbmla ...">2<div class="xtUup"><svg/></div></div>
                                                                         → score "2", gagnant
                      <div class="mLASH rbmla ...">2</div>              → score "2", nul (pas de SVG)
                    """
                    inner = block.select_one("div.LiUVm, div.rbmla")
                    if not inner:
                        return None, False
                    score_text = read_direct_text(inner)
                    # Est gagnant si rbmla ET contient le SVG winner (xtUup)
                    is_winner  = (
                        "rbmla" in inner.get("class", []) and
                        inner.select_one("div.xtUup") is not None
                    )
                    return score_text, is_winner

                score_left_val,  left_is_winner  = extract_score(score_blocks[0])
                score_right_val, right_is_winner = extract_score(score_blocks[1])

                # ── Résultat du point de vue de l'équipe GAUCHE (home du match du jour) ──
                result_left = None
                if score_left_val is not None and score_right_val is not None:
                    try:
                        sl = int(score_left_val)
                        sr = int(score_right_val)
                        result_left = "W" if sl > sr else ("L" if sl < sr else "D")
                    except:
                        pass
                if result_left is None:
                    result_left = "W" if left_is_winner else ("L" if right_is_winner else "D")

                # ── Métadonnées ──
                meta = content.select_one("div.vIQoV.QXDKT")

                comp_div    = meta.select_one("div.LiUVm.PLrIT.KTwp.FuEs") if meta else None
                competition = comp_div.get_text(strip=True) if comp_div else None

                date_div = meta.select_one("div.uMFIG") if meta else None
                date_raw = date_div.get_text(strip=True) if date_div else None
                date_iso = None
                if date_raw:
                    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
                        try:
                            date_iso = datetime.strptime(date_raw, fmt).strftime("%Y-%m-%d")
                            break
                        except:
                            continue
                    if not date_iso:
                        date_iso = date_raw

                venue_span = meta.select_one("span.LiUVm.FWLyZ") if meta else None
                venue_text = venue_span.get_text(strip=True) if venue_span else None
                # Ex: "@ FOR" → jouait chez Fortaleza dans ce H2H
                # "@ NAU"  → jouait chez Nautico dans ce H2H

                # ── Déterminer home/away dans ce match H2H ──
                # venue_text = "@ XXX" où XXX est l'abréviation de l'équipe recevante
                h2h_home_id, h2h_away_id     = None, None
                h2h_home_slug, h2h_away_slug = None, None
                if venue_text:
                    venue_clean = venue_text.replace("@", "").strip()
                    # On compare avec les abréviations des logos dans le header
                    abbr_left  = header_links[0].select_one("img").get("alt", "").strip() if len(header_links) >= 1 else ""
                    abbr_right = header_links[1].select_one("img").get("alt", "").strip() if len(header_links) >= 2 else ""
                    if venue_clean.upper() == abbr_right.upper():
                        # Équipe droite (away du match du jour) était à domicile dans ce H2H
                        h2h_home_id, h2h_home_slug = id_right, slug_right
                        h2h_away_id, h2h_away_slug = id_left,  slug_left
                    elif venue_clean.upper() == abbr_left.upper():
                        # Équipe gauche (home du match du jour) était à domicile dans ce H2H
                        h2h_home_id, h2h_home_slug = id_left,  slug_left
                        h2h_away_id, h2h_away_slug = id_right, slug_right

                h2h_list.append({
                    "game_id":        game_id_h2h,
                    "date":           date_iso,
                    "competition":    competition,
                    # Scores avec les noms explicites des équipes
                    "score": {
                        "left":  score_left_val,   # score NAU (home du match du jour)
                        "right": score_right_val,  # score FOR (away du match du jour)
                    },
                    "result_left":    result_left,     # W/D/L du point de vue équipe gauche
                    "venue":          venue_text,      # "@ FOR" ou "@ NAU"
                    "h2h_home": {
                        "team_id":   h2h_home_id,
                        "team_slug": h2h_home_slug,
                    },
                    "h2h_away": {
                        "team_id":   h2h_away_id,
                        "team_slug": h2h_away_slug,
                    },
                    "match_url": match_url,
                })

            except Exception as e:
                print(f"    ⚠️ Erreur ligne H2H : {e}")
                continue

    except Exception as e:
        print(f"  ⚠️ Erreur H2H globale : {e}")

    return h2h_list

# ================= EXTRACTION DERNIERS MATCHS (LAST 5) =================
def extract_last_five(soup, team_id):
    """
    Extrait les 5 derniers matchs d'une équipe.
    team_id : ID ESPN de l'équipe, utilisé pour identifier la section active.
    opponent_id et opponent_slug sont extraits depuis l'URL de l'équipe adverse.
    """
    last_five = []
    try:
        sections = soup.find_all("section", {"data-testid": "lastGames"})

        target_section = None
        for sec in sections:
            active_btn = sec.select_one("button.Button--active")
            if active_btn and team_id:
                img = active_btn.select_one("img")
                if img:
                    tid = extract_team_id_from_logo(img.get("src", ""))
                    if tid == team_id:
                        target_section = sec
                        break

        if not target_section and sections:
            target_section = sections[0]

        if not target_section:
            return last_five

        rows = target_section.select("tbody tr.Table__TR")
        for row in rows:
            try:
                tds = row.select("td.Table__TD")
                if len(tds) < 4:
                    continue

                # ── Date ──
                date_raw = tds[0].get_text(strip=True)
                date_iso = None
                for fmt in ("%m/%d/%y", "%m/%d/%Y"):
                    try:
                        date_iso = datetime.strptime(date_raw, fmt).strftime("%Y-%m-%d")
                        break
                    except:
                        continue
                if not date_iso:
                    date_iso = date_raw

                # ── Adversaire ──
                opp_td       = tds[1]
                at_span      = opp_td.select_one("span.atVs")
                venue        = at_span.get_text(strip=True) if at_span else ""

                opp_link_tag = opp_td.select_one("a.AnchorLink")
                opp_href     = opp_link_tag.get("href", "") if opp_link_tag else ""
                opp_team_id  = extract_team_id_from_team_url(opp_href)
                # Slug depuis /soccer/team/_/id/10281/botafogo-sp → "botafogo-sp"
                m_slug       = re.search(r"/id/\d+/([^/\?]+)$", opp_href)
                opp_slug     = m_slug.group(1) if m_slug else None
                opp_full_url = ("https://www.espn.com" + opp_href) if opp_href else None

                # ── Résultat & score ──
                result_td    = tds[2]
                result_link  = result_td.select_one("a.AnchorLink")
                match_href   = result_link.get("href", "") if result_link else ""
                match_url    = ("https://www.espn.com" + match_href) if match_href else None

                gid_m        = re.search(r"gameId/(\d+)", match_href)
                match_gid    = gid_m.group(1) if gid_m else None

                # Slug du match depuis URL : /soccer/match/_/gameId/401860130/nautico-botafogo-sp
                slug_m       = re.search(r"gameId/\d+/([^/\?]+)$", match_href.rstrip("/"))
                match_slug   = slug_m.group(1) if slug_m else None

                result_span  = result_td.select_one("span.GameResults")
                result       = result_span.get_text(strip=True) if result_span else None
                score_span   = result_td.select_one("span.Score")
                score        = score_span.get_text(strip=True) if score_span else None

                # ── Compétition ──
                competition  = tds[3].get_text(strip=True)

                last_five.append({
                    "date":          date_iso,
                    "venue":         venue,         # "@" = away, "vs" = home
                    "opponent_slug": opp_slug,      # ex: "botafogo-sp"
                    "opponent_id":   opp_team_id,   # ex: "10281"
                    "opponent_url":  opp_full_url,
                    "result":        result,         # W / D / L
                    "score":         score,
                    "competition":   competition,
                    "game_id":       match_gid,
                    "match_slug":    match_slug,    # ex: "nautico-botafogo-sp"
                    "match_url":     match_url,
                })

            except Exception as e:
                print(f"    ⚠️ Erreur ligne last5 : {e}")
                continue

    except Exception as e:
        print(f"  ⚠️ Erreur last5 globale : {e}")

    return last_five

# ================= CHARGEMENT STANDINGS =================
STANDINGS_FILE = os.path.join(STANDINGS_DIR, "Standings.json")
standings_data = {}
if os.path.exists(STANDINGS_FILE):
    with open(STANDINGS_FILE, "r", encoding="utf-8") as f:
        standings_data = json.load(f)
else:
    print(f"⚠️ Standings introuvables : {STANDINGS_FILE}")

# ================= SCRAPING PRINCIPAL =================
games_of_day = {}
driver = make_driver()

try:
    for league_name, league_code in LEAGUES.items():
        print(f"\n📅 {league_name}")

        try:
            soup = get_soup(
                driver,
                BASE_URL.format(date=today_str, league=league_code),
                wait_selector="div.ResponsiveTable",
                timeout=15,
            )
        except Exception as e:
            print(f"  ⚠️ Erreur réseau : {e}")
            continue

        for table in soup.select("div.ResponsiveTable"):
            date_tag = table.select_one("div.Table__Title")
            date_iso = convert_date_to_iso(date_tag.text.strip() if date_tag else today_str)

            if date_iso != today_iso:
                continue

            for row in table.select("tbody > tr.Table__TR"):
                teams     = row.select("span.Table__Team a.AnchorLink:last-child")
                score_tag = row.select_one("a.AnchorLink.at")
                time_tag  = row.select_one("td.date__col a")

                if len(teams) != 2 or not score_tag:
                    continue
                if score_tag.text.strip().lower() != "v":
                    continue

                match_id = re.search(r"gameId/(\d+)", score_tag["href"])
                if not match_id:
                    continue

                game_id   = match_id.group(1)
                team1     = teams[0].text.strip()
                team2     = teams[1].text.strip()
                match_url = "https://www.espn.com" + score_tag["href"]
                raw_time  = time_tag.text.strip() if time_tag else None

                # ── Heure locale Côte d'Ivoire (format 24h, UTC+0) ──
                time_ci = convert_time_espn_to_ci(raw_time) if raw_time else None

                # ── Chargement de la page du match ──
                match_soup = get_soup(
                    driver,
                    match_url,
                    wait_selector=(
                        'img[data-testid="prism-image"], '
                        'section[data-testid="lastGames"], '
                        'section[data-testid="prism-LayoutCard"]'
                    ),
                    timeout=20,
                )
                time.sleep(1)

                # ── Logos & IDs ──
                logo_home, logo_away = extract_logos_from_match_page(match_soup)
                team_id_home = extract_team_id_from_logo(logo_home)
                team_id_away = extract_team_id_from_logo(logo_away)

                # ── Slugs depuis les liens de la page ──
                slug_home, slug_away = None, None
                for a_tag in match_soup.select("a[data-clubhouse-uid]"):
                    href = a_tag.get("href", "")
                    if team_id_home and f"/id/{team_id_home}/" in href:
                        m = re.search(r"/id/\d+/([^/\?]+)$", href)
                        if m and not slug_home:
                            slug_home = m.group(1)
                    if team_id_away and f"/id/{team_id_away}/" in href:
                        m = re.search(r"/id/\d+/([^/\?]+)$", href)
                        if m and not slug_away:
                            slug_away = m.group(1)

                # ── Cotes ──
                ml = extract_ml_odds(match_soup)

                # ── Stats ──
                match_stats = extract_match_stats(match_soup)

                # ── H2H ──
                h2h = extract_h2h(match_soup)

                # ── Last 5 home (onglet home actif par défaut) ──
                last5_home = extract_last_five(match_soup, team_id_home)

                # ── Last 5 away : clic sur le 2ème bouton via Selenium ──
                last5_away = []
                try:
                    away_btns = driver.find_elements(
                        By.CSS_SELECTOR,
                        "section[data-testid='lastGames'] button.Button--filter"
                    )
                    if len(away_btns) >= 2:
                        driver.execute_script("arguments[0].click();", away_btns[1])
                        time.sleep(1.5)
                        away_soup  = BeautifulSoup(driver.page_source, "html.parser")
                        last5_away = extract_last_five(away_soup, team_id_away)
                    else:
                        print(f"  ⚠️ Bouton away last5 introuvable")
                except Exception as e:
                    print(f"  ⚠️ Erreur clic onglet away last5 : {e}")

                games_of_day[game_id] = {
                    "gameId":    game_id,
                    "date":      date_iso,
                    "time_ci":   time_ci,      # heure locale CI, format 24h "HH:MM"
                    "league":    league_name,
                    "match_url": match_url,

                    "home": {
                        "team":      team1,
                        "team_id":   team_id_home,
                        "team_slug": slug_home,
                        "logo":      logo_home,
                        "url":       f"https://www.espn.com/soccer/team/_/id/{team_id_home}" if team_id_home else None,
                        "last_five": last5_home,
                    },
                    "away": {
                        "team":      team2,
                        "team_id":   team_id_away,
                        "team_slug": slug_away,
                        "logo":      logo_away,
                        "url":       f"https://www.espn.com/soccer/team/_/id/{team_id_away}" if team_id_away else None,
                        "last_five": last5_away,
                    },

                    "odds": {
                        "home": ml["home"] if ml else None,
                        "away": ml["away"] if ml else None,
                        "draw": ml["draw"] if ml else None,
                    },

                    "stats":  match_stats,
                    "h2h":    h2h,
                }

                odds_str = f"✅ {ml['home']} / {ml['draw']} / {ml['away']}" if ml else "ℹ️  pas de cotes"
                h2h_str  = f"🔁 {len(h2h)} H2H" if h2h else "🔁 pas de H2H"
                l5_str   = f"🏠{len(last5_home)} ✈️{len(last5_away)}"
                print(f"  {team1} vs {team2} [{time_ci}] → {odds_str} | {h2h_str} | L5:{l5_str}")
                time.sleep(0.5)

finally:
    driver.quit()

# ================= SAUVEGARDE ATOMIQUE =================
tmp_file = OUTPUT_FILE + ".tmp"
with open(tmp_file, "w", encoding="utf-8") as f:
    json.dump(list(games_of_day.values()), f, indent=2, ensure_ascii=False)
os.replace(tmp_file, OUTPUT_FILE)

print(f"\n💾 {len(games_of_day)} matchs sauvegardés → {OUTPUT_FILE}")