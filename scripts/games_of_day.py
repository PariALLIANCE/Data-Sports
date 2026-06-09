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

def convert_time_to_utc(time_str):
    try:
        dt = datetime.strptime(time_str, "%I:%M %p")
        return f"{(dt.hour - 4) % 24:02d}:{dt.minute:02d}"
    except:
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
    match = re.search(r"/(\d+)\.png$", logo_url)
    return match.group(1) if match else None

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
    Extrait les 5 derniers matchs H2H depuis la section Head-To-Head ESPN.
    Retourne une liste de dicts avec date, competition, score_home, score_away,
    venue (@HOME ou @AWAY depuis la perspective de l'équipe home du match du jour),
    match_url et résultat (W/D/L) du point de vue de l'équipe home du match du jour.
    """
    h2h_list = []
    try:
        # Sélecteur pour la section H2H (nouveau layout "prism")
        section = soup.find("section", {"data-testid": "prism-LayoutCard"})
        if not section:
            # Fallback ancien layout
            section = soup.find("section", class_=re.compile(r".*Head.*To.*Head.*", re.I))
        if not section:
            return h2h_list

        # Chaque ligne de match H2H
        rows = section.select("div.mLASH.rpjsZ.TzFuW")
        for row in rows:
            try:
                # Lien du match
                link_tag = row.select_one("a[data-game-link='true']")
                match_url = ("https://www.espn.com" + link_tag["href"]) if link_tag and link_tag.get("href") else None

                # Scores : deux blocs score (left = home de ce match H2H, right = away)
                score_divs = row.select("div.mLASH.RRvbN")
                score_left  = score_divs[0].select_one("div.mLASH.LiUVm, div.mLASH.rbmla")
                score_right = score_divs[1].select_one("div.mLASH.LiUVm, div.mLASH.rbmla") if len(score_divs) > 1 else None

                # On récupère uniquement le chiffre (pas le SVG winner arrow)
                def clean_score(div):
                    if not div:
                        return None
                    # Retirer les sous-éléments (ex: svg arrow winner)
                    for sub in div.select("div, svg"):
                        sub.decompose()
                    return div.get_text(strip=True)

                score_left_val  = clean_score(score_left)
                score_right_val = clean_score(score_right)

                # Compétition
                comp_div = row.select_one("div.LiUVm.PLrIT")
                competition = comp_div.get_text(strip=True) if comp_div else None

                # Date
                date_div = row.select_one("div.uMFIG")
                date_raw = date_div.get_text(strip=True) if date_div else None
                try:
                    date_iso = datetime.strptime(date_raw, "%m/%d/%y").strftime("%Y-%m-%d") if date_raw else None
                except:
                    date_iso = date_raw

                # Venue : "@ FOR" ou "@ NAU" → indique où se jouait le match
                venue_span = row.select_one("span.LiUVm.FWLyZ")
                venue_text = venue_span.get_text(strip=True) if venue_span else None

                h2h_list.append({
                    "date":        date_iso,
                    "competition": competition,
                    "score_left":  score_left_val,
                    "score_right": score_right_val,
                    "venue":       venue_text,
                    "match_url":   match_url,
                })
            except Exception as e:
                print(f"    ⚠️ Erreur ligne H2H : {e}")
                continue

    except Exception as e:
        print(f"  ⚠️ Erreur H2H globale : {e}")

    return h2h_list

# ================= EXTRACTION DERNIERS MATCHS (LAST 5) =================
def extract_last_five(soup, team_abbr):
    """
    Extrait les 5 derniers matchs d'une équipe depuis la section LastGamesV4.
    team_abbr : ex 'NAU' ou 'FOR' — correspond au bouton actif (Button--active).
    
    Comme ESPN affiche les deux équipes dans la même section avec des onglets,
    on cherche la section dont le bouton actif correspond à team_abbr.
    Retourne une liste de dicts.
    """
    last_five = []
    try:
        # Il peut y avoir plusieurs sections LastGamesV4 (une par équipe)
        sections = soup.find_all("section", {"data-testid": "lastGames"})
        
        target_section = None
        for sec in sections:
            # Cherche le bouton actif
            active_btn = sec.select_one("button.Button--active")
            if active_btn:
                abbr_span = active_btn.select_one("span.LastGames__TeamName")
                abbr_text = abbr_span.get_text(strip=True) if abbr_span else ""
                if team_abbr.upper() in abbr_text.upper():
                    target_section = sec
                    break

        if not target_section:
            # Fallback : prendre la première section disponible
            if sections:
                target_section = sections[0]
            else:
                return last_five

        rows = target_section.select("tbody tr.Table__TR")
        for row in rows:
            try:
                tds = row.select("td.Table__TD")
                if len(tds) < 4:
                    continue

                # Date
                date_raw = tds[0].get_text(strip=True)
                try:
                    date_iso = datetime.strptime(date_raw, "%m/%d/%y").strftime("%Y-%m-%d")
                except:
                    date_iso = date_raw

                # Adversaire
                opp_td   = tds[1]
                at_span  = opp_td.select_one("span.atVs")
                venue    = at_span.get_text(strip=True) if at_span else ""  # "@" ou "vs"
                opp_abbr_span = opp_td.select_one("span.OppAbbr")
                opp_name = opp_abbr_span.get_text(strip=True) if opp_abbr_span else ""
                opp_link_tag = opp_td.select_one("a.AnchorLink")
                opp_url  = ("https://www.espn.com" + opp_link_tag["href"]) if opp_link_tag and opp_link_tag.get("href") else None

                # Logo adversaire → team_id
                opp_logo_img = opp_td.select_one("img")
                opp_logo_src = opp_logo_img["src"] if opp_logo_img else None
                opp_team_id  = extract_team_id_from_logo(opp_logo_src)

                # Résultat
                result_td    = tds[2]
                result_link  = result_td.select_one("a.AnchorLink")
                match_url    = ("https://www.espn.com" + result_link["href"]) if result_link and result_link.get("href") else None
                result_span  = result_td.select_one("span.GameResults")
                result       = result_span.get_text(strip=True) if result_span else None  # W / D / L
                score_span   = result_td.select_one("span.Score")
                score        = score_span.get_text(strip=True) if score_span else None

                # Compétition
                comp_td      = tds[3]
                competition  = comp_td.get_text(strip=True)

                last_five.append({
                    "date":        date_iso,
                    "venue":       venue,          # "@" = away, "vs" = home
                    "opponent":    opp_name,
                    "opponent_id": opp_team_id,
                    "opponent_url": opp_url,
                    "result":      result,         # W / D / L
                    "score":       score,
                    "competition": competition,
                    "match_url":   match_url,
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

                # ── Chargement unique de la page du match ──
                match_soup = get_soup(
                    driver,
                    match_url,
                    wait_selector=(
                        'img[data-testid="prism-image"], '
                        '[data-testid="OddsCell"], '
                        'section[data-testid="lastGames"], '
                        'section[data-testid="prism-LayoutCard"]'
                    ),
                    timeout=20,
                )
                time.sleep(1)

                # ── Logos & IDs extraits depuis la page du match ──
                logo_home, logo_away = extract_logos_from_match_page(match_soup)
                team_id_home = extract_team_id_from_logo(logo_home)
                team_id_away = extract_team_id_from_logo(logo_away)

                # ── Cotes extraites depuis la même soup ──
                ml = extract_ml_odds(match_soup)

                # ── Stats extraites depuis la même soup ──
                match_stats = extract_match_stats(match_soup)

                # ── H2H extrait depuis la même soup ──
                h2h = extract_h2h(match_soup)

                # ── Déduction des abréviations depuis les logos ──
                # On cherche dans la section LastGamesV4 les abréviations réelles
                last5_sections = match_soup.find_all("section", {"data-testid": "lastGames"})
                abbr_home, abbr_away = None, None
                if last5_sections:
                    for sec in last5_sections:
                        btns = sec.select("button.Button--filter span.LastGames__TeamName")
                        if len(btns) >= 2:
                            abbr_home = btns[0].get_text(strip=True).strip()
                            abbr_away = btns[1].get_text(strip=True).strip()
                            # Nettoyer les espaces et éventuels artefacts
                            # Les spans contiennent img + texte, get_text peut donner "NAU"
                            # On extrait proprement
                            def get_abbr(btn_span):
                                txt = btn_span.get_text(strip=True)
                                # Enlever éventuels caractères non-alpha
                                return re.sub(r'[^A-Z]', '', txt.upper()) or txt.strip()
                            abbr_home = get_abbr(btns[0])
                            abbr_away = get_abbr(btns[1])
                            break

                # ── Last 5 matchs home ──
                last5_home = extract_last_five(match_soup, abbr_home) if abbr_home else []

                # ── Last 5 matchs away ──
                # Pour l'équipe away, on a besoin que la section avec abbr_away soit active.
                # ESPN affiche les deux équipes dans la même section avec onglets JS.
                # On tente de cliquer sur l'onglet away via Selenium pour charger ses données.
                last5_away = []
                if abbr_away:
                    try:
                        # Chercher le bouton de l'équipe away et cliquer dessus
                        away_btn = None
                        btns_el = driver.find_elements(
                            By.CSS_SELECTOR,
                            "section[data-testid='lastGames'] button.Button--filter"
                        )
                        for btn_el in btns_el:
                            if abbr_away.upper() in btn_el.text.upper():
                                away_btn = btn_el
                                break

                        if away_btn:
                            driver.execute_script("arguments[0].click();", away_btn)
                            time.sleep(1.5)
                            away_soup = BeautifulSoup(driver.page_source, "html.parser")
                            last5_away = extract_last_five(away_soup, abbr_away)
                        else:
                            print(f"  ⚠️ Bouton away '{abbr_away}' introuvable pour last5")
                    except Exception as e:
                        print(f"  ⚠️ Erreur clic onglet away last5 : {e}")

                games_of_day[game_id] = {
                    "gameId":    game_id,
                    "date":      date_iso,
                    "time_utc":  convert_time_to_utc(raw_time) if raw_time else None,
                    "league":    league_name,
                    "match_url": match_url,

                    "home": {
                        "team":      team1,
                        "team_id":   team_id_home,
                        "logo":      logo_home,
                        "url":       f"https://www.espn.com/soccer/team/_/id/{team_id_home}" if team_id_home else None,
                        "last_five": last5_home,
                    },
                    "away": {
                        "team":      team2,
                        "team_id":   team_id_away,
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
                logo_str  = f"🖼️  {team_id_home} / {team_id_away}" if team_id_home else "🖼️  logos manquants"
                h2h_str   = f"🔁 {len(h2h)} H2H" if h2h else "🔁 pas de H2H"
                l5h_str   = f"🏠 {len(last5_home)} matchs" if last5_home else "🏠 0 matchs"
                l5a_str   = f"✈️  {len(last5_away)} matchs" if last5_away else "✈️  0 matchs"
                print(f"  {team1} vs {team2} → {odds_str} | {stats_str} | {logo_str} | {h2h_str} | {l5h_str} | {l5a_str}")
                time.sleep(0.5)

finally:
    driver.quit()

# ================= SAUVEGARDE ATOMIQUE =================
tmp_file = OUTPUT_FILE + ".tmp"
with open(tmp_file, "w", encoding="utf-8") as f:
    json.dump(list(games_of_day.values()), f, indent=2, ensure_ascii=False)
os.replace(tmp_file, OUTPUT_FILE)

print(f"\n💾 {len(games_of_day)} matchs sauvegardés → {OUTPUT_FILE}")