import json
import os
import glob
from datetime import datetime

# ================= CONFIG =================
LEAGUES_WITH_ODDS_DIR = "data/football/leagues_with_odds"
STANDINGS_FILE        = "data/football/standings/Standings.json"
OUTPUT_FILE           = "dataset_ml.json"

# ================= UTILITAIRES =================

def parse_date(date_str):
    for fmt in ("%A, %B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    return None

def parse_score(score_str):
    """Retourne (buts_home, buts_away) depuis '1 - 2'."""
    try:
        parts = score_str.strip().split("-")
        return int(parts[0].strip()), int(parts[1].strip())
    except:
        return None, None

def parse_pct(val):
    """'52.4%' → 52.4"""
    try:
        return float(str(val).replace("%", "").strip())
    except:
        return 0.0

def get_team_position(team_name, standings):
    """
    Cherche la position d'une équipe dans standings par correspondance exacte.
    Retourne (position, league_key) ou (None, None).
    """
    for league_key, teams in standings.items():
        for t in teams:
            if t["name"] == team_name:
                return t["position"], league_key
    return None, None

def result_for_team(score_home, score_away, side):
    """'V', 'N', 'D' du point de vue de side ('home' ou 'away')."""
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

# ================= CHARGEMENT DE TOUS LES MATCHS AVEC CÔTES =================
# On charge tous les matchs avec côtes ET stats, toutes ligues confondues,
# pour pouvoir retrouver les 7 derniers matchs d'une équipe cross-ligue.

print(f"📂 Chargement des matchs avec côtes depuis : {LEAGUES_WITH_ODDS_DIR}")
json_files = sorted(glob.glob(os.path.join(LEAGUES_WITH_ODDS_DIR, "*.json")))

if not json_files:
    print(f"❌ Aucun fichier JSON trouvé dans {LEAGUES_WITH_ODDS_DIR}")
    exit(1)

all_matches_with_odds = []   # tous les matchs valides (côtes + stats + score)

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

# Tri global par date croissante
all_matches_with_odds.sort(key=lambda m: m["_date_obj"])

print(f"   {len(all_matches_with_odds)} matchs valides (avec côtes + stats + score) chargés\n")

# Index rapide : team_name → liste de matchs triés par date (croissant)
# Un match apparaît deux fois : une fois pour home, une fois pour away
from collections import defaultdict
team_history = defaultdict(list)   # team_name (exact) → [match, ...]

for m in all_matches_with_odds:
    t1 = m.get("team1", "").strip()
    t2 = m.get("team2", "").strip()
    team_history[t1].append(m)
    team_history[t2].append(m)

# ================= CONSTRUCTION DU DATASET =================
# Pour chaque ligue, on traite les matchs avec côtes par ordre croissant.
# On commence à générer une entrée dataset à partir du 8ème match avec côtes
# d'une équipe (on a donc 7 matchs d'historique).

dataset = []
processed_game_ids = set()

print("=" * 60)
print("🔨 Construction du dataset...")
print("=" * 60)

for jf in json_files:
    league_name = os.path.splitext(os.path.basename(jf))[0]

    with open(jf, "r", encoding="utf-8") as f:
        matches_raw = json.load(f)

    # Filtrer et trier par date croissante
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

    for i, match in enumerate(matches_valid):
        game_id = match.get("gameId")
        if game_id in processed_game_ids:
            continue

        team1     = match.get("team1", "").strip()
        team2     = match.get("team2", "").strip()
        date_str  = match.get("date", "")
        dt        = match["_date_obj"]
        score_h   = match["_score_home"]
        score_a   = match["_score_away"]
        odds      = match["odds"]
        stats     = match.get("stats", {})

        # ── Récupérer les 7 derniers matchs avec côtes AVANT ce match ──
        # pour chaque équipe, toutes ligues confondues

        def get_last_7(team_name, before_dt, before_game_id):
            """
            Retourne les 7 derniers matchs avec côtes de team_name
            strictement avant before_dt (ou même date mais gameId différent).
            """
            history = team_history.get(team_name, [])
            prev = [
                m for m in history
                if m["_date_obj"] < before_dt or
                   (m["_date_obj"] == before_dt and m.get("gameId") != before_game_id)
            ]
            prev.sort(key=lambda m: m["_date_obj"], reverse=True)
            return prev[:7]

        hist_home = get_last_7(team1, dt, game_id)
        hist_away = get_last_7(team2, dt, game_id)

        # On saute si l'une des équipes a moins de 7 matchs d'historique
        if len(hist_home) < 7 or len(hist_away) < 7:
            continue

        # Remettre dans l'ordre chronologique pour les calculs
        hist_home_chron = sorted(hist_home, key=lambda m: m["_date_obj"])
        hist_away_chron = sorted(hist_away, key=lambda m: m["_date_obj"])

        # ── Moyennes sur les 7 derniers matchs ──────────────────────────

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
                "moy_possession":      safe_avg(poss_list),
                "moy_shots_ontarget":  safe_avg(shots_list),
                "moy_buts_marques":    safe_avg(buts_m_list),
                "moy_buts_encaisses":  safe_avg(buts_e_list),
            }

        means_home = calc_means(hist_home_chron, team1)
        means_away = calc_means(hist_away_chron, team2)

        # ── Form recents with odds ───────────────────────────────────────

        def build_form(history, team_name):
            """
            Pour chaque match dans l'historique (ordre chronologique) :
            - résultat du point de vue de team_name (V/N/D)
            - cote_vainqueur, cote_nul, cote_perdant
            Pour un nul : cote_home, cote_nul, cote_away (ordre conventionnel)
            """
            form = []
            for m in history:
                is_h     = m.get("team1", "").strip() == team_name
                sh, sa   = m["_score_home"], m["_score_away"]
                res      = result_for_team(sh, sa, "home" if is_h else "away")
                o        = m["odds"]
                odd_home = o["home"]
                odd_draw = o["draw"]
                odd_away = o["away"]

                if sh > sa:
                    # Home a gagné
                    winner_odd, draw_odd_val, loser_odd = odd_home, odd_draw, odd_away
                elif sa > sh:
                    # Away a gagné
                    winner_odd, draw_odd_val, loser_odd = odd_away, odd_draw, odd_home
                else:
                    # Nul : ordre conventionnel home, nul, away
                    winner_odd, draw_odd_val, loser_odd = odd_home, odd_draw, odd_away

                form.append(f"{res}:{winner_odd},{draw_odd_val},{loser_odd}")
            return form

        form_home = build_form(hist_home_chron, team1)
        form_away = build_form(hist_away_chron, team2)

        # ── pos_adv_vaincu / pos_adv_invaincu ───────────────────────────

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

        vaincu_h, invaincu_h = build_pos_adv(hist_home_chron, team1)
        vaincu_a, invaincu_a = build_pos_adv(hist_away_chron, team2)

        # ── Scores finaux récents ────────────────────────────────────────

        def build_scores_recents(history, team_name):
            scores = []
            for m in history:
                scores.append(m.get("score", "?"))
            return " | ".join(scores)

        scores_home = build_scores_recents(hist_home_chron, team1)
        scores_away = build_scores_recents(hist_away_chron, team2)

        # ── Targets (binaires depuis le score réel) ──────────────────────

        total_buts = score_h + score_a
        over_25    = 1 if total_buts > 2 else 0
        under_25   = 1 - over_25
        btts_yes   = 1 if score_h > 0 and score_a > 0 else 0
        btts_no    = 1 - btts_yes

        # Spread : home gagne par 2+ buts → home_1.5 = 1
        home_spread = 1 if (score_h - score_a) >= 2 else 0
        away_spread = 1 if (score_a - score_h) >= 2 else 0

        # Target score
        target_score_home = score_h
        target_score_away = score_a

        # ── Assemblage de l'entrée dataset ──────────────────────────────

        entry = {
            "gameId":   game_id,
            "date":     date_str,
            "league":   league_name,
            "team1":    team1,
            "team2":    team2,

            "Moy_7derniersmatchs": {
                "moy_possession_home":      means_home["moy_possession"],
                "moy_possession_away":      means_away["moy_possession"],
                "moy_shots_ontarget_home":  means_home["moy_shots_ontarget"],
                "moy_shots_ontarget_away":  means_away["moy_shots_ontarget"],
                "moy_buts_marques_home":    means_home["moy_buts_marques"],
                "moy_buts_marques_away":    means_away["moy_buts_marques"],
                "moy_buts_encaisses_home":  means_home["moy_buts_encaisses"],
                "moy_buts_encaisses_away":  means_away["moy_buts_encaisses"],
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
                "target_score_home": target_score_home,
                "target_score_away": target_score_away,
                "target_over_under_2_5": {
                    "Over_2_5": over_25,
                    "Under_2_5": under_25,
                },
                "target_btts": {
                    "Yes": btts_yes,
                    "No":  btts_no,
                },
                "target_spread": {
                    "home_plus1_5": home_spread,
                    "away_plus1_5": away_spread,
                },
            },
        }

        dataset.append(entry)
        processed_game_ids.add(game_id)
        league_count += 1

    print(f"  ✅ {league_name} : {league_count} entrées générées")

# ================= SAUVEGARDE =================
tmp_file = OUTPUT_FILE + ".tmp"
with open(tmp_file, "w", encoding="utf-8") as f:
    json.dump(dataset, f, indent=2, ensure_ascii=False)
os.replace(tmp_file, OUTPUT_FILE)

print(f"\n{'='*60}")
print(f"💾 Dataset sauvegardé : {OUTPUT_FILE}")
print(f"   Total entrées       : {len(dataset)}")
print(f"{'='*60}")