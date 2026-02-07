import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
import re

# ================= CONFIG =================
BASE_URL = "https://www.espn.com/nhl/schedule/_/date/"
OUTPUT_FILE = "data/hockey/leagues/NHL.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# ================= UTILS =================
def extract_team_from_href(href):
    """
    /nhl/team/_/name/bos/boston-bruins
    -> Boston Bruins, bos
    """
    parts = href.split("/")
    short = parts[-2]
    full_name = parts[-1].replace("-", " ").title()
    return full_name, short


def build_logo_url(short):
    return f"https://a.espncdn.com/i/teamlogos/nhl/500/{short}.png"


def extract_game_id(href):
    """
    /nhl/game/_/gameId/401561694
    -> 401561694
    """
    match = re.search(r'/gameId/(\d+)', href)
    return match.group(1) if match else None


def is_played_match(text):
    """
    Détecte un score : 'MTL 4, BUF 2' ou 'TOR 3, VAN 2 (SO)'
    """
    return bool(re.search(r"\d+\s*,\s*\w+\s*\d+", text))


def load_existing_games():
    """
    Charge les matchs existants depuis le fichier JSON
    Retourne un set de game_ids déjà présents et la liste complète
    """
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {game["game_id"] for game in data if "game_id" in game}, data
        except:
            return set(), []
    return set(), []


# ================= MAIN =================
def get_recent_played_games():
    """
    Récupère les matchs d'avant-hier et hier uniquement
    """
    # Charger les game_ids existants
    existing_ids, existing_games = load_existing_games()
    print(f"📂 {len(existing_ids)} matchs déjà en base")
    
    results = list(existing_games)  # Garder les matchs existants
    new_games = 0
    today = datetime.utcnow().date()
    
    # Avant-hier et hier
    dates_to_check = [
        today - timedelta(days=2),  # Avant-hier
        today - timedelta(days=1)   # Hier
    ]
    
    print(f"🔍 Vérification des matchs pour : {[d.isoformat() for d in dates_to_check]}")

    for current_date in dates_to_check:
        date_str = current_date.strftime("%Y%m%d")
        url = BASE_URL + date_str

        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code != 200:
                print(f"❌ Erreur HTTP {response.status_code} pour {current_date}")
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            rows = soup.select("tbody tr")

            games_found = 0
            for row in rows:
                score_link = row.select_one("td a[href*='/nhl/game/_/gameId']")
                if not score_link:
                    continue

                score_text = score_link.get_text(strip=True)

                if not is_played_match(score_text):
                    continue  # pas encore joué

                # Extraire le game_id
                game_id = extract_game_id(score_link["href"])
                if not game_id:
                    continue
                
                # Vérifier si le match existe déjà
                if game_id in existing_ids:
                    print(f"⏭️  Match {game_id} déjà présent, skip")
                    continue  # Match déjà enregistré, on skip

                # Récupérer toutes les cellules <td> de la ligne
                cells = row.select("td")
                
                away_team_link = None
                home_team_link = None
                
                if len(cells) >= 2:
                    # Équipe extérieure dans la première cellule
                    away_team_link = cells[0].select_one("a[href*='/nhl/team/_/name/']")
                    # Équipe domicile dans la deuxième cellule
                    home_team_link = cells[1].select_one("a[href*='/nhl/team/_/name/']")
                
                if not away_team_link or not home_team_link:
                    continue

                away_name, away_short = extract_team_from_href(away_team_link["href"])
                home_name, home_short = extract_team_from_href(home_team_link["href"])

                new_game = {
                    "game_id": game_id,
                    "date": current_date.isoformat(),
                    "score": score_text,
                    "away_team": {
                        "name": away_name,
                        "short": away_short,
                        "logo": build_logo_url(away_short)
                    },
                    "home_team": {
                        "name": home_name,
                        "short": home_short,
                        "logo": build_logo_url(home_short)
                    }
                }
                
                results.append(new_game)
                existing_ids.add(game_id)  # Ajouter au set pour éviter les doublons
                games_found += 1
                new_games += 1
                print(f"✅ Nouveau match ajouté : {away_short.upper()} vs {home_short.upper()} ({game_id})")

            if games_found > 0:
                print(f"📅 {current_date}: {games_found} nouveau(x) match(s) trouvé(s)")
            else:
                print(f"📅 {current_date}: Aucun nouveau match")

        except Exception as e:
            print(f"❌ Erreur pour {current_date}: {e}")

    print(f"\n✨ {new_games} nouveau(x) match(s) ajouté(s)")
    print(f"📊 Total : {len(results)} matchs dans la base")
    return results


# ================= SAVE =================
def save_json(data):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Fichier sauvegardé : {OUTPUT_FILE}")


if __name__ == "__main__":
    games = get_recent_played_games()
    save_json(games)
    print(f"✅ Terminé !")