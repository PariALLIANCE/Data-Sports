import json
from datetime import datetime, timezone
import re
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup, NavigableString
from webdriver_manager.chrome import ChromeDriverManager

# ===============================================================
# DRIVER
# ===============================================================

def make_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_argument("--lang=en-US")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
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

# ===============================================================
# DOSSIERS
# ===============================================================

BASE_DIR      = "data/football"
STANDINGS_DIR = os.path.join(BASE_DIR, "standings")
os.makedirs(BASE_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(BASE_DIR, "games_of_day.json")

# ===============================================================
# LIGUES
# ===============================================================

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

# ===============================================================
# DATE
# ===============================================================

today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ===============================================================
# UTILITAIRES
# ===============================================================

def convert_date_to_iso(date_text):
    try:
        return datetime.strptime(date_text, "%A, %B %d, %Y").strftime("%Y-%m-%d")
    except Exception:
        return date_text

def convert_time_espn_to_ci(time_str):
    if not time_str:
        return None
    try:
        cleaned = time_str.strip().replace("\u202f", " ").replace("\xa0", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).upper()
        if "AM" in cleaned or "PM" in cleaned:
            if " " in cleaned:
                dt_eastern = datetime.strptime(cleaned, "%I:%M %p")
            else:
                dt_eastern = datetime.strptime(cleaned, "%I:%M%p")
            hour_ci = (dt_eastern.hour + 4) % 24
            return f"{hour_ci:02d}:{dt_eastern.minute:02d}"
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
    except Exception:
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

def build_logo_url(team_id, size=500):
    if not team_id:
        return None
    return f"https://a.espncdn.com/i/teamlogos/soccer/{size}/{team_id}.png"

# ===============================================================
# EXTRACTION LOGOS DEPUIS LA PAGE DU MATCH
# ===============================================================

def extract_logos_from_match_page(soup):
    imgs = soup.select('img[data-testid="prism-image"]')
    logo_home = imgs[0]["src"] if len(imgs) >= 1 else None
    logo_away = imgs[1]["src"] if len(imgs) >= 2 else None
    return logo_home, logo_away

# ===============================================================
# EXTRACTION COTES ESPN
# ===============================================================

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
            except Exception:
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

# ===============================================================
# EXTRACTION STATS — NOUVELLE STRUCTURE ESPN (ProgressBar / Prism)
# Structure : home_val | label | away_val avec balises <p class="...">
# ===============================================================

def extract_match_stats_prism(soup):
    """
    Extrait les stats depuis la section 'Team Stats' ESPN nouvelle UI.
    Structure détectée :
      <section data-testid="prism-LayoutCard">
        <h2>Team Stats</h2>
        <div class="THHyw">
          <div class="jaZjJ">
            <p ...><span>75%</span></p>   ← home
            <p ...>Possession</p>          ← label
            <p ...><span>25%</span></p>   ← away
          </div>
          <div data-testid="prism-ProgressBar">...</div>
        </div>
        ...
    """
    stats = {}
    try:
        # Cherche la section Team Stats
        section = None
        for sec in soup.find_all("section", {"data-testid": "prism-LayoutCard"}):
            h2 = sec.find("h2", {"data-testid": "prism-LayoutCardSlot"})
            if h2 and "stat" in h2.get_text(strip=True).lower():
                section = sec
                break

        if not section:
            return stats

        # Chaque stat est dans un div.THHyw
        stat_blocks = section.select("div.THHyw")
        for block in stat_blocks:
            # Les 3 <p> : home, label, away
            paragraphs = block.select("div.jaZjJ p")
            if len(paragraphs) < 3:
                continue

            # home value = span dans 1er p (classe OrMJA = home side)
            home_span = paragraphs[0].find("span")
            home_val  = home_span.get_text(strip=True) if home_span else paragraphs[0].get_text(strip=True)

            # label = 2e p (texte direct, souvent dans un span ou texte brut)
            label = paragraphs[1].get_text(strip=True)

            # away value = span dans 3e p
            away_span = paragraphs[2].find("span")
            away_val  = away_span.get_text(strip=True) if away_span else paragraphs[2].get_text(strip=True)

            if label:
                stats[label] = {"home": home_val, "away": away_val}

    except Exception as e:
        print(f"  ⚠️ Erreur stats prism : {e}")

    return stats

def extract_match_stats(soup):
    """
    Essaie d'abord la nouvelle structure Prism ESPN,
    puis tombe en fallback sur les anciennes méthodes.
    """
    # Méthode 1 : nouvelle UI Prism (ProgressBar)
    stats = extract_match_stats_prism(soup)
    if stats:
        return stats

    # Méthode 2 : StatCellContent (ancienne UI)
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
    except Exception:
        pass

    # Méthode 3 : GameStat
    try:
        game_stat_rows = soup.select("div.GameStat")
        if game_stat_rows:
            for row in game_stat_rows:
                cols  = row.select("div")
                texts = [c.get_text(strip=True) for c in cols if c.get_text(strip=True)]
                if len(texts) >= 3:
                    stats[texts[1]] = {"home": texts[0], "away": texts[2]}
            if stats:
                return stats
    except Exception:
        pass

    return {}

# ===============================================================
# EXTRACTION STATS DU MATCH (script 1 — Selenium CSS avancé)
# Utilisée pour les pages de matchs passés (last5 / H2H)
# ===============================================================

def get_match_stats_selenium(driver, game_id):
    url = f"https://www.espn.com/soccer/match/_/gameId/{game_id}"
    try:
        driver.get(url)
        WebDriverWait(driver, 12).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "section[data-testid='prism-LayoutCard']")
            )
        )
    except TimeoutException:
        pass
    except WebDriverException as e:
        print(f"    ⚠️  WebDriver erreur stats ({game_id}) : {e}")
        return {}

    # Tente d'abord la nouvelle structure via BeautifulSoup
    soup = BeautifulSoup(driver.page_source, "html.parser")
    stats = extract_match_stats_prism(soup)
    if stats:
        return stats

    # Fallback : Selenium CSS avancé (ancienne UI)
    try:
        stats_section = driver.find_element(
            By.CSS_SELECTOR, "section[data-testid='prism-LayoutCard']"
        )
        rows  = stats_section.find_elements(By.CSS_SELECTOR, "div.LOSQp")
        for row in rows:
            try:
                name_tag = row.find_element(By.CSS_SELECTOR, "span.OkRBU")
                values   = row.find_elements(By.CSS_SELECTOR, "span.bLeWt")
                if name_tag and len(values) >= 2:
                    stats[name_tag.text.strip()] = {
                        "home": values[0].text.strip(),
                        "away": values[1].text.strip(),
                    }
            except NoSuchElementException:
                continue
        time.sleep(0.6)
        return stats
    except NoSuchElementException:
        return {}
    except Exception as e:
        print(f"    ⚠️  Erreur stats selenium ({game_id}) : {e}")
        return {}

# ===============================================================
# EXTRACTION ÉVÉNEMENTS — MATCH TIMELINE
# Structure ESPN Prism :
#   <section data-testid="prism-LayoutCard">
#     <h2>Match Timeline</h2>
#     <div class="XYehN ThkOQ">          ← rangée home (haut) ou away (bas)
#       <div role="button" style="left: XX%">
#         <svg data-icon="soccer-goal02|soccer-card03|soccer-substitution02">
# Légende :
#   soccer-goal02         → but
#   soccer-card03 jaune   → carton jaune  (fill penaltyYellow)
#   soccer-card03 rouge   → carton rouge  (fill red)
#   soccer-substitution02 → remplacement
#
# Pourcentage left → minute = left% * 90 / 100  (approximation sur 90 min)
# ===============================================================

def _icon_type_from_svg(svg_tag):
    """Retourne le type d'événement depuis l'attribut data-icon du SVG."""
    if not svg_tag:
        return "unknown"
    icon = svg_tag.get("data-icon", "")
    if icon == "soccer-goal02":
        return "goal"
    if icon == "soccer-substitution02":
        return "substitution"
    if icon == "soccer-card03":
        # Couleur déterminée par le fill du <path>
        path = svg_tag.find("path")
        if path:
            fill = path.get("fill", "")
            if "red" in fill.lower() or "ff3232" in fill.lower() or "940005" in fill.lower():
                return "red_card"
            if "yellow" in fill.lower() or "ffff00" in fill.lower() or "penaltyyellow" in fill.lower():
                return "yellow_card"
        return "card"
    return "unknown"

def _left_to_minute(left_str):
    """
    Convertit le style left: XX.XX% en minute approximative.
    ESPN étale KO (≈2.4%) à FT (≈97.6%) sur 90 min (+ éventuelles prolongations).
    On ramène [2.4 ; 97.6] → [0 ; 90].
    """
    try:
        pct = float(left_str.replace("%", "").strip())
        # KO ≈ 2.44%  FT ≈ 97.56%  → plage utile ≈ 95.12 pts de %
        minute = round((pct - 2.44) * 90 / 95.12)
        return max(0, minute)
    except Exception:
        return None

def extract_match_events(soup):
    """
    Retourne un dict :
    {
        "home": [{"minute": 27, "type": "goal"}, ...],
        "away": [{"minute": 39, "type": "yellow_card"}, ...]
    }
    """
    events = {"home": [], "away": []}

    try:
        # Trouve la section Match Timeline
        timeline_section = None
        for sec in soup.find_all("section", {"data-testid": "prism-LayoutCard"}):
            h2 = sec.find("h2", {"data-testid": "prism-LayoutCardSlot"})
            if h2:
                title_text = h2.get_text(strip=True).lower()
                if "timeline" in title_text or "match" in title_text:
                    timeline_section = sec
                    break
            # Fallback : cherche via le span enfant
            span = sec.find("span", class_=lambda c: c and "lZur" in c)
            if span and "timeline" in span.get_text(strip=True).lower():
                timeline_section = sec
                break

        if not timeline_section:
            print("  ℹ️  Section Timeline introuvable")
            return events

        # Les deux rangées d'événements sont dans des div.XYehN.ThkOQ
        # Ordre DOM : première rangée = HOME (haut), deuxième = AWAY (bas)
        rows = timeline_section.select("div.XYehN.ThkOQ")

        for row_idx, row in enumerate(rows):
            side = "home" if row_idx == 0 else "away"

            # Chaque événement est un div[role="button"] avec un style left:XX%
            event_divs = row.select("div[role='button'][style]")
            for ev_div in event_divs:
                style = ev_div.get("style", "")
                left_match = re.search(r"left\s*:\s*([\d.]+%)", style)
                if not left_match:
                    continue
                minute = _left_to_minute(left_match.group(1))

                svg = ev_div.find("svg")
                ev_type = _icon_type_from_svg(svg)

                events[side].append({
                    "minute": minute,
                    "type":   ev_type,
                })

        # Tri par minute
        events["home"].sort(key=lambda x: x["minute"] or 0)
        events["away"].sort(key=lambda x: x["minute"] or 0)

    except Exception as e:
        print(f"  ⚠️ Erreur events timeline : {e}")

    return events

# ===============================================================
# EXTRACTION CLASSEMENT — POSITIONS ACTUELLES + PROJETÉES
# Structure ESPN (fournie en doc) :
#   <a data-clubhouse-uid="s:600~t:XXXX" href="/soccer/team/_/id/XXXX/slug">
#     <span class="Standings__TeamName">Nom</span>
#   </a>
#   TDs suivants : GP W D L GD P
#
# Position actuelle  = data-idx + 1
# Position projetée si victoire :
#   - On recalcule les points (P+3) et on compte combien d'équipes
#     ont plus de points que l'équipe après victoire → nouvelle position.
# ===============================================================

def extract_standings_for_match(soup, team_id_home, team_id_away):
    """
    Retourne un dict :
    {
        "home": {
            "position_current": 12,
            "position_if_win":  10,
            "played": 13, "won": 4, "drawn": 5, "lost": 4,
            "gd": 0, "points": 17
        },
        "away": { ... }
    }
    Retourne None si le classement est introuvable.
    """
    result = {"home": None, "away": None}

    try:
        # Cherche la table de classement dans la page du match
        # ESPN embarque parfois les standings dans un <section> ou <div class="Card">
        standings_tables = soup.select(
            "div.ResponsiveTable.Table__noConference, "
            "div.ResponsiveTable, "
            "section.Card table"
        )

        # On va aussi chercher directement les lignes avec data-clubhouse-uid
        all_rows = soup.select("tr.Table__TR.Table__TR--sm")

        if not all_rows:
            return result

        # Reconstruit le tableau complet : liste de dicts par équipe
        table = []
        for row in all_rows:
            uid_td = row.select_one("td a[data-clubhouse-uid]")
            if not uid_td:
                continue
            uid = uid_td.get("data-clubhouse-uid", "")
            m   = re.search(r"t:(\d+)", uid)
            if not m:
                continue
            tid = m.group(1)

            tds = row.select("td")
            if len(tds) < 7:
                continue

            def safe_int(s):
                try:
                    return int(s.replace("+", "").replace("−", "-").strip())
                except Exception:
                    return 0

            texts = [td.get_text(strip=True) for td in tds]
            # texts[0] = team name, [1]=GP, [2]=W, [3]=D, [4]=L, [5]=GD, [6]=P
            table.append({
                "team_id": tid,
                "played":  safe_int(texts[1]),
                "won":     safe_int(texts[2]),
                "drawn":   safe_int(texts[3]),
                "lost":    safe_int(texts[4]),
                "gd":      safe_int(texts[5]),
                "points":  safe_int(texts[6]),
            })

        if not table:
            return result

        # Position actuelle = index dans le tableau (déjà trié par ESPN)
        for idx, entry in enumerate(table):
            entry["position_current"] = idx + 1

        def projected_position(team_id, table_snapshot):
            """
            Calcule la position projetée si l'équipe team_id gagne (+3 pts).
            On considère que les autres équipes gardent leurs pts actuels.
            """
            proj_points = {}
            for e in table_snapshot:
                if e["team_id"] == team_id:
                    proj_points[e["team_id"]] = e["points"] + 3
                else:
                    proj_points[e["team_id"]] = e["points"]

            # Compte combien d'équipes ont STRICTEMENT plus de points
            my_pts = proj_points[team_id]
            better = sum(1 for tid, pts in proj_points.items() if pts > my_pts)
            return better + 1  # position = nb d'équipes devant + 1

        # Cherche home et away dans le tableau
        for entry in table:
            if entry["team_id"] == team_id_home:
                result["home"] = {
                    "position_current": entry["position_current"],
                    "position_if_win":  projected_position(team_id_home, table),
                    "played":  entry["played"],
                    "won":     entry["won"],
                    "drawn":   entry["drawn"],
                    "lost":    entry["lost"],
                    "gd":      entry["gd"],
                    "points":  entry["points"],
                }
            if entry["team_id"] == team_id_away:
                result["away"] = {
                    "position_current": entry["position_current"],
                    "position_if_win":  projected_position(team_id_away, table),
                    "played":  entry["played"],
                    "won":     entry["won"],
                    "drawn":   entry["drawn"],
                    "lost":    entry["lost"],
                    "gd":      entry["gd"],
                    "points":  entry["points"],
                }

    except Exception as e:
        print(f"  ⚠️ Erreur standings extraction : {e}")

    return result

# ===============================================================
# IDs ÉQUIPES DEPUIS LE GAMESTRIP (script 1)
# ===============================================================

def extract_team_ids_gamestrip(driver):
    ids = []
    try:
        container = driver.find_element(By.CSS_SELECTOR, "div.Gamestrip__Container")
        links = container.find_elements(
            By.CSS_SELECTOR, "a[data-clubhouse-uid][href*='/soccer/team/_/id/']"
        )
        seen = []
        for a in links:
            href = a.get_attribute("href") or ""
            m = re.search(r"/soccer/team/_/id/(\d+)/", href)
            if not m:
                continue
            tid = m.group(1)
            if tid not in seen:
                seen.append(tid)
        ids = seen
    except Exception as e:
        print(f"    ⚠️  Erreur IDs gamestrip : {e}")

    home_id = ids[0] if len(ids) > 0 else None
    away_id = ids[1] if len(ids) > 1 else None
    return home_id, away_id

# ===============================================================
# NOMS DEPUIS LE CLASSEMENT (script 1)
# ===============================================================

def build_standings_name_map(driver):
    name_map = {}
    try:
        links = driver.find_elements(
            By.CSS_SELECTOR,
            "a.AnchorLink[data-clubhouse-uid][href*='/soccer/team/_/id/']"
        )
        for a in links:
            uid = a.get_attribute("data-clubhouse-uid") or ""
            m   = re.search(r"t:(\d+)", uid)
            if not m:
                continue
            team_id = m.group(1)
            try:
                name = a.find_element(
                    By.CSS_SELECTOR, "span.Standings__TeamName"
                ).text.strip()
            except NoSuchElementException:
                continue
            if name:
                name_map[team_id] = name
    except Exception as e:
        print(f"    ⚠️  Erreur standings name map : {e}")
    return name_map

# ===============================================================
# SCORE ET STATUT (script 1)
# ===============================================================

def extract_score_and_status(driver):
    home_score = away_score = status = None
    try:
        score_els = driver.find_elements(By.CSS_SELECTOR, "div.uCTxv")
        scores = [
            el.text.strip()
            for el in score_els
            if re.match(r"^\d+$", el.text.strip())
        ]
        if len(scores) >= 2:
            home_score, away_score = scores[0], scores[1]
        elif len(scores) == 1:
            home_score = scores[0]
    except Exception as e:
        print(f"    ⚠️  Erreur score : {e}")
    try:
        st_els   = driver.find_elements(By.CSS_SELECTOR, "span.zRALO")
        statuses = [el.text.strip() for el in st_els if el.text.strip()]
        if statuses:
            status = statuses[0]
    except Exception:
        pass
    return home_score, away_score, status

# ===============================================================
# SCRAPING D'UN MATCH PASSÉ (last5 / H2H) — enrichi avec events
# ===============================================================

def scrape_past_match(driver, url):
    """
    Charge une page de match ESPN et retourne :
    {
        gameId, url,
        team_home, team_home_id, team_home_logo,
        team_away, team_away_id, team_away_logo,
        home_score, away_score, status,
        stats, events
    }
    Retourne None en cas d'échec.
    """
    m = re.search(r"gameId/(\d+)", url)
    if not m:
        print(f"    ⚠️  gameId introuvable dans : {url}")
        return None
    game_id = m.group(1)

    print(f"    🔍 Traitement match passé gameId={game_id}")

    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.Gamestrip__Container"))
        )
    except TimeoutException:
        print(f"      ⚠️  Timeout gameId={game_id}")
        return None
    except WebDriverException as e:
        print(f"      ⚠️  WebDriver : {e}")
        return None

    time.sleep(1.2)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # IDs équipes
    home_id, away_id = extract_team_ids_gamestrip(driver)

    # Noms depuis classement
    name_map  = build_standings_name_map(driver)
    home_name = name_map.get(home_id) if home_id else None
    away_name = name_map.get(away_id) if away_id else None

    # Logos ESPN CDN
    home_logo = build_logo_url(home_id)
    away_logo = build_logo_url(away_id)

    # Score & statut
    home_score, away_score, status = extract_score_and_status(driver)

    # Stats (nouvelle structure Prism en priorité)
    stats = get_match_stats_selenium(driver, game_id)

    # Événements Timeline
    events = extract_match_events(soup)

    result = {
        "gameId":          game_id,
        "url":             url,
        "team_home":       home_name,
        "team_home_id":    home_id,
        "team_home_logo":  home_logo,
        "team_away":       away_name,
        "team_away_id":    away_id,
        "team_away_logo":  away_logo,
        "home_score":      home_score,
        "away_score":      away_score,
        "status":          status,
        "stats":           stats,
        "events":          events,
    }

    score_str = f"{home_score}-{away_score}" if home_score is not None else "?-?"
    ev_str    = f"⚡ {len(events['home'])}H/{len(events['away'])}A events"
    print(
        f"      ✅ {home_name} {score_str} {away_name} "
        f"[{status}] | 📊 {len(stats)} stats | {ev_str}"
    )
    return result

# ===============================================================
# EXTRACTION H2H
# ===============================================================

def extract_h2h(soup, home_team_id, away_team_id):
    h2h_list = []
    try:
        section = None
        for sec in soup.find_all("section", {"data-testid": "prism-LayoutCard"}):
            h2_tag = sec.find("h2", {"data-testid": "prism-LayoutCardSlot"})
            if h2_tag and "head" in h2_tag.get_text(strip=True).lower():
                section = sec
                break

        if not section:
            print("  ℹ️  Section H2H introuvable")
            return h2h_list

        match_rows = section.select("div.rpjsZ.TzFuW.lSDCP")

        for row in match_rows:
            try:
                link_tag   = row.select_one("a[data-game-link='true']")
                match_href = link_tag.get("href", "") if link_tag else ""
                match_url  = ("https://www.espn.com" + match_href) if match_href else None

                content = row.select_one("div.iEHPA.TzFuW")
                if not content:
                    continue

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
                        except Exception:
                            continue
                    if not date_iso:
                        date_iso = date_raw

                h2h_list.append({
                    "date":        date_iso,
                    "competition": competition,
                    "match_url":   match_url,
                })

            except Exception as e:
                print(f"    ⚠️ Erreur ligne H2H : {e}")
                continue

    except Exception as e:
        print(f"  ⚠️ Erreur H2H globale : {e}")

    return h2h_list

# ===============================================================
# EXTRACTION DERNIERS MATCHS (LAST 5)
# ===============================================================

def extract_last_five(soup, team_id):
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

                date_raw = tds[0].get_text(strip=True)
                date_iso = None
                for fmt in ("%m/%d/%y", "%m/%d/%Y"):
                    try:
                        date_iso = datetime.strptime(date_raw, fmt).strftime("%Y-%m-%d")
                        break
                    except Exception:
                        continue
                if not date_iso:
                    date_iso = date_raw

                result_td   = tds[2]
                result_link = result_td.select_one("a.AnchorLink")
                match_href  = result_link.get("href", "") if result_link else ""
                match_url   = ("https://www.espn.com" + match_href) if match_href else None

                result_span = result_td.select_one("span.GameResults")
                result      = result_span.get_text(strip=True) if result_span else None

                competition = tds[3].get_text(strip=True)

                last_five.append({
                    "date":        date_iso,
                    "competition": competition,
                    "match_url":   match_url,
                    "result":      result,
                })

            except Exception as e:
                print(f"    ⚠️ Erreur ligne last5 : {e}")
                continue

    except Exception as e:
        print(f"  ⚠️ Erreur last5 globale : {e}")

    return last_five

# ===============================================================
# CHARGEMENT STANDINGS
# ===============================================================

STANDINGS_FILE = os.path.join(STANDINGS_DIR, "Standings.json")
standings_data = {}
if os.path.exists(STANDINGS_FILE):
    with open(STANDINGS_FILE, "r", encoding="utf-8") as f:
        standings_data = json.load(f)
else:
    print(f"⚠️ Standings introuvables : {STANDINGS_FILE}")

# ===============================================================
# SCRAPING PRINCIPAL — MATCHS DU JOUR
# ===============================================================

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
                time_ci   = convert_time_espn_to_ci(raw_time) if raw_time else None

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

                # ── Slugs depuis les liens ──
                slug_home, slug_away = None, None
                for a_tag in match_soup.select("a[data-clubhouse-uid]"):
                    href = a_tag.get("href", "")
                    if team_id_home and f"/id/{team_id_home}/" in href:
                        m2 = re.search(r"/id/\d+/([^/\?]+)$", href)
                        if m2 and not slug_home:
                            slug_home = m2.group(1)
                    if team_id_away and f"/id/{team_id_away}/" in href:
                        m2 = re.search(r"/id/\d+/([^/\?]+)$", href)
                        if m2 and not slug_away:
                            slug_away = m2.group(1)

                # ── Cotes ──
                ml = extract_ml_odds(match_soup)

                # ── Stats (nouvelle structure Prism en priorité) ──
                match_stats = extract_match_stats(match_soup)

                # ── Événements Timeline ──
                match_events = extract_match_events(match_soup)

                # ── Classement actuel + projeté ──
                standings_info = extract_standings_for_match(
                    match_soup, team_id_home, team_id_away
                )

                # ── H2H ──
                h2h = extract_h2h(match_soup, team_id_home, team_id_away)

                # ── Last 5 home ──
                last5_home = extract_last_five(match_soup, team_id_home)

                # ── Last 5 away ──
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
                    "time_ci":   time_ci,
                    "league":    league_name,
                    "match_url": match_url,

                    "home": {
                        "team":           team1,
                        "team_id":        team_id_home,
                        "team_slug":      slug_home,
                        "logo":           logo_home,
                        "url":            f"https://www.espn.com/soccer/team/_/id/{team_id_home}" if team_id_home else None,
                        "standings":      standings_info.get("home"),   # ← NOUVEAU
                        "last_five":      last5_home,
                    },
                    "away": {
                        "team":           team2,
                        "team_id":        team_id_away,
                        "team_slug":      slug_away,
                        "logo":           logo_away,
                        "url":            f"https://www.espn.com/soccer/team/_/id/{team_id_away}" if team_id_away else None,
                        "standings":      standings_info.get("away"),   # ← NOUVEAU
                        "last_five":      last5_away,
                    },

                    "odds": {
                        "home": ml["home"] if ml else None,
                        "away": ml["away"] if ml else None,
                        "draw": ml["draw"] if ml else None,
                    },

                    "stats":   match_stats,
                    "events":  match_events,   # ← NOUVEAU
                    "h2h":     h2h,
                }

                odds_str  = f"✅ {ml['home']} / {ml['draw']} / {ml['away']}" if ml else "ℹ️  pas de cotes"
                h2h_str   = f"🔁 {len(h2h)} H2H" if h2h else "🔁 pas de H2H"
                l5_str    = f"🏠{len(last5_home)} ✈️{len(last5_away)}"
                ev_str    = f"⚡{len(match_events['home'])}H/{len(match_events['away'])}A"
                st_str    = (
                    f"📊#{standings_info['home']['position_current'] if standings_info['home'] else '?'}"
                    f"→#{standings_info['home']['position_if_win'] if standings_info['home'] else '?'}"
                )
                print(f"  {team1} vs {team2} [{time_ci}] → {odds_str} | {h2h_str} | L5:{l5_str} | {ev_str} | {st_str}")
                time.sleep(0.5)

    # ==============================================================
    # PHASE 2 — ENRICHISSEMENT DES URLs last5 ET H2H
    # ==============================================================

    print("\n" + "=" * 60)
    print("🔄 PHASE 2 — Enrichissement last5 & H2H")
    print("=" * 60)

    urls_to_scrape = {}

    for gid, gdata in games_of_day.items():
        for entry in gdata["home"]["last_five"]:
            u = entry.get("match_url")
            if u and u not in urls_to_scrape:
                urls_to_scrape[u] = None
        for entry in gdata["away"]["last_five"]:
            u = entry.get("match_url")
            if u and u not in urls_to_scrape:
                urls_to_scrape[u] = None
        for entry in gdata["h2h"]:
            u = entry.get("match_url")
            if u and u not in urls_to_scrape:
                urls_to_scrape[u] = None

    total = len(urls_to_scrape)
    print(f"  📋 {total} URLs uniques à enrichir\n")

    for idx, url in enumerate(urls_to_scrape, 1):
        print(f"  [{idx}/{total}] {url}")
        result = scrape_past_match(driver, url)
        urls_to_scrape[url] = result
        time.sleep(1)

    print("\n  💉 Injection des données enrichies…")

    for gid, gdata in games_of_day.items():

        # Champs injectés pour last5 et H2H (désormais avec events)
        def inject(entry):
            u = entry.get("match_url")
            if u and urls_to_scrape.get(u):
                d = urls_to_scrape[u]
                entry["team_home"]       = d.get("team_home")
                entry["team_home_id"]    = d.get("team_home_id")
                entry["team_home_logo"]  = d.get("team_home_logo")
                entry["team_away"]       = d.get("team_away")
                entry["team_away_id"]    = d.get("team_away_id")
                entry["team_away_logo"]  = d.get("team_away_logo")
                entry["home_score"]      = d.get("home_score")
                entry["away_score"]      = d.get("away_score")
                entry["status"]          = d.get("status")
                entry["stats"]           = d.get("stats", {})
                entry["events"]          = d.get("events", {"home": [], "away": []})  # ← NOUVEAU

        for entry in gdata["home"]["last_five"]:
            inject(entry)
        for entry in gdata["away"]["last_five"]:
            inject(entry)
        for entry in gdata["h2h"]:
            inject(entry)

    print("  ✅ Injection terminée")

finally:
    driver.quit()
    print("\n✅ Driver fermé.")

# ===============================================================
# SAUVEGARDE ATOMIQUE
# ===============================================================

tmp_file = OUTPUT_FILE + ".tmp"
with open(tmp_file, "w", encoding="utf-8") as f:
    json.dump(list(games_of_day.values()), f, indent=2, ensure_ascii=False)
os.replace(tmp_file, OUTPUT_FILE)

print(f"\n💾 {len(games_of_day)} matchs sauvegardés → {OUTPUT_FILE}")