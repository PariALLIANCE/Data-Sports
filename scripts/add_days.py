import json
import copy
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────────
# 1. LIGUES CIBLES (sans England_Premier_League)
# ─────────────────────────────────────────────

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
    "USA_Major_League_Soccer": {"id": "usa.1", "json": "USA_Major_League_Soccer.json"},
    "Venezuela_Primera_Division": {"id": "ven.1", "json": "Venezuela_Primera_Division.json"},
}

LEAGUES_DIR  = "data/football/leagues/"
STANDINGS_PATH = "data/football/standings/Standings.json"

# ─────────────────────────────────────────────
# 2. CHARGEMENT STANDINGS
# ─────────────────────────────────────────────

with open(STANDINGS_PATH, "r", encoding="utf-8") as f:
    standings_raw = json.load(f)

# ─────────────────────────────────────────────
# 3. PARSING DES DATES
# ─────────────────────────────────────────────

DATE_FORMATS = [
    "%A, %B %d, %Y",
    "%A, %d %B %Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
]

def parse_date(date_str: str) -> datetime | None:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    print(f"  [WARN] Format de date non reconnu : '{date_str}'")
    return None

# ─────────────────────────────────────────────
# 4. LABEL DE SAISON DYNAMIQUE
# ─────────────────────────────────────────────

def get_saison_label(saison_offset: int) -> str:
    current_year = datetime.now().year
    start = current_year - saison_offset - 1
    end   = current_year - saison_offset
    return f"{start}/{end}"

# ─────────────────────────────────────────────
# 5. TRAITEMENT D'UNE LIGUE
# ─────────────────────────────────────────────

def process_league(league_key: str, league_info: dict) -> None:
    json_file = league_info["json"]
    json_path = LEAGUES_DIR + json_file

    # 5.1 Vérification standings disponibles
    if league_key not in standings_raw:
        print(f"  [SKIP] Standings introuvables pour {league_key}")
        return

    standing = standings_raw[league_key]
    TOTAL_JOURNEES = standing["total_journees"]

    gp_per_team = {
        entry["name"]: entry["stats"]["GP"]
        for entry in standing["standings"]
    }

    CURRENT_JOURNEE = max(gp_per_team.values())

    print(f"  Total journées : {TOTAL_JOURNEES} | Journée courante : {CURRENT_JOURNEE}")

    # 5.2 Chargement des matchs
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            matches_data = json.load(f)
    except FileNotFoundError:
        print(f"  [SKIP] Fichier introuvable : {json_path}")
        return

    # 5.3 Tri du plus récent au plus ancien
    def sort_key(match):
        d = parse_date(match.get("date", ""))
        return d if d else datetime.min

    matches_sorted = sorted(matches_data, key=sort_key, reverse=True)

    # 5.4 Regroupement par équipe
    team_matches_order = defaultdict(list)
    for match in matches_sorted:
        t1 = match.get("team1")
        t2 = match.get("team2")
        if t1:
            team_matches_order[t1].append(match)
        if t2:
            team_matches_order[t2].append(match)

    # 5.5 Attribution des journées par équipe
    match_journee = {}

    for team, team_matches in team_matches_order.items():
        journee = gp_per_team.get(team, CURRENT_JOURNEE)
        saison_offset = 0

        for match in team_matches:
            game_id = match.get("gameId")
            if not game_id:
                journee -= 1
                if journee < 1:
                    saison_offset += 1
                    journee = TOTAL_JOURNEES
                continue

            if game_id not in match_journee:
                match_journee[game_id] = {}

            match_journee[game_id][f"journee_team_{team}"] = {
                "journee": journee,
                "saison_offset": saison_offset
            }

            journee -= 1
            if journee < 1:
                saison_offset += 1
                journee = TOTAL_JOURNEES

    # 5.6 Consolidation : une journée unique par match
    def consolidate_journee(game_id, match):
        data = match_journee.get(game_id, {})
        t1 = match.get("team1")
        t2 = match.get("team2")

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

    # 5.7 Enrichissement avec deepcopy
    enriched_matches = []

    for match in matches_data:
        m = copy.deepcopy(match)
        game_id = m.get("gameId")

        if game_id:
            result = consolidate_journee(game_id, m)
            journee = result["journee"]
            saison_offset = result["saison_offset"]

            m["journee"] = journee
            m["saison_offset"] = saison_offset
            m["saison"] = get_saison_label(saison_offset) if saison_offset is not None else None
            m["saison_terminee"] = (CURRENT_JOURNEE >= TOTAL_JOURNEES)
        else:
            m["journee"] = None
            m["saison_offset"] = None
            m["saison"] = None
            m["saison_terminee"] = None

        enriched_matches.append(m)

    # 5.8 Sauvegarde
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(enriched_matches, f, ensure_ascii=False, indent=2)

    print(f"  [OK] {len(enriched_matches)} matchs enrichis → {json_path}")

# ─────────────────────────────────────────────
# 6. BOUCLE PRINCIPALE
# ─────────────────────────────────────────────

print("=" * 55)
print("  ADD JOURNÉE — TOUTES LIGUES")
print("=" * 55)

success = 0
skipped = 0

for league_key, league_info in LEAGUES.items():
    print(f"\n▶ {league_key}")
    try:
        process_league(league_key, league_info)
        success += 1
    except Exception as e:
        print(f"  [ERROR] {e}")
        skipped += 1

print("\n" + "=" * 55)
print(f"  Terminé : {success} ligues traitées, {skipped} erreurs")
print("=" * 55)