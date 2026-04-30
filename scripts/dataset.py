import json
import os
import glob
from datetime import datetime
from collections import defaultdict

# ================= CONFIG =================
LEAGUES_DIR    = "data/football/leagues"
STANDINGS_FILE = "data/football/standings/Standings.json"
OUTPUT_PREFIX  = "dataset_ml"   # → dataset_ml1.json, dataset_ml2.json, ...
NUM_PARTS      = 4              # Nombre de fichiers de sortie

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

# ================= CHARGEMENT STANDINGS =================
print(f"📂 Chargement des classements : {STANDINGS_FILE}")
with open(STANDINGS_FILE, "r", encoding="utf-8") as f:
    standings = json.load(f)
print(f"   {len(standings)} ligues dans le classement\n")

# ================= CHARGEMENT DE TOUS LES MATCHS =================
# (nécessaire pour construire team_history et h2h_index cross-league)
print(f"📂 Chargement de tous les matchs depuis : {LEAGUES_DIR}")
json_files = sorted(glob.glob(os.path.join(LEAGUES_DIR, "*.json")))

if not json_files:
    print(f"❌ Aucun fichier JSON trouvé dans {LEAGUES_DIR}")
    exit(1)

print(f"   {len(json_files)} fichiers JSON trouvés")

all_matches_with_odds = []

for jf in json_files:
    league_name = os.path.splitext(os.path.basename(jf))[0]
    with open(jf, "r", encoding="utf-8") as f:
        matches = json.load(f)
    for m in matches:
        if "odds" not in m:
            continue
        if not m.get("stats"):
            continue
        score_h, score_a = parse_score(m.get("score", ""))
        if score_h is None:
            continue
        dt = parse_date(m.get("date", ""))
        if dt is None:
            continue
        m["_date_obj"]   = dt
        m["_score_home"] = score_h
        m["_score_away"] = score_a
        m["_league"]     = league_name
        all_matches_with_odds.append(m)

all_matches_with_odds.sort(key=lambda m: m["_date_obj"])
print(f"   {len(all_matches_with_odds)} matchs valides chargés (cross-league)\n")

# ── Index par équipe ──────────────────────────────────────────────────────────
team_history = defaultdict(list)
for m in all_matches_with_odds:
    t1 = m.get("team1", "").strip()
    t2 = m.get("team2", "").strip()
    team_history[t1].append(m)
    team_history[t2].append(m)

# ── Index H2H ─────────────────────────────────────────────────────────────────
h2h_index = defaultdict(list)
for m in all_matches_with_odds:
    t1  = m.get("team1", "").strip()
    t2  = m.get("team2", "").strip()
    key = tuple(sorted([t1, t2]))
    h2h_index[key].append(m)

# ================= HELPERS =================

def get_last_n(team_name, before_dt, before_game_id, n=6):
    history = team_history.get(team_name, [])
    prev = [
        m for m in history
        if m["_date_obj"] < before_dt or
           (m["_date_obj"] == before_dt and m.get("gameId") != before_game_id)
    ]
    prev.sort(key=lambda m: m["_date_obj"], reverse=True)
    return prev[:n]

def get_h2h(team1, team2, before_dt, before_game_id, n=5):
    key = tuple(sorted([team1, team2]))
    history = h2h_index.get(key, [])
    prev = [
        m for m in history
        if m["_date_obj"] < before_dt or
           (m["_date_obj"] == before_dt and m.get("gameId") != before_game_id)
    ]
    prev.sort(key=lambda m: m["_date_obj"], reverse=True)
    return prev[:n]

def calc_means(history, team_name):
    poss_list, shots_list, buts_m_list, buts_e_list = [], [], [], []
    for m in history:
        s    = m.get("stats", {})
        is_h = m.get("team1", "").strip() == team_name
        side = "home" if is_h else "away"
        poss_list.append(parse_pct(s.get("Possession", {}).get(side, 0)))
        shots_list.append(float(s.get("Shots on Goal", {}).get(side, 0) or 0))
        buts_m_list.append(m["_score_home"] if is_h else m["_score_away"])
        buts_e_list.append(m["_score_away"] if is_h else m["_score_home"])
    return {
        "moy_possession":     safe_avg(poss_list),
        "moy_shots_ontarget": safe_avg(shots_list),
        "moy_buts_marques":   safe_avg(buts_m_list),
        "moy_buts_encaisses": safe_avg(buts_e_list),
    }

def build_form(history, team_name):
    form = []
    for m in history:
        is_h     = m.get("team1", "").strip() == team_name
        sh, sa   = m["_score_home"], m["_score_away"]
        res      = result_for_team(sh, sa, "home" if is_h else "away")
        o        = m["odds"]
        odd_home, odd_draw, odd_away = o["home"], o["draw"], o["away"]
        if sh > sa:
            winner_odd, draw_odd_val, loser_odd = odd_home, odd_draw, odd_away
        elif sa > sh:
            winner_odd, draw_odd_val, loser_odd = odd_away, odd_draw, odd_home
        else:
            winner_odd, draw_odd_val, loser_odd = odd_home, odd_draw, odd_away
        form.append(f"{res}:{winner_odd},{draw_odd_val},{loser_odd}")
    return form

def build_pos_adv(history, team_name):
    vaincu, invaincu = [], []
    for m in history:
        is_h   = m.get("team1", "").strip() == team_name
        sh, sa = m["_score_home"], m["_score_away"]
        res    = result_for_team(sh, sa, "home" if is_h else "away")
        adv    = m.get("team2" if is_h else "team1", "").strip()
        pos, _ = get_team_position(adv, standings)
        pos_str = str(pos) if pos is not None else "?"
        if res == "V":
            vaincu.append(pos_str)
        if res in ("V", "N"):
            invaincu.append(pos_str)
    return vaincu, invaincu

def build_scores_recents(history):
    return " | ".join(m.get("score", "?") for m in history)

def calc_h2h_metrics(h2h_matches, ref_team):
    wins = nuls = losses = 0
    buts_m, buts_e = [], []
    form = []
    for m in h2h_matches:
        is_h   = m.get("team1", "").strip() == ref_team
        sh, sa = m["_score_home"], m["_score_away"]
        res    = result_for_team(sh, sa, "home" if is_h else "away")
        if res == "V":
            wins += 1
        elif res == "N":
            nuls += 1
        else:
            losses += 1
        buts_m.append(sh if is_h else sa)
        buts_e.append(sa if is_h else sh)
        o = m["odds"]
        odd_home, odd_draw, odd_away = o["home"], o["draw"], o["away"]
        if sh > sa:
            winner_odd, draw_odd_val, loser_odd = odd_home, odd_draw, odd_away
        elif sa > sh:
            winner_odd, draw_odd_val, loser_odd = odd_away, odd_draw, odd_home
        else:
            winner_odd, draw_odd_val, loser_odd = odd_home, odd_draw, odd_away
        form.append(f"{res}:{winner_odd},{draw_odd_val},{loser_odd}")
    return {
        "h2h_wins":               wins,
        "h2h_nuls":               nuls,
        "h2h_losses":             losses,
        "h2h_moy_buts_marques":   safe_avg(buts_m),
        "h2h_moy_buts_encaisses": safe_avg(buts_e),
        "h2h_form":               form,
    }

# ================= DÉCOUPAGE EN PARTS =================
# On répartit les 32 fichiers en NUM_PARTS groupes équilibrés
def split_list(lst, n):
    """Divise lst en n sous-listes aussi équilibrées que possible."""
    k, r = divmod(len(lst), n)
    parts = []
    i = 0
    for p in range(n):
        size = k + (1 if p < r else 0)
        parts.append(lst[i:i + size])
        i += size
    return parts

file_groups = split_list(json_files, NUM_PARTS)

print("📋 Répartition des fichiers :")
for idx, group in enumerate(file_groups, 1):
    names = [os.path.splitext(os.path.basename(f))[0] for f in group]
    print(f"   Part {idx} ({len(group)} ligues) : {', '.join(names)}")
print()

# ================= CONSTRUCTION DES DATASETS =================
processed_game_ids = set()
total_entries = 0

print("=" * 60)
print("🔨 Construction des datasets...")
print("=" * 60)

for part_idx, group in enumerate(file_groups, 1):
    dataset = []

    for jf in group:
        league_name = os.path.splitext(os.path.basename(jf))[0]

        with open(jf, "r", encoding="utf-8") as f:
            matches_raw = json.load(f)

        matches_valid = []
        for m in matches_raw:
            if "odds" not in m:
                continue
            if not m.get("stats"):
                continue
            score_h, score_a = parse_score(m.get("score", ""))
            if score_h is None:
                continue
            dt = parse_date(m.get("date", ""))
            if dt is None:
                continue
            m["_date_obj"]   = dt
            m["_score_home"] = score_h
            m["_score_away"] = score_a
            m["_league"]     = league_name
            matches_valid.append(m)

        matches_valid.sort(key=lambda m: m["_date_obj"])

        if not matches_valid:
            continue

        league_count = 0

        for match in matches_valid:
            game_id = match.get("gameId")
            if game_id in processed_game_ids:
                continue

            team1    = match.get("team1", "").strip()
            team2    = match.get("team2", "").strip()
            date_str = match.get("date", "")
            dt       = match["_date_obj"]
            score_h  = match["_score_home"]
            score_a  = match["_score_away"]
            odds     = match["odds"]

            hist_home = get_last_n(team1, dt, game_id, n=6)
            hist_away = get_last_n(team2, dt, game_id, n=6)

            if len(hist_home) < 6 or len(hist_away) < 6:
                continue

            hist_home_chron = sorted(hist_home, key=lambda m: m["_date_obj"])
            hist_away_chron = sorted(hist_away, key=lambda m: m["_date_obj"])

            h2h_matches = get_h2h(team1, team2, dt, game_id, n=5)
            h2h_recent  = sorted(h2h_matches, key=lambda m: m["_date_obj"], reverse=True)

            means_home = calc_means(hist_home_chron, team1)
            means_away = calc_means(hist_away_chron, team2)

            form_home = build_form(hist_home_chron, team1)
            form_away = build_form(hist_away_chron, team2)

            vaincu_h, invaincu_h = build_pos_adv(hist_home_chron, team1)
            vaincu_a, invaincu_a = build_pos_adv(hist_away_chron, team2)

            scores_home = build_scores_recents(hist_home_chron)
            scores_away = build_scores_recents(hist_away_chron)

            h2h_metrics_home = calc_h2h_metrics(h2h_recent, team1)
            h2h_metrics_away = calc_h2h_metrics(h2h_recent, team2)

            total_buts = score_h + score_a
            over_25    = 1 if total_buts > 2 else 0
            btts_yes   = 1 if score_h > 0 and score_a > 0 else 0

            entry = {
                "gameId":  game_id,
                "date":    date_str,
                "league":  league_name,
                "team1":   team1,
                "team2":   team2,

                "Moy_6derniersmatchs": {
                    "moy_possession_home":     means_home["moy_possession"],
                    "moy_possession_away":     means_away["moy_possession"],
                    "moy_shots_ontarget_home": means_home["moy_shots_ontarget"],
                    "moy_shots_ontarget_away": means_away["moy_shots_ontarget"],
                    "moy_buts_marques_home":   means_home["moy_buts_marques"],
                    "moy_buts_marques_away":   means_away["moy_buts_marques"],
                    "moy_buts_encaisses_home": means_home["moy_buts_encaisses"],
                    "moy_buts_encaisses_away": means_away["moy_buts_encaisses"],
                },

                "Form_recents_with_odds_home": form_home,
                "Form_recents_with_odds_away": form_away,

                "pos_adv_vaincu_home":   vaincu_h,
                "pos_adv_vaincu_away":   vaincu_a,
                "pos_adv_invaincu_home": invaincu_h,
                "pos_adv_invaincu_away": invaincu_a,

                "scores_finaux_recents_home": scores_home,
                "scores_finaux_recents_away": scores_away,

                "h2h": {
                    "nb_matchs": len(h2h_recent),
                    "home":      h2h_metrics_home,
                    "away":      h2h_metrics_away,
                },

                "cotes_match": {
                    "odds_home": odds.get("home"),
                    "odds_away": odds.get("away"),
                    "odds_draw": odds.get("draw"),
                },

                "targets": {
                    "target_score_home": score_h,
                    "target_score_away": score_a,
                    "target_over_under_2_5": {
                        "Over_2_5":  over_25,
                        "Under_2_5": 1 - over_25,
                    },
                    "target_btts": {
                        "Yes": btts_yes,
                        "No":  1 - btts_yes,
                    },
                },
            }

            dataset.append(entry)
            processed_game_ids.add(game_id)
            league_count += 1

        print(f"  ✅ {league_name} : {league_count} entrées")

    # ── Sauvegarde de la part ──────────────────────────────────────────────────
    output_file = f"{OUTPUT_PREFIX}{part_idx}.json"
    tmp_file    = output_file + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, output_file)

    total_entries += len(dataset)
    print(f"\n  💾 {output_file} → {len(dataset)} entrées\n")

# ================= RÉSUMÉ =================
print("=" * 60)
print(f"✅ Terminé — {NUM_PARTS} fichiers générés")
print(f"   Total entrées : {total_entries}")
print(f"   Fichiers      : {', '.join(f'{OUTPUT_PREFIX}{i}.json' for i in range(1, NUM_PARTS+1))}")
print("=" * 60)
