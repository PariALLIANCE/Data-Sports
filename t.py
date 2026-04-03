import json
from collections import defaultdict

INPUT_FILE = "data-with-stats.json"
OUTPUT_FILE = "dataset-expert-full.json"

# 🔹 Historique équipes
team_history = defaultdict(lambda: {
    "goals_scored": [],
    "goals_conceded": [],
    "shots_on_target": [],
    "results": []  # 1=win, 0=draw, -1=lose
})

dataset = []

# ------------------------
# 🔧 UTILS
# ------------------------
def parse_percent(value):
    return float(value.replace("%","")) if "%" in value else float(value)

def parse_int(value):
    try:
        return int(value)
    except:
        return 0

def parse_score(score):
    try:
        home, away = score.split("-")
        return int(home.strip()), int(away.strip())
    except:
        return None, None

def get_result(home, away):
    if home > away:
        return 1, -1
    elif home < away:
        return -1, 1
    else:
        return 0, 0

def avg(lst, default=0):
    return sum(lst)/len(lst) if lst else default

def last_n(lst, n=8):  # 🔹 Utiliser les 8 derniers matchs
    return lst[-n:] if len(lst) >= n else lst

# ------------------------
# 📥 LOAD & SORT
# ------------------------
with open(INPUT_FILE,"r",encoding="utf-8") as f:
    matches = json.load(f)

# Tri par date si elle est bien formatée
matches = sorted(matches,key=lambda x:x.get("date",""))

# ------------------------
# 🔄 PROCESS
# ------------------------
for match in matches:
    stats = match.get("stats",{})
    if not stats:
        continue

    home = match["team1"]
    away = match["team2"]

    home_score, away_score = parse_score(match.get("score",""))
    if home_score is None:
        continue

    try:
        home_sot = parse_int(stats["Shots on Goal"]["home"])
        away_sot = parse_int(stats["Shots on Goal"]["away"])

        home_hist = team_history[home]
        away_hist = team_history[away]

        # ------------------------
        # 🔹 FEATURES HISTORIQUES (8 derniers matchs)
        # ------------------------
        data = {
            "home_form": avg(last_n(home_hist["results"],8)),
            "away_form": avg(last_n(away_hist["results"],8)),

            "home_goals_avg": avg(last_n(home_hist["goals_scored"],8)),
            "away_goals_avg": avg(last_n(away_hist["goals_scored"],8)),

            "home_conceded_avg": avg(last_n(home_hist["goals_conceded"],8)),
            "away_conceded_avg": avg(last_n(away_hist["goals_conceded"],8)),

            "home_sot_avg": avg(last_n(home_hist["shots_on_target"],8)),
            "away_sot_avg": avg(last_n(away_hist["shots_on_target"],8)),
        }

        # ------------------------
        # 🔹 FEATURES MATCH ACTUEL
        # ------------------------
        data.update({
            "home_possession": parse_percent(stats["Possession"]["home"]),
            "away_possession": parse_percent(stats["Possession"]["away"]),

            "home_shots_on_target": home_sot,
            "away_shots_on_target": away_sot,

            "home_shots": parse_int(stats["Shot Attempts"]["home"]),
            "away_shots": parse_int(stats["Shot Attempts"]["away"]),

            "home_corners": parse_int(stats["Corner Kicks"]["home"]),
            "away_corners": parse_int(stats["Corner Kicks"]["away"]),
        })

        # ------------------------
        # 🔹 SCORES & LABELS
        # ------------------------
        data["home_score"] = home_score
        data["away_score"] = away_score
        data["total_goals"] = home_score + away_score
        data["label"] = 1 if home_score>away_score else 2 if home_score<away_score else 0

        # Over/Under
        data["over_1_5"] = 1 if data["total_goals"]>1.5 else 0
        data["over_2_5"] = 1 if data["total_goals"]>2.5 else 0
        data["over_3_5"] = 1 if data["total_goals"]>3.5 else 0
        data["under_1_5"] = 1 - data["over_1_5"]

        # BTTS
        data["btts"] = 1 if home_score>0 and away_score>0 else 0

        # Différence de buts / handicap
        data["goal_diff"] = home_score - away_score

        # Score exact
        data["exact_score"] = f"{home_score}-{away_score}"

        dataset.append(data)

        # ------------------------
        # 🔹 UPDATE HISTORIQUE
        # ------------------------
        res_home,res_away = get_result(home_score, away_score)

        team_history[home]["goals_scored"].append(home_score)
        team_history[home]["goals_conceded"].append(away_score)
        team_history[home]["shots_on_target"].append(home_sot)
        team_history[home]["results"].append(res_home)

        team_history[away]["goals_scored"].append(away_score)
        team_history[away]["goals_conceded"].append(home_score)
        team_history[away]["shots_on_target"].append(away_sot)
        team_history[away]["results"].append(res_away)

    except KeyError:
        continue

# ------------------------
# 💾 SAVE
# ------------------------
with open(OUTPUT_FILE,"w",encoding="utf-8") as f:
    json.dump(dataset,f,indent=2)

print(f"✅ Dataset FULL FEATURES (8 derniers matchs) généré : {len(dataset)} matchs")