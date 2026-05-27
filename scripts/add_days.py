import json
import copy
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────────
# 1. CHARGEMENT DES FICHIERS
# ─────────────────────────────────────────────

with open("data/football/leagues/England_Premier_League.json", "r", encoding="utf-8") as f:
    matches_data = json.load(f)

with open("data/football/standings/Standings.json", "r", encoding="utf-8") as f:
    standings_raw = json.load(f)

# ─────────────────────────────────────────────
# 2. EXTRACTION DES INFOS STANDINGS
# ─────────────────────────────────────────────

LEAGUE_KEY = "England_Premier_League"
league_info = standings_raw[LEAGUE_KEY]

TOTAL_JOURNEES = league_info["total_journees"]

gp_per_team = {
    entry["name"]: entry["stats"]["GP"]
    for entry in league_info["standings"]
}

CURRENT_JOURNEE = max(gp_per_team.values())

print(f"[INFO] Total journées saison : {TOTAL_JOURNEES}")
print(f"[INFO] Journée courante (max GP) : {CURRENT_JOURNEE}")

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
    print(f"[WARN] Format de date non reconnu : '{date_str}'")
    return None

# ─────────────────────────────────────────────
# 4. TRI DES MATCHS DU PLUS RÉCENT AU PLUS ANCIEN
# ─────────────────────────────────────────────

def sort_key(match: dict):
    d = parse_date(match.get("date", ""))
    return d if d else datetime.min

matches_sorted = sorted(matches_data, key=sort_key, reverse=True)

# ─────────────────────────────────────────────
# 5. REGROUPEMENT DES MATCHS PAR ÉQUIPE
# ─────────────────────────────────────────────

team_matches_order: dict[str, list[dict]] = defaultdict(list)

for match in matches_sorted:
    t1 = match.get("team1")
    t2 = match.get("team2")
    if t1:
        team_matches_order[t1].append(match)
    if t2:
        team_matches_order[t2].append(match)

# ─────────────────────────────────────────────
# 6. ATTRIBUTION DES JOURNÉES PAR ÉQUIPE
# ─────────────────────────────────────────────

match_journee: dict[str, dict] = {}

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

# ─────────────────────────────────────────────
# 7. CONSOLIDATION : une journée unique par match
# ─────────────────────────────────────────────

def consolidate_journee(game_id: str, match: dict) -> dict:
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

# ─────────────────────────────────────────────
# 8. LABEL DE SAISON DYNAMIQUE
# ─────────────────────────────────────────────

def get_saison_label(saison_offset: int) -> str:
    current_year = datetime.now().year
    start = current_year - saison_offset - 1
    end   = current_year - saison_offset
    return f"{start}/{end}"

# ─────────────────────────────────────────────
# 9. ENRICHISSEMENT AVEC DEEPCOPY
# ─────────────────────────────────────────────

enriched_matches = []

for match in matches_data:
    m = copy.deepcopy(match)  # ✅ copie totale, stats et odds 100% préservés
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

# ─────────────────────────────────────────────
# 10. VÉRIFICATION INTÉGRITÉ DES STATS
# ─────────────────────────────────────────────

print("\n── Vérification intégrité (5 premiers matchs) ──")
for original, enriched in zip(matches_data[:5], enriched_matches[:5]):
    stats_ok  = original.get("stats")  == enriched.get("stats")
    odds_ok   = original.get("odds")   == enriched.get("odds")
    score_ok  = original.get("score")  == enriched.get("score")
    print(
        f"  [{enriched.get('date')}] {enriched.get('team1')} vs {enriched.get('team2')}"
        f" | stats={'✅' if stats_ok else '❌'}"
        f" | odds={'✅' if odds_ok else '❌'}"
        f" | score={'✅' if score_ok else '❌'}"
        f" → J{enriched.get('journee')} {enriched.get('saison')}"
    )

# ─────────────────────────────────────────────
# 11. SAUVEGARDE
# ─────────────────────────────────────────────

output_path = "data/football/leagues/England_Premier_League.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(enriched_matches, f, ensure_ascii=False, indent=2)

print(f"\n[OK] {len(enriched_matches)} matchs enrichis → {output_path}")