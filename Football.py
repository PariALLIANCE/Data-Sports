import json
import time
import random
import ssl
import requests
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

# =====================================================
# TLS Adapter
# =====================================================

class TLS13Adapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        ctx.maximum_version = ssl.TLSVersion.TLSv1_3
        ctx.set_alpn_protocols(["h2", "http/1.1"])
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        ctx.maximum_version = ssl.TLSVersion.TLSv1_3
        ctx.set_alpn_protocols(["h2", "http/1.1"])
        kwargs["ssl_context"] = ctx
        return super().proxy_manager_for(*args, **kwargs)

# =====================================================
# Configuration
# =====================================================

HOST = "vqpi9pfespngna.com"
APPGUID = "e3e84e89ad06a492_2"

CHAMP_EXCLUSIONS = ["Paris spéciaux", "Statistiques", "Vainqueur", "Gagnant", "Statistique"]
TEAM_EXCLUSIONS = ["à domicile", "a domicile", "Winner"]

# Championnats à traiter (limité à l'Angleterre. Premier League pour l'instant).
# Ajouter d'autres IDs ici pour élargir le périmètre plus tard.
CHAMP_IDS = [88637]

# Cache mémoire pour les championnats/stages déjà récupérés durant l'exécution.
# Clé : nom du championnat (connu à l'avance pour le match principal) ou ID de match
# (pour les matchs passés, dont le championnat est inconnu tant qu'on n'a pas interrogé l'API).
STAGE_CACHE = {}

# Cache mémoire des logos d'équipe déjà résolus durant l'exécution (clé : ID équipe).
# Évite de reconstruire/re-résoudre le logo d'une équipe déjà rencontrée dans un
# match précédent (même équipe croisée dans plusieurs matchs du jour).
TEAM_LOGO_CACHE = {}

# =====================================================
# Mapping des groupes
# =====================================================

GROUP_MAPPING = {
    1: "1N2",
    2: "Double Chance",
    3: "Handicap",
    4: "Total buts",
    5: "Total domicile",
    6: "Total extérieur",
    21: "Les deux équipes marquent",
    22: "Total pair",
    26: "Equipe2 + Total",
    29: "Equipe1 + Total",
    42: "But dans chaque mi-temps",
    55: "Perd 1er set et gagne",
    58: "Equipe1 gagne au moins une mi-temps",
    59: "Equipe2 gagne au moins une mi-temps",
    62: "Nul au moins une mi-temps",
    66: "Penalty accordé",
    248: "Total balles de match",
    249: "Match gagné sur un Ace",
    346: "Premier Run",
    378: "Match supplémentaire",
    380: "Dernier Run",
    2009: "Mené sur les sets et gagne",
    3271: "Coups sûrs - Handicap",
    5557: "1N2 2up",
}

TYPE_MAPPING = {
    1: {1: "Equipe1", 2: "Nul", 3: "Equipe2"},
    2: {4: "1X", 5: "12", 6: "2X"},
    21: {180: "Oui", 181: "Non", 11273: "2 buts - Oui", 11274: "2 buts - Non"},
    4: {9: "Plus de", 10: "Moins de"},
    3: {7: "Handicap 1", 8: "Handicap 2"},
    5: {11: "+", 12: "-"},
    6: {13: "+", 14: "-"},
    22: {182: "Oui", 183: "Non"},
    5557: {16684: "Equipe1", 16685: "Nul", 16686: "Equipe2"},
    29: {
        196: "Equipe1 & Moins de",
        197: "Equipe1 & Plus de",
        198: "1X & Moins de",
        199: "1X & Plus de",
        206: "Equipe1 & Moins de - Non",
        207: "Equipe1 & Plus de - Non",
        208: "1X & Moins de - Non",
        209: "1X & Plus de - Non",
    },
    26: {
        191: "Equipe2 & Moins de",
        192: "Equipe2 & Plus de",
        193: "2X & Moins de",
        194: "2X & Plus de",
        211: "Equipe2 & Moins de - Non",
        212: "Equipe2 & Plus de - Non",
        213: "2X & Moins de - Non",
        214: "2X & Plus de - Non",
    },
    42: {478: "Oui", 479: "Non"},
    55: {975: "Oui", 976: "Non"},
    58: {504: "Oui", 505: "Non"},
    59: {506: "Oui", 507: "Non"},
    62: {516: "Oui", 517: "Non"},
    66: {518: "Oui", 519: "Non"},
    248: {1103: "Plus de", 1104: "Moins de"},
    249: {1105: "Oui", 1106: "Non"},
    346: {1519: "Equipe1", 1520: "Equipe2"},
    378: {1521: "Oui", 1522: "Non"},
    380: {1526: "Equipe1", 1527: "Equipe2"},
    2009: {6346: "Mené & gagne - Oui", 6347: "Mené & gagne - Non"},
    3271: {10330: "Handicap 1", 10331: "Handicap 2"},
}

def get_type_name(group_id, type_id):
    group_types = TYPE_MAPPING.get(group_id, {})
    return group_types.get(type_id)

# =====================================================
# Headers
# =====================================================

def generate_headers(host):
    timestamp = int(time.time() * 1000)
    random_part = random.randint(100000000, 999999999)
    request_guid = f"1_{APPGUID}_{timestamp}_13_257_{random_part}"
    
    return {
        "host": host,
        "accept": "application/vnd.xenvelop+json",
        "x-language": "fr_FR",
        "x-whence": "22",
        "x-referral": "1",
        "x-group": "1357",
        "x-bundleid": "org.xbet.client1",
        "appguid": APPGUID,
        "x-fcountry": "96",
        "content-type": "application/json; charset=utf-8",
        "user-agent": "org.xbet.client1-user-agent/1xbet-prod-v257.0.74",
        "version": "1xbet-prod-v257.0.74",
        "x-devicemanufacturer": "ITEL",
        "x-devicemodel": "Itel A671L",
        "x-request-guid": request_guid,
        "x-country": "96",
        "accept-encoding": "gzip"
    }

# =====================================================
# Dates & Filtres
# =====================================================

def get_date_range():
    now = datetime.now()
    d1 = now.replace(hour=8, minute=0, second=0, microsecond=0)
    d2 = now.replace(hour=23, minute=55, second=0, microsecond=0)
    
    # Si l'heure de début (08h) est déjà passée, on récupère le jour suivant
    if now >= d1:
        d1 += timedelta(days=1)
        d2 += timedelta(days=1)
    
    return int(d1.timestamp()), int(d2.timestamp())

def is_excluded_champ(name):
    return any(e.lower() in name.lower() for e in CHAMP_EXCLUSIONS)

def is_excluded_team(name):
    return any(e.lower() in name.lower() for e in TEAM_EXCLUSIONS)

# =====================================================
# Requêtes
# =====================================================

def get_matches(host=HOST):
    session = requests.Session()
    session.mount("https://", TLS13Adapter())
    d1, d2 = get_date_range()
    
    url = f"https://{host}/MainFeedLine/mobile/v3/ChampsBySport"
    headers = generate_headers(host)
    params = {
        "cfView": "3", "country": "96",
        "dateFrom": str(d1), "dateTo": str(d2),
        "fcountry": "96", "gr": "1357", "lng": "fr_FR",
        "ref": "1", "sportIds": "1", "whence": "22"
    }
    return session.get(url, headers=headers, params=params, timeout=30)


def get_matches_by_champ(champ_ids, host=HOST):
    """
    Récupère les matchs filtrés sur un ou plusieurs championnats précis (ex: Premier
    League = 88637), avec les infos match (lieu, météo, journée) déjà incluses.
    champ_ids : int, str, ou liste d'IDs (jointe par des virgules).
    """
    session = requests.Session()
    session.mount("https://", TLS13Adapter())
    d1, d2 = get_date_range()
    
    if isinstance(champ_ids, (list, tuple)):
        champ_ids_str = ",".join(str(c) for c in champ_ids)
    else:
        champ_ids_str = str(champ_ids)
    
    url = f"https://{host}/MainFeedLine/mobile/v3/gamesByChamp"
    headers = generate_headers(host)
    params = {
        "cfView": "3", "champIds": champ_ids_str, "country": "96",
        "dateFrom": str(d1), "dateTo": str(d2),
        "fcountry": "96", "gr": "1357", "lng": "fr_FR",
        "mode": "2", "ref": "1", "whence": "22"
    }
    return session.get(url, headers=headers, params=params, timeout=30)

def get_game_details(game_id, host=HOST):
    session = requests.Session()
    session.mount("https://", TLS13Adapter())
    
    url = f"https://{host}/MainFeedLine/mobile/v3/game"
    headers = generate_headers(host)
    params = {
        "cfView": "3", "country": "96", "fcountry": "96",
        "gameId": str(game_id), "gr": "1357", "lng": "fr_FR",
        "ref": "1", "supportedSpecialType": "1", "whence": "22"
    }
    return session.get(url, headers=headers, params=params, timeout=30)

def get_head_to_head(h2h_id, host=HOST):
    """Récupère le H2H via l'ID HACHÉ (statisticInfo.gameId)"""
    session = requests.Session()
    session.mount("https://", TLS13Adapter())
    
    url = f"https://{host}/statisticGame/v2/HeadToHead"
    headers = generate_headers(host)
    params = {
        "lng": "fr_FR", "id": str(h2h_id),
        "ref": "1", "fcountry": "96", "gr": "1357"
    }
    return session.get(url, headers=headers, params=params, timeout=30)


def get_game_stats(game_id, host=HOST):
    """Récupère les statistiques détaillées d'un match (confrontation directe ou match passé)"""
    session = requests.Session()
    session.mount("https://", TLS13Adapter())
    
    url = f"https://{host}/statisticGame/v2/Game"
    headers = generate_headers(host)
    params = {
        "id": str(game_id), "ref": "1",
        "fcountry": "96", "lng": "fr_FR"
    }
    return session.get(url, headers=headers, params=params, timeout=30)


def get_stage_data(match_id, host=HOST):
    """Récupère l'arbre de phase finale (coupe/élimination directe) — utilisé en repli si StageTTable échoue"""
    session = requests.Session()
    session.mount("https://", TLS13Adapter())
    
    url = f"https://{host}/statisticGame/v2/StageNet"
    headers = generate_headers(host)
    params = {
        "id": str(match_id), "ref": "1",
        "fcountry": "96", "lng": "fr_FR"
    }
    return session.get(url, headers=headers, params=params, timeout=30)


def get_table_data(match_id, host=HOST):
    """Récupère le classement du championnat (appelé en premier)"""
    session = requests.Session()
    session.mount("https://", TLS13Adapter())
    
    url = f"https://{host}/statisticGame/v2/StageTTable"
    headers = generate_headers(host)
    params = {
        "id": str(match_id), "lng": "fr_FR",
        "ref": "1", "fcountry": "96"
    }
    return session.get(url, headers=headers, params=params, timeout=30)

# =====================================================
# Extraction
# =====================================================

def extract_all_matches(data):
    results = []
    
    champs_list = data.get("data", [])
    if not champs_list:
        return results
    
    sport_data = champs_list[0]
    
    for champ in sport_data.get("mainLigas", []):
        champ_name = champ.get("name", "?")
        
        if is_excluded_champ(champ_name):
            continue
        
        champ_matches = []
        
        for game in champ.get("games", []):
            opp1 = game.get("opponent1", {}).get("fullName", "?")
            if is_excluded_team(opp1):
                continue
            champ_matches.append({
                "opp1": opp1,
                "opp2": game.get("opponent2", {}).get("fullName", "?"),
                "game_id": game.get("id"),
                "start_ts": game.get("startTs", 0)
            })
        
        for sub in champ.get("subLigas", []):
            sub_name = sub.get("name", champ_name)
            
            if is_excluded_champ(sub_name):
                continue
            
            for game in sub.get("games", []):
                opp1 = game.get("opponent1", {}).get("fullName", "?")
                if is_excluded_team(opp1):
                    continue
                champ_matches.append({
                    "opp1": opp1,
                    "opp2": game.get("opponent2", {}).get("fullName", "?"),
                    "game_id": game.get("id"),
                    "start_ts": game.get("startTs", 0)
                })
        
        if champ_matches:
            results.append({
                "champ": champ_name,
                "matches": champ_matches
            })
    
    return results


def extract_champ_matches(data):
    """
    Extrait les matchs d'une réponse gamesByChamp (déjà filtrée sur un/des championnat(s)
    précis côté serveur). Récupère aussi :
    - h2h_id et stage_id (statisticInfo), déjà connus donc pas besoin de les redécouvrir
      via l'endpoint cotes ensuite
    - les infos match (journée, lieu, météo) depuis matchInfoObj
    - les logos des 2 équipes (déjà présents ici, pas besoin d'attendre le H2H)
    Ne touche PAS aux cotes (eventGroups) : gérées ailleurs via get_game_details.
    """
    results = []
    
    for liga_block in data.get("data", []):
        liga = liga_block.get("liga", {})
        champ_name = liga.get("name", "?")
        champ_matches = []
        
        for game in liga_block.get("games", []):
            opp1_block = game.get("opponent1", {}) or {}
            opp2_block = game.get("opponent2", {}) or {}
            
            opp1_name = opp1_block.get("fullName", "?")
            if is_excluded_team(opp1_name):
                continue
            
            match_info = game.get("matchInfoObj", {}) or {}
            stat_info = game.get("statisticInfo", {}) or {}
            
            opp1_logo = None
            if opp1_block.get("opps"):
                opp1_logo = opp1_block["opps"][0].get("image")
            opp2_logo = None
            if opp2_block.get("opps"):
                opp2_logo = opp2_block["opps"][0].get("image")
            
            champ_matches.append({
                "opp1": opp1_name,
                "opp2": opp2_block.get("fullName", "?"),
                "opp1_logo": opp1_logo,
                "opp2_logo": opp2_logo,
                "game_id": game.get("id"),
                "start_ts": game.get("startTs", 0),
                "h2h_id": stat_info.get("gameId"),
                "stage_id": stat_info.get("stageId"),
                "tournament_stage": match_info.get("tournamentStage"),
                "location": match_info.get("location"),
                "location_country": match_info.get("locationCountry"),
                "stadium_id": match_info.get("stadiumId"),
                "weather": {
                    "temperature": match_info.get("temperature"),
                    "description": match_info.get("weatherDescription"),
                    "wind": match_info.get("weatherWindDescription"),
                    "pressure": match_info.get("weatherPressureDescription"),
                    "humidity": match_info.get("weatherHumidityDescription"),
                    "precipitation_chance": match_info.get("weatherPrecipitationChanceDescription"),
                } if match_info else None
            })
        
        if champ_matches:
            results.append({
                "champ": champ_name,
                "matches": champ_matches
            })
    
    return results

# =====================================================
# Extraction COTES
# =====================================================

def get_mapped_odds(game_data):
    match_data = game_data.get("data", {})
    if not match_data:
        return []
    
    result = []
    event_groups = match_data.get("eventGroups", [])
    
    for group in event_groups:
        group_id = group.get("groupId", 0)
        group_name = GROUP_MAPPING.get(group_id)
        if not group_name:
            continue
        
        mapped_odds = []
        for event_item in group.get("events", []):
            for option in event_item:
                if isinstance(option, dict):
                    type_id = option.get("type")
                    type_name = get_type_name(group_id, type_id)
                    if not type_name:
                        continue
                    
                    cf = option.get("cf")
                    if not cf:
                        continue
                    
                    param = option.get("parameter")
                    mapped_odds.append({
                        "type_id": type_id,
                        "type_name": type_name,
                        "cf": cf,
                        "parameter": param
                    })
        
        if mapped_odds:
            result.append({
                "group_id": group_id,
                "group_name": group_name,
                "odds": mapped_odds
            })
    
    return result

# =====================================================
# Extraction H2H
# =====================================================

def build_team_map(teams):
    """
    ID équipe -> vrai nom
    Convertit la liste 'teams' en dictionnaire pour une recherche rapide (O(1)).
    """
    return {
        str(team.get("id", "")).strip().lower(): team.get("title", "?")
        for team in teams
    }


def build_team_image_map(teams):
    """ID équipe -> logo (champ 'image' déjà présent dans la liste 'teams')"""
    return {
        str(team.get("id", "")).strip().lower(): team.get("image")
        for team in teams
    }


def build_logo_url(path):
    """
    Construit l'URL complète d'un logo à partir du chemin renvoyé par l'API.
    - Déjà une URL complète -> inchangé
    - Chemin relatif avec dossier (ex: 'sfiles/logo_teams/12763.png' ou
      '/sfiles/logo_teams/12763.png') -> préfixé par HOST (slash de tête retiré
      pour éviter un double slash)
    - Simple nom de fichier (ex: '12763.png') -> dossier 'sfiles/logo_teams/'
      (convention confirmée par la réponse gamesByChamp pour les logos d'équipe)
    """
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    path = path.lstrip("/")
    if "/" in path:
        return f"https://{HOST}/{path}"
    return f"https://{HOST}/sfiles/logo_teams/{path}"


def to_img_tag(path):
    """Formate un logo en balise <img> complète, ou None si absent"""
    url = build_logo_url(path)
    if not url:
        return None
    return f'<img src="{url}">'


def get_team_image(image_map, team_id):
    if not team_id:
        return None
    
    key = str(team_id).strip().lower()
    if key in TEAM_LOGO_CACHE:
        return TEAM_LOGO_CACHE[key]
    
    raw = image_map.get(key)
    img_tag = to_img_tag(raw)
    TEAM_LOGO_CACHE[key] = img_tag
    return img_tag


def get_league_logo(payload):
    """Logo du championnat (champ 'logo' présent dans StageNet/StageTTable)"""
    if not payload:
        return None
    data = payload.get("data", payload)
    raw = data.get("response", {}).get("logo")
    return to_img_tag(raw)


def build_game_entry(team_map, image_map, game, show_score=True):
    """Construit l'entrée complète d'un match : texte formaté + ID + logos des 2 équipes"""
    return {
        "id": game.get("id"),
        "text": format_game(team_map, game, show_score=show_score),
        "team1_logo": get_team_image(image_map, game.get("team1")),
        "team2_logo": get_team_image(image_map, game.get("team2")),
    }


def get_team_name(team_map, team_id):
    """Trouve le nom d'une équipe par son ID via le team_map"""
    if not team_id:
        return "?"
    team_id_clean = str(team_id).strip().lower()
    return team_map.get(team_id_clean, f"? (ID: {str(team_id)[:8]}...)")


def format_game(team_map, game, show_score=True):
    t1 = get_team_name(team_map, game.get("team1"))
    t2 = get_team_name(team_map, game.get("team2"))
    ts = game.get("dateStart", 0)
    try:
        d = datetime.fromtimestamp(ts).strftime("%d/%m/%Y")
    except:
        d = "?"
    
    game_id = game.get("id", "?")
    s1 = game.get("score1")
    s2 = game.get("score2")
    
    if show_score and s1 is not None and s2 is not None:
        return f"{t1} {s1}-{s2} {t2} ({d}) [ID: {game_id}]"
    
    # Match à venir : pas encore de score
    return f"{t1} vs {t2} ({d}) [ID: {game_id}]"


def parse_game_stats(stats_data):
    """
    Extrait du /statisticGame/v2/Game :
    - les stats du match complet (bloc gameStatistic dont title == "Match")
    - les stats de la 1ère mi-temps (1er bloc gameStatistic dont title == "Mi-temps")
    - les scores par période (1 Mi-temps, 2 Mi-temps, Résultat)
    """
    data = stats_data.get("data", stats_data)
    response = data.get("response", {})
    
    game_stats = response.get("gameStatistic", [])
    
    full_match = None
    first_half = None
    for block in game_stats:
        title = block.get("title", "")
        if title == "Match" and full_match is None:
            full_match = block.get("periodStatistic", [])
        elif title == "Mi-temps" and first_half is None:
            first_half = block.get("periodStatistic", [])
    
    scores = [
        {"title": p.get("title"), "score1": p.get("score1"), "score2": p.get("score2")}
        for p in response.get("period", [])
    ]
    
    return {
        "full_match": full_match or [],
        "first_half": first_half or [],
        "scores": scores
    }


def fetch_stats_for_games(games, pause_range=(0.3, 0.7)):
    """
    Pour une liste de matchs [{'id': ..., 'text': ...}], récupère les stats
    (match complet + 1ère mi-temps + scores) de chacun via get_game_stats.
    Modifie chaque dict en place en ajoutant la clé 'stats'.
    """
    for game in games:
        game_id = game.get("id")
        if not game_id or game_id == "?":
            game["stats"] = None
            continue
        try:
            resp = get_game_stats(game_id)
            game["stats"] = parse_game_stats(resp.json()) if resp.status_code == 200 else None
        except Exception:
            game["stats"] = None
        time.sleep(random.uniform(*pause_range))
    return games


def format_scores_line(stats):
    """Résumé compact 'MT1: x-y | MT2: x-y | Résultat: x-y' pour l'affichage console"""
    if not stats or not stats.get("scores"):
        return None
    return " | ".join(f"{s['title']}: {s['score1']}-{s['score2']}" for s in stats["scores"])


def get_league_name(match_id, cache_key=None, pause_range=(1, 5), max_retries=2, retry_delay=3):
    """
    Récupère le nom du championnat d'un match :
    1) essaie StageTTable (classement de championnat)
    2) si échec, essaie StageNet (arbre de phase finale / coupe)
    
    Chaque endpoint est retenté jusqu'à max_retries fois en cas de timeout/erreur
    réseau (pas en cas de réponse HTTP valide sans 'title' — inutile de réessayer
    une structure qui ne changera pas).
    
    cache_key : clé de cache à utiliser (ex: le nom de championnat déjà connu pour le
    match principal, afin de réutiliser le même appel pour tout autre match du jour de
    la même ligue). Si omis, on cache par match_id (utile pour les matchs passés dont
    on ne connaît pas encore le championnat).
    
    En cas d'échec total des deux endpoints : si cache_key est fourni (nom de
    championnat déjà connu via le feed gamesByChamp), on l'utilise comme repli au
    lieu de renvoyer None — mieux vaut un nom déjà fiable que rien du tout. Sans
    cache_key (matchs passés), on ne peut pas deviner le championnat : on renvoie None.
    
    Espace chaque requête réseau de 1 à 5 sec (pause_range).
    """
    if not match_id:
        print("      [get_league_name] ⚠️ match_id vide/None, abandon")
        return None, None
    
    lookup_key = cache_key or match_id
    if lookup_key in STAGE_CACHE:
        cached = STAGE_CACHE[lookup_key]
        print(f"      [get_league_name] 💾 CACHE HIT clé='{lookup_key}' -> title={cached['title']!r}")
        return cached["title"], cached["data"]
    
    print(f"      [get_league_name] CACHE MISS clé='{lookup_key}' | match_id='{match_id}'")
    
    def try_endpoint(fetch_func, label):
        """Tente un endpoint avec retries sur timeout/erreur réseau. Renvoie (title, payload) ou (None, None)."""
        for attempt in range(1, max_retries + 1):
            suffix = f" (tentative {attempt}/{max_retries})" if attempt > 1 else ""
            try:
                print(f"      [get_league_name] → GET {label}?id={match_id}{suffix}")
                resp = fetch_func(match_id)
                time.sleep(random.uniform(*pause_range))
                print(f"      [get_league_name]   {label} HTTP {resp.status_code}")
                
                if resp.status_code == 200:
                    payload = resp.json()
                    data = payload.get("data", payload)
                    response_block = data.get("response", {})
                    title = response_block.get("title")
                    
                    if title:
                        print(f"      [get_league_name]   ✅ title trouvé : {title!r}")
                        return title, payload
                    
                    print(f"      [get_league_name]   ⚠️ HTTP 200 mais pas de 'title'. "
                          f"Clés de 'data' : {list(data.keys())} | Clés de 'response' : {list(response_block.keys())}")
                    return None, None  # structure vide : pas la peine de réessayer
                
                body_preview = ""
                try:
                    body_preview = json.dumps(resp.json())[:300]
                except Exception:
                    body_preview = resp.text[:300] if hasattr(resp, "text") else "(pas de corps lisible)"
                print(f"      [get_league_name]   ❌ Corps de la réponse (300 premiers car.) : {body_preview}")
                return None, None  # erreur HTTP franche : pas la peine de réessayer non plus
            
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                print(f"      [get_league_name]   ⏱️ {type(e).__name__} sur {label}{suffix} : {e}")
                if attempt < max_retries:
                    print(f"      [get_league_name]   🔁 Nouvelle tentative dans {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                print(f"      [get_league_name]   ❌ {label} abandonné après {max_retries} tentatives")
            except Exception as e:
                print(f"      [get_league_name]   ❌ Exception {label} : {type(e).__name__}: {e}")
                return None, None
        return None, None
    
    league_name, payload_used = try_endpoint(get_table_data, "StageTTable")
    
    if not league_name:
        league_name, payload_used = try_endpoint(get_stage_data, "StageNet")
    
    if not league_name:
        if cache_key:
            print(f"      [get_league_name] ⚠️ ÉCHEC TOTAL — repli sur le nom déjà connu : '{cache_key}'")
            league_name = cache_key
        else:
            print(f"      [get_league_name] ❌ ÉCHEC TOTAL pour match_id='{match_id}' (pas de repli possible)")
    
    STAGE_CACHE[lookup_key] = {"title": league_name, "data": payload_used}
    return league_name, payload_used


def fetch_leagues_for_games(games):
    """
    Pour une liste de matchs [{'id': ..., 'text': ...}], récupère et attache le nom
    du championnat de chacun (clé 'league'). Chaque match passé a son propre ID, donc
    pas de cache_key partagé ici (le championnat n'est pas connu à l'avance).
    """
    for game in games:
        game_id = game.get("id")
        if not game_id or game_id == "?":
            game["league"] = None
            continue
        league_name, _ = get_league_name(game_id)
        game["league"] = league_name
    return games


def is_classification_payload(payload):
    """True si le payload vient de StageTTable (classement) plutôt que de StageNet (arbre coupe)"""
    if not payload:
        return False
    data = payload.get("data", payload)
    return bool(data.get("response", {}).get("table"))


def parse_classification_table(payload):
    """
    Extrait le classement d'une réponse StageTTable :
    liste de dicts {colonne_titre: valeur} (une entrée par équipe), dans l'ordre du classement.
    Les colonnes usuelles sont '#', 'Equipe', 'MJ', 'W', 'L', 'T', 'B', 'Pts', 'Formulaire'.
    Ajoute aussi 'Logo' (logo de l'équipe).
    """
    data = payload.get("data", payload)
    team_map = build_team_map(data.get("teams", []))
    image_map = build_team_image_map(data.get("teams", []))
    response = data.get("response", {})
    table_block = response.get("table", {}).get("table", {})
    
    titles = table_block.get("tableTitles", [])
    col_names = {}
    if titles:
        for col in titles[0].get("valueCol", []):
            col_names[col.get("id")] = col.get("title")
    
    rows = []
    for group in table_block.get("tableBody", []):
        for row in group:
            row_data = {}
            for col in row.get("valueCol", []):
                col_id = col.get("id")
                title = col_names.get(col_id, str(col_id))
                values = col.get("value", [])
                competitor_id = col.get("competitorId")
                
                if competitor_id and not values:
                    # Colonne "Equipe" : la valeur est le nom, pas un texte brut
                    row_data[title] = get_team_name(team_map, competitor_id)
                    row_data["Logo"] = get_team_image(image_map, competitor_id)
                else:
                    row_data[title] = values[0] if len(values) == 1 else values
            rows.append(row_data)
    
    return rows


def get_team_standing(table_rows, team_name):
    """Retrouve la ligne de classement d'une équipe par son nom"""
    for row in table_rows:
        if row.get("Equipe") == team_name:
            return row
    return None


def get_h2h_data(h2h_data):
    """
    La réponse de l'API HeadToHead est englobée dans une clé 'data' :
    { "data": { "teams": [...], "response": {...} } }
    """
    data = h2h_data.get("data", h2h_data)
    teams = data.get("teams", [])
    team_map = build_team_map(teams)
    image_map = build_team_image_map(teams)
    response = data.get("response", {})
    
    team1_id = response.get("team1")
    team2_id = response.get("team2")
    team1_name = get_team_name(team_map, team1_id)
    team2_name = get_team_name(team_map, team2_id)
    
    h2h = {
        "team1": team1_name,
        "team2": team2_name,
        "team1_logo": get_team_image(image_map, team1_id),
        "team2_logo": get_team_image(image_map, team2_id),
        "confrontations": [],
        "last_team1": [],
        "last_team2": [],
        "next_team1": None,
        "next_team2": None
    }
    
    # Confrontations directes entre les 2 équipes (6 plus récentes)
    games_sorted = sorted(response.get("games", []), key=lambda g: g.get("dateStart", 0), reverse=True)
    for game in games_sorted[:6]:
        h2h["confrontations"].append(build_game_entry(team_map, image_map, game))
    
    # Matchs passés individuels de chaque équipe (7 plus récents, tous adversaires confondus)
    team1_games_sorted = sorted(response.get("team1Games", []), key=lambda g: g.get("dateStart", 0), reverse=True)
    for game in team1_games_sorted[:7]:
        h2h["last_team1"].append(build_game_entry(team_map, image_map, game))
    
    team2_games_sorted = sorted(response.get("team2Games", []), key=lambda g: g.get("dateStart", 0), reverse=True)
    for game in team2_games_sorted[:7]:
        h2h["last_team2"].append(build_game_entry(team_map, image_map, game))
    
    # Prochain match de chaque équipe : le 2e (le 1er correspond en général au match
    # principal en cours d'analyse lui-même, donc pas informatif)
    future1 = response.get("team1FutureGames", [])
    if len(future1) > 1:
        h2h["next_team1"] = build_game_entry(team_map, image_map, future1[1], show_score=False)
    
    future2 = response.get("team2FutureGames", [])
    if len(future2) > 1:
        h2h["next_team2"] = build_game_entry(team_map, image_map, future2[1], show_score=False)
    
    return h2h

# =====================================================
# Affichage détaillé
# =====================================================

def print_first_match_full(match, champ_name):
    game_id = match["game_id"]
    
    try:
        heure = datetime.fromtimestamp(match["start_ts"]).strftime("%H:%M")
    except:
        heure = "?"
    
    print("\n" + "=" * 70)
    print(f"🏆 {champ_name}")
    print(f"⚽ {match['opp1']} vs {match['opp2']}")
    print(f"⏰ {heure} | 🆔 Game ID : {game_id}")
    if match.get("tournament_stage"):
        print(f"📅 Journée : {match['tournament_stage']}")
    if match.get("location"):
        pays = f" ({match['location_country']})" if match.get("location_country") else ""
        print(f"📍 Lieu : {match['location']}{pays}")
    if match.get("weather") and match["weather"].get("description"):
        w = match["weather"]
        print(f"🌤️ Météo : {w.get('description')} | {w.get('temperature', '?')} | "
              f"Vent {w.get('wind', '?')} | Humidité {w.get('humidity', '?')}%")
    print("=" * 70)
    
    # h2h_id et stage_id sont déjà connus via gamesByChamp (statisticInfo) — pas besoin
    # de les redécouvrir depuis la réponse cotes. On les garde en repli si absents ici
    # (ex: si le match provient encore de l'ancien flux ChampsBySport).
    h2h_id = match.get("h2h_id")
    stage_id = match.get("stage_id")
    
    # === COTES MAPPÉES ===
    print(f"\n💰 COTES MAPPÉES")
    print("-" * 70)
    
    mapped_odds = []
    
    odds_resp = get_game_details(game_id)
    if odds_resp.status_code == 200:
        odds_data = odds_resp.json()
        
        if not h2h_id:
            # Repli : extraction depuis la réponse cotes (comportement historique)
            match_data = odds_data.get("data", {})
            statistic_info = match_data.get("statisticInfo", {})
            h2h_id = statistic_info.get("gameId")
        
        if h2h_id:
            print(f"   🔑 ID haché (H2H) : {h2h_id}")
        
        mapped_odds = get_mapped_odds(odds_data)
        
        if mapped_odds:
            for group in mapped_odds:
                print(f"\n   📊 {group['group_name']} (Groupe {group['group_id']})")
                for o in group["odds"]:
                    param_str = f" ({o['parameter']})" if o['parameter'] is not None else ""
                    print(f"      • {o['type_name']}{param_str} : {o['cf']:.3f}")
        else:
            print("   Aucune cote mappée disponible")
    else:
        print(f"   ❌ Erreur HTTP: {odds_resp.status_code}")
    
    # === CLASSEMENT / STAGE DU CHAMPIONNAT (mis en cache par nom de championnat) ===
    # Utilise stage_id (statisticInfo.stageId), PAS h2h_id (statisticInfo.gameId) :
    # stageId identifie le championnat/la saison (identique pour tous les matchs de
    # la même compétition), alors que gameId identifie une paire de confrontation H2H
    # précise. C'est stageId qu'attendent StageNet/StageTTable.
    league_title, league_logo, classification_full = None, None, []
    
    stage_lookup_id = stage_id or h2h_id  # repli sur h2h_id si stage_id indisponible
    
    if stage_lookup_id:
        was_cached = champ_name in STAGE_CACHE
        league_title, stage_payload = get_league_name(stage_lookup_id, cache_key=champ_name)
        
        if stage_payload:
            source = "cache (déjà récupéré pour cette ligue aujourd'hui)" if was_cached else "requête serveur"
            league_logo = get_league_logo(stage_payload)
            print(f"\n📋 Classement/Stage du championnat : {league_title} ({source})")
            
            if league_title and league_title != champ_name:
                print(f"   ℹ️ Nom du championnat corrigé : '{champ_name}' → '{league_title}'")
                champ_name = league_title
            
            if is_classification_payload(stage_payload):
                classification_full = parse_classification_table(stage_payload)
                row1 = get_team_standing(classification_full, match["opp1"])
                row2 = get_team_standing(classification_full, match["opp2"])
                for opp, row in [(match["opp1"], row1), (match["opp2"], row2)]:
                    if row:
                        print(f"   • {opp} : {row.get('#', '?')}e place | "
                              f"{row.get('MJ', '?')} MJ | {row.get('W', '?')}V {row.get('T', '?')}N {row.get('L', '?')}D | "
                              f"Buts {row.get('B', '?')} | {row.get('Pts', '?')} pts")
                    else:
                        print(f"   • {opp} : non trouvée dans ce classement")
                print(f"   ({len(classification_full)} équipes au total — classement complet sauvegardé dans le fichier)")
            else:
                print(f"   (Arbre de phase finale récupéré — pas de classement disponible pour ce format)")
        elif league_title:
            # Échec total de StageTTable/StageNet mais repli sur le nom déjà connu
            # (cache_key = champ_name du feed gamesByChamp) : pas de classement disponible,
            # mais on garde au moins le bon nom de championnat.
            print(f"\n📋 Classement/Stage du championnat : introuvable (StageNet et StageTTable ont échoué) "
                  f"— nom conservé : '{league_title}'")
        else:
            print(f"\n📋 Classement/Stage du championnat : introuvable (StageNet et StageTTable ont échoué)")
    
    # === HEAD TO HEAD ===
    print(f"\n📊 HEAD TO HEAD")
    print("-" * 70)
    
    if not h2h_id:
        print("   ❌ Impossible de récupérer l'ID haché")
        return
    
    h2h_resp = get_head_to_head(h2h_id)
    if h2h_resp.status_code != 200:
        print(f"   ❌ Erreur HTTP: {h2h_resp.status_code}")
        return
    
    h2h_data = h2h_resp.json()
    print(f"   🔑 ID haché (H2H) : {h2h_id}")
    
    h2h = get_h2h_data(h2h_data)
    
    print(f"\n   ⏳ Récupération des stats détaillées ({len(h2h['confrontations']) + len(h2h['last_team1']) + len(h2h['last_team2'])} matchs)...")
    fetch_stats_for_games(h2h["confrontations"])
    fetch_stats_for_games(h2h["last_team1"])
    fetch_stats_for_games(h2h["last_team2"])
    
    print(f"   ⏳ Récupération des championnats de chaque match (StageTTable, repli StageNet)...")
    fetch_leagues_for_games(h2h["confrontations"])
    fetch_leagues_for_games(h2h["last_team1"])
    fetch_leagues_for_games(h2h["last_team2"])
    
    if h2h["confrontations"]:
        print(f"\n   🔥 Confrontations directes :")
        for c in h2h["confrontations"]:
            print(f"      • {c['text']}")
            if c.get("league"):
                print(f"         🏆 {c['league']}")
            score_line = format_scores_line(c.get("stats"))
            if score_line:
                print(f"         📊 {score_line}")
    else:
        print(f"\n   🔥 Aucune confrontation directe")
    
    if h2h["last_team1"]:
        print(f"\n   🏃 Matchs passés de {h2h['team1']} :")
        for c in h2h["last_team1"]:
            print(f"      • {c['text']}")
            if c.get("league"):
                print(f"         🏆 {c['league']}")
            score_line = format_scores_line(c.get("stats"))
            if score_line:
                print(f"         📊 {score_line}")
    
    if h2h["last_team2"]:
        print(f"\n   🏃 Matchs passés de {h2h['team2']} :")
        for c in h2h["last_team2"]:
            print(f"      • {c['text']}")
            if c.get("league"):
                print(f"         🏆 {c['league']}")
            score_line = format_scores_line(c.get("stats"))
            if score_line:
                print(f"         📊 {score_line}")
    
    if h2h["next_team1"]:
        print(f"\n   📅 2e prochain match de {h2h['team1']} : {h2h['next_team1']['text']}")
    
    if h2h["next_team2"]:
        print(f"\n   📅 2e prochain match de {h2h['team2']} : {h2h['next_team2']['text']}")
    
    # === RAPPORT COMPLET DU MATCH (retourné à l'appelant, pas sauvegardé ici) ===
    match_report = {
        "champ_name": champ_name,
        "league_logo": league_logo,
        "match": {
            "game_id": game_id,
            "h2h_id": h2h_id,
            "stage_id": stage_id,
            "start_ts": match.get("start_ts"),
            "tournament_stage": match.get("tournament_stage"),
            "location": match.get("location"),
            "location_country": match.get("location_country"),
            "weather": match.get("weather"),
            "team1": {"name": match["opp1"], "logo": h2h.get("team1_logo") or to_img_tag(match.get("opp1_logo"))},
            "team2": {"name": match["opp2"], "logo": h2h.get("team2_logo") or to_img_tag(match.get("opp2_logo"))},
        },
        "odds": mapped_odds,
        "classification": classification_full,
        "h2h": {
            "h2h_id": h2h_id,
            "team1": h2h["team1"],
            "team2": h2h["team2"],
            "team1_logo": h2h["team1_logo"],
            "team2_logo": h2h["team2_logo"],
            "confrontations": h2h["confrontations"],
            "last_team1": h2h["last_team1"],
            "last_team2": h2h["last_team2"],
            "next_team1": h2h["next_team1"],
            "next_team2": h2h["next_team2"],
        }
    }
    
    return match_report

# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    print("=" * 60)
    print("1xBET - Analyse complète (1er match du 1er championnat)")
    print("=" * 60)
    
    try:
        print(f"\n📡 Récupération des matchs (championnats : {CHAMP_IDS})...")
        resp = get_matches_by_champ(CHAMP_IDS)
        
        if resp.status_code != 200:
            print(f"❌ Erreur HTTP: {resp.status_code}")
            exit(1)
        
        data = resp.json()
        champ_results = extract_champ_matches(data)
        
        if not champ_results:
            print("❌ Aucun championnat trouvé")
            exit(1)
        
        total_matches = sum(len(c["matches"]) for c in champ_results)
        print(f"\n📊 {len(champ_results)} championnats | {total_matches} matchs au total")
        
        print("\n" + "=" * 70)
        print("📋 RÉSUMÉ DES CHAMPIONNATS")
        print("=" * 70)
        
        for champ in champ_results:
            print(f"\n🏆 {champ['champ']} ({len(champ['matches'])} matchs)")
            for m in champ["matches"]:
                try:
                    h = datetime.fromtimestamp(m["start_ts"]).strftime("%H:%M")
                except:
                    h = "?"
                print(f"   • {m['opp1']} vs {m['opp2']} ({h})")
        
        print("\n\n" + "=" * 70)
        print(f"🎯 TRAITEMENT COMPLET DE {total_matches} MATCH(S)")
        print("=" * 70)
        
        output_filename = "games_of_day.json"
        all_reports = []
        match_num = 0
        
        for champ in champ_results:
            for match in champ["matches"]:
                match_num += 1
                print(f"\n\n{'#' * 70}")
                print(f"# MATCH {match_num}/{total_matches} — {match['opp1']} vs {match['opp2']}")
                print(f"{'#' * 70}")
                
                try:
                    report = print_first_match_full(match, champ["champ"])
                    if report:
                        all_reports.append(report)
                    else:
                        print(f"   ⚠️ Match {match_num} ignoré (échec cotes/H2H)")
                except Exception as e:
                    print(f"   ❌ Erreur sur le match {match_num} : {e}")
                
                # Sauvegarde incrémentale après CHAQUE match : rien n'est perdu
                # si le script est interrompu en cours de route.
                with open(output_filename, "w", encoding="utf-8") as f:
                    json.dump({
                        "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "matchs_traites": len(all_reports),
                        "matchs_total": total_matches,
                        "games": all_reports
                    }, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*70}")
        print(f"✅ Analyse terminée : {len(all_reports)}/{total_matches} matchs traités avec succès")
        print(f"💾 Sauvegardé dans {output_filename}")
        print(f"{'='*70}")
        
    except KeyboardInterrupt:
        print("\n⏹️ Interrompu")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()