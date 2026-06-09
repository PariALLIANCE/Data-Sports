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
from bs4 import BeautifulSoup

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
    ESPN affiche l'heure en US Eastern Time.
    En été  : Eastern = UTC-4  → Côte d'Ivoire (UTC+0) = Eastern + 4h
    En hiver: Eastern = UTC-5  → Côte d'Ivoire (UTC+0) = Eastern + 5h
    On utilise +4 (période estivale, mai-novembre).
    Retourne l'heure locale CI au format HH:MM.
    """
    try:
        # Normalise "1:30 PM", "1:30PM", "13:30" etc.
        time_str = time_str.strip().upper().replace("\u202f", " ")
        if "AM" in time_str or "PM" in time_str:
            # Format 12h
            fmt = "%I:%M %p" if " " in time_str.replace("AM","").replace("PM","").strip() else "%I:%M%p"
            dt = datetime.strptime(time_str, fmt)
            hour_utc = dt.hour + 4   # Eastern Summer → UTC
        else:
            # Format 24h déjà
            dt = datetime.strptime(time_str, "%H:%M")
            hour_utc = dt.hour + 4   # Suppose déjà Eastern → UTC
        hour_ci = hour_utc % 24
        return f"{hour_ci:02d}:{dt.minute:02d}"
    except Exception as e:
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
    """Extrait le team_id depuis l'URL du logo ESPN."""
    if not logo_url:
        return None
    match = re.search(r"/(\d+)\.png", logo_url)
    return match.group(1) if match else None

def extract_names_from_match_url(match_url):
    """
    Extrait les slugs home/away depuis l'URL du match ESPN.
    Ex: /soccer/match/_/gameId/401860130/nautico-botafogo-sp
    → ("nautico", "botafogo-sp")
    La convention ESPN est : gameId/XXXXXXX/HOME-AWAY
    où HOME et AWAY sont séparés par le dernier tiret du slug complet.
    On coupe sur le premier tiret entre les deux équipes en utilisant
    le gameId comme ancre.
    """
    if not match_url:
        return None, None
    # Extrait le slug après gameId/XXXXXXX/
    m = re.search(r"gameId/\d+/(.+)$", match_url.rstrip("/"))
    if not m:
        return None, None
    slug = m.group(1)  # ex: "nautico-botafogo-sp" ou "fortaleza-vitoria"
    # On ne peut pas toujours séparer les deux équipes de façon fiable
    # sans connaître les noms. On retourne le slug brut pour référence.
    return slug  # slug complet retourné, décomposé si besoin par l'appelant

def extract_team_id_from_team_url(team_url):
    """
    Extrait le team_id depuis l'URL d'équipe ESPN.
    Ex: /soccer/team/_/id/10281/botafogo-sp → '10281'
    """
    if not team_url:
        return None
    m = re.search(r"/id/(\d+)/", team_url)
    return m.group(1) if m else None

def extract_opponent_slug_from_match_url(match_url, own_team_id, own_team_slug):
    """
    Depuis l'URL du match /soccer/match/_/gameId/XXXXX/team1-team2,
    on déduit le slug de l'adversaire en retirant le slug de l'équipe connue.
    Retourne le slug de l'adversaire ou None.
    """
    if not match_url:
        return None
    m = re.search(r"gameId/\d+/(.+)$", match_url.rstrip("/"))
    if not m:
        return None
    full_slug = m.group(1)
    if own_team_slug and own_team_slug in full_slug:
        # Retire le slug de l'équipe connue + tiret séparateur
        opp = full_slug.replace(own_team_slug, "").strip("-")
        return opp if opp else full_slug
    return full_slug

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
    Parse la section Head-To-Head ESPN (nouveau layout prism).

    Structure HTML ciblée :
    <section data-testid="prism-LayoutCard">
      <h2>Head-To-Head</h2>
      <!-- Header avec logos des 2 équipes -->
      <div class="oimqG dCMNJ ...">
        <a href="/soccer/team/_/id/7633/nautico">  ← équipe gauche (home du match du jour)
        <a href="/soccer/team/_/id/6272/fortaleza"> ← équipe droite (away du match du jour)
      </div>
      <!-- Lignes de matchs H2H -->
      <div class="mLASH rpjsZ TzFuW ...">          ← une ligne par match
        <a data-game-link="true" href="/soccer/match/_/gameId/662243/nautico-fortaleza">
        <div class="mLASH iEHPA TzFuW ...">
          <div class="mLASH RRvbN ...">             ← score équipe gauche
            <div class="mLASH LiUVm ...">1</div>   (ou rbmla si winner)
          </div>
          <div class="mLASH VZTD rEPuv vIQoV QXDKT">
            <div class="LiUVm PLrIT KTwp FuEs">2023 Copa do Nordeste...</div>  ← compétition
            <div class="uMFIG ...">2/26/23</div>   ← date
            <span class="LiUVm FWLyZ ...">@ FOR</span> ← venue
          </div>
          <div class="mLASH RRvbN ...">             ← score équipe droite
            <div class="mLASH rbmla ...">2          (rbmla = winner, LiUVm = normal)
              <div class="mLASH xtUup ..."><svg .../></div>  ← flèche winner à ignorer
            </div>
          </div>
        </div>
      </div>
      ...
    </section>
    """
    h2h_list = []
    try:
        # ── Trouver la section H2H ──
        section = None
        for sec in soup.find_all("section", {"data-testid": "prism-LayoutCard"}):
            h2_tag = sec.find("h2", {"data-testid": "prism-LayoutCardSlot"})
            if h2_tag and "head" in h2_tag.get_text(strip=True).lower():
                section = sec
                break

        if not section:
            print("  ℹ️  Section H2H introuvable")
            return h2h_list

        # ── Extraire les slugs des deux équipes depuis le header ──
        header_links = section.select("div.oimqG a[data-testid='prism-linkbase']")
        slug_left, slug_right = None, None
        if len(header_links) >= 2:
            # Ex: href="/soccer/team/_/id/7633/nautico" → slug = "nautico"
            def slug_from_team_url(href):
                m = re.search(r"/id/\d+/([^/]+)$", href)
                return m.group(1) if m else None
            slug_left  = slug_from_team_url(header_links[0].get("href", ""))
            slug_right = slug_from_team_url(header_links[1].get("href", ""))

        # ── Parser chaque ligne de match H2H ──
        # Chaque ligne = div avec les classes rpjsZ ET TzFuW ET lSDCP
        match_rows = section.select("div.rpjsZ.TzFuW.lSDCP")

        for row in match_rows:
            try:
                # ── URL du match ──
                link_tag  = row.select_one("a[data-game-link='true']")
                match_href = link_tag.get("href", "") if link_tag else ""
                match_url  = ("https://www.espn.com" + match_href) if match_href else None

                # ── Slug du match pour retrouver home/away ──
                # Ex: /soccer/match/_/gameId/662243/nautico-fortaleza
                game_id_h2h = None
                m_gid = re.search(r"gameId/(\d+)", match_href)
                if m_gid:
                    game_id_h2h = m_gid.group(1)

                # ── Contenu principal de la ligne ──
                content_div = row.select_one("div.mLASH.iEHPA.TzFuW")
                if not content_div:
                    continue

                # ── Les deux blocs de score sont les div.mLASH.RRvbN ──
                score_blocks = content_div.select("div.mLASH.RRvbN")
                if len(score_blocks) < 2:
                    continue

                def parse_score_block(block):
                    """
                    Extrait le score numérique d'un bloc RRvbN.
                    Le div interne est soit LiUVm (perdant/nul) soit rbmla (gagnant).
                    Il peut contenir un sous-div xtUup avec SVG (flèche winner) à ignorer.
                    """
                    inner = block.select_one("div.LiUVm, div.rbmla")
                    if not inner:
                        return None, False
                    is_winner = "rbmla" in inner.get("class", []) and \
                                inner.select_one("div.xtUup") is not None
                    # Cloner le texte en ignorant les sous-divs
                    text_parts = []
                    for child in inner.children:
                        if hasattr(child, 'name'):
                            # Ignorer les sous-divs (contiennent SVG)
                            continue
                        text_parts.append(str(child).strip())
                    score_text = "".join(text_parts).strip()
                    return score_text if score_text else None, is_winner

                score_left_val,  left_is_winner  = parse_score_block(score_blocks[0])
                score_right_val, right_is_winner = parse_score_block(score_blocks[1])

                # ── Déterminer le résultat (W/D/L) du point de vue de l'équipe gauche ──
                if score_left_val is not None and score_right_val is not None:
                    try:
                        sl = int(score_left_val)
                        sr = int(score_right_val)
                        if sl > sr:
                            result_left = "W"
                        elif sl < sr:
                            result_left = "L"
                        else:
                            result_left = "D"
                    except:
                        result_left = None
                else:
                    result_left = "W" if left_is_winner else ("L" if right_is_winner else "D")

                # ── Compétition ──
                comp_div  = content_div.select_one("div.LiUVm.PLrIT.KTwp.FuEs")
                competition = comp_div.get_text(strip=True) if comp_div else None

                # ── Date ──
                date_div  = content_div.select_one("div.uMFIG")
                date_raw  = date_div.get_text(strip=True) if date_div else None
                date_iso  = None
                if date_raw:
                    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
                        try:
                            date_iso = datetime.strptime(date_raw, fmt).strftime("%Y-%m-%d")
                            break
                        except:
                            continue
                    if not date_iso:
                        date_iso = date_raw

                # ── Venue ──
                # "@ FOR" = joué chez Fortaleza, "@ NAU" = joué chez Nautico
                venue_span = content_div.select_one("span.LiUVm.FWLyZ")
                venue_text = venue_span.get_text(strip=True) if venue_span else None

                # ── Déterminer qui jouait à domicile dans ce match H2H ──
                # venue_text = "@ FOR" → FOR était à domicile dans ce match H2H
                # On compare avec slug_right (équipe away du match du jour)
                h2h_home_slug = None
                h2h_away_slug = None
                if venue_text and slug_right and slug_left:
                    venue_clean = venue_text.replace("@", "").strip().upper()
                    # Cherche si venue correspond à left ou right
                    if slug_right.upper().startswith(venue_clean) or \
                       venue_clean in slug_right.upper():
                        h2h_home_slug = slug_right
                        h2h_away_slug = slug_left
                    else:
                        h2h_home_slug = slug_left
                        h2h_away_slug = slug_right

                h2h_list.append({
                    "game_id":     game_id_h2h,
                    "date":        date_iso,
                    "competition": competition,
                    "score_left":  score_left_val,   # score équipe gauche (home du match du jour)
                    "score_right": score_right_val,  # score équipe away du match du jour
                    "result_left": result_left,      # W/D/L du point de vue équipe gauche
                    "venue":       venue_text,       # ex: "@ FOR"
                    "h2h_home":    h2h_home_slug,    # slug équipe recevante dans ce H2H
                    "h2h_away":    h2h_away_slug,    # slug équipe visiteuse dans ce H2H
                    "match_url":   match_url,
                })

            except Exception as e:
                print(f"    ⚠️ Erreur ligne H2H : {e}")
                continue

    except Exception as e:
        print(f"  ⚠️ Erreur H2H globale : {e}")

    return h2h_list

# ================= EXTRACTION DERNIERS MATCHS (LAST 5) =================
def extract_last_five(soup, team_slug):
    """
    Extrait les 5 derniers matchs d'une équipe.
    team_slug : slug ESPN de l'équipe, ex 'nautico' ou 'fortaleza'
                utilisé pour identifier quelle section est active.
    Les opponent_id et opponent_slug sont extraits depuis les URLs
    des matchs et des pages d'équipes adverses.
    """
    last_five = []
    try:
        sections = soup.find_all("section", {"data-testid": "lastGames"})

        target_section = None
        for sec in sections:
            active_btn = sec.select_one("button.Button--active")
            if active_btn:
                # Cherche le lien d'équipe dans les boutons pour matcher le slug
                team_img = active_btn.select_one("img")
                if team_img:
                    img_src = team_img.get("src", "")
                    tid = extract_team_id_from_logo(img_src)
                    # On vérifie aussi via data-clubhouse-uid si dispo
                    uid_attr = active_btn.get("data-clubhouse-uid", "")
                    if team_slug and tid:
                        # Cherche un lien dans le header vers cette équipe
                        header_link = sec.select_one(f"a[href*='/{tid}/']")
                        if header_link:
                            target_section = sec
                            break
                # Fallback: match par texte
                btn_text = active_btn.get_text(strip=True).upper()
                if team_slug and team_slug[:3].upper() in btn_text:
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
                opp_td      = tds[1]
                at_span     = opp_td.select_one("span.atVs")
                venue       = at_span.get_text(strip=True) if at_span else ""

                # URL de l'équipe adverse → team_id + slug
                opp_link_tag = opp_td.select_one("a.AnchorLink")
                opp_team_url = opp_link_tag.get("href", "") if opp_link_tag else ""
                opp_team_id  = extract_team_id_from_team_url(opp_team_url)
                # Slug adversaire depuis l'URL : /soccer/team/_/id/10281/botafogo-sp → "botafogo-sp"
                opp_slug_match = re.search(r"/id/\d+/([^/\?]+)$", opp_team_url)
                opp_slug     = opp_slug_match.group(1) if opp_slug_match else None
                opp_full_url = ("https://www.espn.com" + opp_team_url) if opp_team_url else None

                # ── Résultat & score ──
                result_td   = tds[2]
                result_link = result_td.select_one("a.AnchorLink")
                match_href  = result_link.get("href", "") if result_link else ""
                match_url   = ("https://www.espn.com" + match_href) if match_href else None

                # game_id depuis l'URL du match
                gid_m = re.search(r"gameId/(\d+)", match_href)
                match_game_id = gid_m.group(1) if gid_m else None

                # Noms des équipes depuis le slug de l'URL du match
                # Ex: /soccer/match/_/gameId/401860130/nautico-botafogo-sp
                match_slug_m = re.search(r"gameId/\d+/(.+)$", match_href.rstrip("/"))
                match_slug   = match_slug_m.group(1) if match_slug_m else None

                result_span = result_td.select_one("span.GameResults")
                result      = result_span.get_text(strip=True) if result_span else None
                score_span  = result_td.select_one("span.Score")
                score       = score_span.get_text(strip=True) if score_span else None

                # ── Compétition ──
                comp_td    = tds[3]
                competition = comp_td.get_text(strip=True)

                last_five.append({
                    "date":          date_iso,
                    "venue":         venue,           # "@" = away, "vs" = home
                    "opponent_slug": opp_slug,        # ex: "botafogo-sp"
                    "opponent_id":   opp_team_id,     # ex: "10281"
                    "opponent_url":  opp_full_url,
                    "result":        result,           # W / D / L
                    "score":         score,
                    "competition":   competition,
                    "game_id":       match_game_id,
                    "match_slug":    match_slug,       # ex: "nautico-botafogo-sp"
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

                # ── Heure locale Côte d'Ivoire (UTC+0 = Eastern + 4h en été) ──
                time_ci = convert_time_espn_to_ci(raw_time) if raw_time else None

                # ── Chargement unique de la page du match ──
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

                # ── Slugs des équipes depuis les liens de la page ──
                slug_home, slug_away = None, None
                team_links = match_soup.select("a[data-clubhouse-uid]")
                for lnk in team_links:
                    href = lnk.get("href", "")
                    if team_id_home and f"/id/{team_id_home}/" in href:
                        m = re.search(r"/id/\d+/([^/\?]+)$", href)
                        if m:
                            slug_home = m.group(1)
                    if team_id_away and f"/id/{team_id_away}/" in href:
                        m = re.search(r"/id/\d+/([^/\?]+)$", href)
                        if m:
                            slug_away = m.group(1)

                # ── Cotes ──
                ml = extract_ml_odds(match_soup)

                # ── Stats ──
                match_stats = extract_match_stats(match_soup)

                # ── H2H ──
                h2h = extract_h2h(match_soup)

                # ── Last 5 home (onglet home déjà actif par défaut) ──
                last5_home = extract_last_five(match_soup, slug_home)

                # ── Last 5 away (clic sur l'onglet away via Selenium) ──
                last5_away = []
                try:
                    away_btns = driver.find_elements(
                        By.CSS_SELECTOR,
                        "section[data-testid='lastGames'] button.Button--filter"
                    )
                    # Le bouton away est le 2ème (index 1)
                    if len(away_btns) >= 2:
                        driver.execute_script("arguments[0].click();", away_btns[1])
                        time.sleep(1.5)
                        away_soup  = BeautifulSoup(driver.page_source, "html.parser")
                        last5_away = extract_last_five(away_soup, slug_away)
                    else:
                        print(f"  ⚠️ Bouton away last5 introuvable")
                except Exception as e:
                    print(f"  ⚠️ Erreur clic onglet away last5 : {e}")

                games_of_day[game_id] = {
                    "gameId":    game_id,
                    "date":      date_iso,
                    "time_ci":   time_ci,     # heure locale Côte d'Ivoire
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

                    "stats": match_stats,
                    "h2h":   h2h,
                }

                odds_str  = f"✅ {ml['home']} / {ml['draw']} / {ml['away']}" if ml else "ℹ️  pas de cotes"
                stats_str = f"📊 {len(match_stats)} stats" if match_stats else "📊 pas de stats"
                h2h_str   = f"🔁 {len(h2h)} H2H" if h2h else "🔁 pas de H2H"
                l5h_str   = f"🏠 {len(last5_home)}" if last5_home else "🏠 0"
                l5a_str   = f"✈️  {len(last5_away)}" if last5_away else "✈️  0"
                print(f"  {team1} vs {team2} [{time_ci}] → {odds_str} | {stats_str} | {h2h_str} | L5: {l5h_str}/{l5a_str}")
                time.sleep(0.5)

finally:
    driver.quit()

# ================= SAUVEGARDE ATOMIQUE =================
tmp_file = OUTPUT_FILE + ".tmp"
with open(tmp_file, "w", encoding="utf-8") as f:
    json.dump(list(games_of_day.values()), f, indent=2, ensure_ascii=False)
os.replace(tmp_file, OUTPUT_FILE)

print(f"\n💾 {len(games_of_day)} matchs sauvegardés → {OUTPUT_FILE}")