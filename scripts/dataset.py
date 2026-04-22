import json
import os
import glob
from datetime import datetime
from collections import defaultdict

# ================= CONFIG =================
LEAGUES_DIR    = "data/football/leagues"
STANDINGS_FILE = "data/football/standings/Standings.json"
OUTPUT_FILE    = "dataset_ml.json"
TMP_DIR        = "data/football/dataset_tmp"

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

# ================= CHARGEMENT STANDINGS =================
print(f"📂 Chargement des classements : {STANDINGS_FILE}")
with open(STANDINGS_FILE, "r", encoding="utf-8") as f:
    standings = json.load(f)
print(f"   {len(standings)} ligues dans le classement\n")

# ================= CHARGEMENT DE TOUS LES MATCHS =================
print(f"📂 Chargement des matchs depuis : {LEAGUES_DIR}")
json_files = sorted(glob.glob(os.path.join(LEAGUES_DIR, "*.json")))

if not json_files:
    print(f"❌ Aucun fichier JSON trouvé dans {LEAGUES_DIR}")
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
        score_h, score_a = parse_score(mc.get("score", ""))
        mc["_date_obj"]   = parse_date(mc.get("date", ""))
        mc["_score_home"] = score_h
        mc["_score_away"] = score_a
        mc["_league"]     = league_name
        all_matches.append(mc)

all_matches.sort(key=lambda m: m["_date_obj"])
print(f"   {len(all_matches)} matchs valides chargés\n")

# ── Index par équipe ──────────────────────────────────────────────────────────
team_history = defaultdict(list)
for m in all_matches:
    team_history[m.get("team1", "").strip()].append(m)
    team_history[m.get("team2", "").strip()].append(m)

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
        is_h   = m.get("team1", "").strip() == team_name
        sh, sa = m["_score_home"], m["_score_away"]
        res    = result_for_team(sh, sa, "home" if is_h else "away")
        o      = m["odds"]
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

# ================= CONSTRUCTION DU DATASET =================
print("=" * 60)
print("🔨 Construction du dataset...")
print("=" * 60)

os.makedirs(TMP_DIR, exist_ok=True)

try:
    processed_game_ids = set()
    league_tmp_files   = []

    for jf in json_files:
        league_name = os.path.splitext(os.path.basename(jf))[0]

        with open(jf, "r", encoding="utf-8") as f:
            matches_raw = json.load(f)

        matches_valid = []
        for m in matches_raw:
            if not is_valid_match(m):
                continue
            mc = dict(m)
            score_h, score_a = parse_score(mc.get("score", ""))
            mc["_date_obj"]   = parse_date(mc.get("date", ""))
            mc["_score_home"] = score_h
            mc["_score_away"] = score_a
            mc["_league"]     = league_name
            matches_valid.append(mc)

        matches_valid.sort(key=lambda m: m["_date_obj"])

        if not matches_valid:
            print(f"  ⏭️  {league_name} : aucun match valide")
            continue

        league_entries = []
        league_count   = 0

        for match in matches_valid:
            game_id = match.get("gameId")
            if not game_id or game_id in processed_game_ids:
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

            means_home = calc_means(hist_home_chron, team1)
            means_away = calc_means(hist_away_chron, team2)

            form_home = build_form(hist_home_chron, team1)
            form_away = build_form(hist_away_chron, team2)

            vaincu_h, invaincu_h = build_pos_adv(hist_home_chron, team1)
            vaincu_a, invaincu_a = build_pos_adv(hist_away_chron, team2)

            scores_home = build_scores_recents(hist_home_chron)
            scores_away = build_scores_recents(hist_away_chron)

            total_buts = score_h + score_a
            over_25    = 1 if total_buts > 2 else 0
            btts_yes   = 1 if score_h > 0 and score_a > 0 else 0
            result_1x2 = "1" if score_h > score_a else ("X" if score_h == score_a else "2")

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

                "cotes_match": {
                    "odds_home": odds.get("home"),
                    "odds_away": odds.get("away"),
                    "odds_draw": odds.get("draw"),
                },

                "targets": {
                    "target_1X2":          result_1x2,
                    "target_score_home":   score_h,
                    "target_score_away":   score_a,
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

            league_entries.append(entry)
            processed_game_ids.add(game_id)
            league_count += 1

        # ── Sauvegarde intermédiaire par ligue ────────────────────────────
        if league_entries:
            tmp_path = os.path.join(TMP_DIR, f"{league_name}.json")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(league_entries, f, ensure_ascii=False)
            league_tmp_files.append(tmp_path)

        print(f"  ✅ {league_name} : {league_count} entrées générées")

    # ── Assemblage final ──────────────────────────────────────────────────
    dataset = []
    for tmp_path in league_tmp_files:
        with open(tmp_path, "r", encoding="utf-8") as f:
            dataset.extend(json.load(f))

    if not dataset:
        print("⚠️  Dataset vide — aucune écriture effectuée")
    else:
        tmp_final = OUTPUT_FILE + ".tmp"
        with open(tmp_final, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        os.replace(tmp_final, OUTPUT_FILE)

        # Nettoyage des fichiers tmp par ligue
        for tmp_path in league_tmp_files:
            os.remove(tmp_path)

        print(f"\n{'='*60}")
        print(f"💾 Dataset sauvegardé : {OUTPUT_FILE}")
        print(f"   Total entrées       : {len(dataset)}")
        print(f"{'='*60}")

except Exception as e:
    print(f"\n❌ Erreur durant la construction : {e}")
    print("⚠️  Fichiers intermédiaires conservés dans {TMP_DIR}/")
    print("⚠️  dataset_ml.json inchangé")
    raise
