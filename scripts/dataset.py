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
            if t["name"].strip() == team_name:
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

# ================= CHARGEMENT =================

print(f"📂 Chargement standings")
with open(STANDINGS_FILE, "r", encoding="utf-8") as f:
    standings = json.load(f)

json_files = sorted(glob.glob(os.path.join(LEAGUES_DIR, "*.json")))
if not json_files:
    print("❌ Aucun fichier")
    exit(1)

# ================= INDEX GLOBAL =================

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

team_history = defaultdict(list)
for m in all_matches:
    team_history[m.get("team1", "").strip()].append(m)
    team_history[m.get("team2", "").strip()].append(m)

# ================= HELPERS =================

def get_last_n(team_name, before_dt, game_id, n=6):
    hist = team_history.get(team_name, [])
    prev = [m for m in hist if m["_date_obj"] < before_dt or m.get("gameId") != game_id]
    prev.sort(key=lambda m: m["_date_obj"], reverse=True)
    return prev[:n]

def calc_means(history, team):
    poss, shots, bm, be = [], [], [], []

    for m in history:
        s = m.get("stats", {})
        is_h = m.get("team1").strip() == team
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
    out = []
    for m in history:
        is_h = m.get("team1").strip() == team
        sh, sa = m["_score_home"], m["_score_away"]
        res = result_for_team(sh, sa, "home" if is_h else "away")
        o = m["odds"]
        out.append(f"{res}:{o['home']},{o['draw']},{o['away']}")
    return out

def build_pos_adv(history, team):
    vaincu, invaincu = [], []

    for m in history:
        is_h = m.get("team1").strip() == team
        sh, sa = m["_score_home"], m["_score_away"]

        res = result_for_team(sh, sa, "home" if is_h else "away")

        adv = m.get("team2" if is_h else "team1").strip()
        pos, _ = get_team_position(adv, standings)

        if pos is None:
            continue  # ✅ FIX

        pos = str(pos)

        if res == "V":
            vaincu.append(pos)

        if res in ("V", "N"):
            invaincu.append(pos)

    return vaincu, invaincu

def build_scores(history):
    return " | ".join(m.get("score", "?") for m in history)

# ================= BUILD =================

os.makedirs(TMP_DIR, exist_ok=True)

dataset = []
processed = set()

for jf in json_files:
    league = os.path.splitext(os.path.basename(jf))[0]

    with open(jf, "r", encoding="utf-8") as f:
        matches = json.load(f)

    entries = []

    for m in matches:
        if not is_valid_match(m):
            continue

        game_id = m.get("gameId")
        if game_id in processed:
            continue

        sh, sa = parse_score(m["score"])
        dt = parse_date(m["date"])

        t1 = m["team1"].strip()
        t2 = m["team2"].strip()

        h1 = get_last_n(t1, dt, game_id)
        h2 = get_last_n(t2, dt, game_id)

        if len(h1) < 6 or len(h2) < 6:
            continue

        h1 = sorted(h1, key=lambda x: x["_date_obj"])
        h2 = sorted(h2, key=lambda x: x["_date_obj"])

        m1 = calc_means(h1, t1)
        m2 = calc_means(h2, t2)

        v1, i1 = build_pos_adv(h1, t1)
        v2, i2 = build_pos_adv(h2, t2)

        entry = {
            "gameId": game_id,
            "date": m["date"],
            "league": league,
            "team1": t1,
            "team2": t2,

            "Moy_6derniersmatchs": {
                "moy_possession_home": m1["moy_possession"],
                "moy_possession_away": m2["moy_possession"],
                "moy_shots_ontarget_home": m1["moy_shots_ontarget"],
                "moy_shots_ontarget_away": m2["moy_shots_ontarget"],
                "moy_buts_marques_home": m1["moy_buts_marques"],
                "moy_buts_marques_away": m2["moy_buts_marques"],
                "moy_buts_encaisses_home": m1["moy_buts_encaisses"],
                "moy_buts_encaisses_away": m2["moy_buts_encaisses"],
            },

            "Form_recents_with_odds_home": build_form(h1, t1),
            "Form_recents_with_odds_away": build_form(h2, t2),

            "pos_adv_vaincu_home": v1,
            "pos_adv_vaincu_away": v2,
            "pos_adv_invaincu_home": i1,
            "pos_adv_invaincu_away": i2,

            "scores_finaux_recents_home": build_scores(h1),
            "scores_finaux_recents_away": build_scores(h2),

            "cotes_match": m["odds"],

            "targets": {
                "target_1X2": "1" if sh > sa else ("X" if sh == sa else "2"),
                "target_score_home": sh,
                "target_score_away": sa,
                "target_over_under_2_5": {
                    "Over_2_5": 1 if sh + sa > 2 else 0,
                    "Under_2_5": 0 if sh + sa > 2 else 1,
                },
                "target_btts": {
                    "Yes": 1 if sh > 0 and sa > 0 else 0,
                    "No": 0 if sh > 0 and sa > 0 else 1,
                },
            },
        }

        entries.append(entry)
        processed.add(game_id)

    if len(entries) >= MIN_ENTRIES:
        tmp = os.path.join(TMP_DIR, f"{league}.json")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False)

        dataset.extend(entries)

        if PUSH_ENABLED:
            git_push(tmp, f"{league} dataset")

# ================= FINAL WRITE =================

tmp_file = OUTPUT_FILE + ".tmp"

with open(tmp_file, "w", encoding="utf-8") as f:
    json.dump(dataset, f, indent=2, ensure_ascii=False)

os.replace(tmp_file, OUTPUT_FILE)

print(f"✅ Dataset final: {len(dataset)} matchs")