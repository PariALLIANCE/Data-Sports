import json
import os
import glob
import subprocess
from datetime import datetime
from collections import defaultdict

# ================= CONFIG =================
LEAGUES_DIR    = "data/football/leagues"
STANDINGS_FILE = "data/football/standings/Standings.json"
OUTPUT_FILE    = "dataset_ml.json"
TMP_DIR        = "data/football/dataset_tmp"
MIN_ENTRIES    = 30
PUSH_ENABLED   = os.environ.get("GIT_PUSH", "false").lower() == "true"

# ================= UTILITAIRES =================

def parse_date(date_str):
    for fmt in ("%A, %B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    return None

def parse_score(score_str):
    try:
        parts = score_str.strip().split("-")
        return int(parts[0].strip()), int(parts[1].strip())
    except:
        return None, None

def parse_pct(val):
    try:
        return float(str(val).replace("%", "").strip())
    except:
        return 0.0

def get_team_position(team_name, standings):
    for league_key, teams in standings.items():
        for t in teams:
            if t["name"] == team_name:
                return t["position"], league_key
    return None, None

def result_for_team(score_home, score_away, side):
    if score_home is None:
        return "?"
    if score_home == score_away:
        return "N"
    if side == "home":
        return "V" if score_home > score_away else "D"
    else:
        return "V" if score_away > score_home else "D"

def safe_avg(values):
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 2)

def is_valid_match(m):
    if "odds" not in m:
        return False
    odds = m["odds"]
    if not odds.get("home") or not odds.get("away") or not odds.get("draw"):
        return False
    stats = m.get("stats")
    if not stats or not isinstance(stats, dict) or len(stats) == 0:
        return False
    score_h, score_a = parse_score(m.get("score", ""))
    if score_h is None:
        return False
    if parse_date(m.get("date", "")) is None:
        return False
    return True

def git_push(path, message):
    subprocess.run(["git", "add", path], check=True)
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if result.returncode != 0:
        subprocess.run(["git", "commit", "-m", message], check=True)
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print(f"📤 {message}")

# ================= CHARGEMENT STANDINGS =================
print(f"📂 Chargement des classements : {STANDINGS_FILE}")
with open(STANDINGS_FILE, "r", encoding="utf-8") as f:
    standings = json.load(f)

# ================= CHARGEMENT MATCHS =================
print(f"📂 Chargement des matchs depuis : {LEAGUES_DIR}")
json_files = sorted(glob.glob(os.path.join(LEAGUES_DIR, "*.json")))

if not json_files:
    print("❌ Aucun fichier JSON trouvé")
    exit(1)

all_matches = []

for jf in json_files:
    league_name = os.path.splitext(os.path.basename(jf))[0]
    with open(jf, "r", encoding="utf-8") as f:
        raw = json.load(f)

    for m in raw:
        if not is_valid_match(m):
            continue

        mc = dict(m)
        sh, sa = parse_score(mc.get("score", ""))
        mc["_date_obj"]   = parse_date(mc.get("date", ""))
        mc["_score_home"] = sh
        mc["_score_away"] = sa
        mc["_league"]     = league_name
        all_matches.append(mc)

all_matches.sort(key=lambda m: m["_date_obj"])
print(f"   {len(all_matches)} matchs valides chargés\n")

# ================= INDEX PAR ÉQUIPE =================
team_history = defaultdict(list)
for m in all_matches:
    team_history[m.get("team1", "").strip()].append(m)
    team_history[m.get("team2", "").strip()].append(m)

# ================= HELPERS =================

def get_last_n(team_name, before_dt, game_id, n=6):
    history = team_history.get(team_name, [])
    prev = [
        m for m in history
        if m["_date_obj"] < before_dt or
           (m["_date_obj"] == before_dt and m.get("gameId") != game_id)
    ]
    prev.sort(key=lambda m: m["_date_obj"], reverse=True)
    return prev[:n]

def calc_means(history, team):
    poss, shots, bm, be = [], [], [], []
    for m in history:
        s = m.get("stats", {})
        is_h = m.get("team1", "").strip() == team
        side = "home" if is_h else "away"

        poss.append(parse_pct(s.get("Possession", {}).get(side, 0)))
        shots.append(float(s.get("Shots on Goal", {}).get(side, 0) or 0))
        bm.append(m["_score_home"] if is_h else m["_score_away"])
        be.append(m["_score_away"] if is_h else m["_score_home"])

    return {
        "moy_possession": safe_avg(poss),
        "moy_shots_ontarget": safe_avg(shots),
        "moy_buts_marques": safe_avg(bm),
        "moy_buts_encaisses": safe_avg(be),
    }

def build_form(history, team):
    form = []
    for m in history:
        is_h = m.get("team1", "").strip() == team
        sh, sa = m["_score_home"], m["_score_away"]
        res = result_for_team(sh, sa, "home" if is_h else "away")
        o = m["odds"]
        form.append(f"{res}:{o['home']},{o['draw']},{o['away']}")
    return form

def build_scores(history):
    return " | ".join(m.get("score", "?") for m in history)

# ================= CONSTRUCTION =================

print("🔨 Construction du dataset...")
os.makedirs(TMP_DIR, exist_ok=True)

processed_ids = set()
dataset = []

for jf in json_files:
    league_name = os.path.splitext(os.path.basename(jf))[0]

    with open(jf, "r", encoding="utf-8") as f:
        matches = json.load(f)

    count = 0

    for match in matches:
        if not is_valid_match(match):
            continue

        game_id = match.get("gameId")
        if not game_id or game_id in processed_ids:
            continue

        dt = parse_date(match.get("date", ""))
        sh, sa = parse_score(match.get("score", ""))

        hist_home = get_last_n(match["team1"], dt, game_id)
        hist_away = get_last_n(match["team2"], dt, game_id)

        if len(hist_home) < 6 or len(hist_away) < 6:
            continue

        mh = calc_means(hist_home, match["team1"])
        ma = calc_means(hist_away, match["team2"])

        entry = {
            "gameId": game_id,
            "date": match["date"],
            "league": league_name,
            "team1": match["team1"],
            "team2": match["team2"],

            "Moy_6derniersmatchs": {
                "moy_possession_home": mh["moy_possession"],
                "moy_possession_away": ma["moy_possession"],
                "moy_shots_ontarget_home": mh["moy_shots_ontarget"],
                "moy_shots_ontarget_away": ma["moy_shots_ontarget"],
                "moy_buts_marques_home": mh["moy_buts_marques"],
                "moy_buts_marques_away": ma["moy_buts_marques"],
                "moy_buts_encaisses_home": mh["moy_buts_encaisses"],
                "moy_buts_encaisses_away": ma["moy_buts_encaisses"],
            },

            "scores_finaux_recents_home": build_scores(hist_home),
            "scores_finaux_recents_away": build_scores(hist_away),

            "targets": {
                "target_score_home": sh,
                "target_score_away": sa,
            }
        }

        dataset.append(entry)
        processed_ids.add(game_id)
        count += 1

    print(f"✅ {league_name} : {count}")

# ================= ÉCRITURE SÉCURISÉE =================

tmp_final = OUTPUT_FILE + ".tmp"

print(f"📊 Total : {len(dataset)} entrées")

with open(tmp_final, "w", encoding="utf-8") as f:
    f.write("[\n")

    for i, item in enumerate(dataset):
        json.dump(item, f, ensure_ascii=False)

        if i < len(dataset) - 1:
            f.write(",\n")

        if i % 1000 == 0:
            f.flush()
            os.fsync(f.fileno())

    f.write("\n]")

os.replace(tmp_final, OUTPUT_FILE)

print("💾 Dataset écrit sans troncature")

# ================= PUSH =================

if PUSH_ENABLED:
    git_push(OUTPUT_FILE, f"dataset {len(dataset)}")