#!/usr/bin/env python3
"""
games_models.py
Convertit games_of_day.json → prediction_input.json
"""

import json
import re
from pathlib import Path


# ── Helpers ────────────────────────────────────────────────────────────────────

def safe_float(val, default=0.0):
    try:
        return float(str(val).replace("%", "").strip())
    except (ValueError, TypeError, AttributeError):
        return default


def parse_score(score_str):
    parts = re.findall(r"\d+", str(score_str))
    return (int(parts[0]), int(parts[1])) if len(parts) >= 2 else (0, 0)


def get_team_stats_from_match(match_data, team_name):
    """
    Dans ESPN, team1 = home, team2 = away dans les stats.
    On détermine le côté de notre équipe via team1/team2.
    """
    t1 = match_data.get("team1", "")
    t2 = match_data.get("team2", "")
    g1, g2 = parse_score(match_data.get("score", "0 - 0"))
    stats = match_data.get("stats", {}) or {}

    # Notre équipe est-elle team1 (home dans les stats) ?
    team_lower = team_name.lower()
    if team_lower in t1.lower():
        pov, gs, gc = "home", g1, g2
    elif team_lower in t2.lower():
        pov, gs, gc = "away", g2, g1
    else:
        # Fallback : correspondance partielle
        pov = "home" if t1 else "away"
        gs, gc = (g1, g2) if pov == "home" else (g2, g1)

    def s(key):
        bloc = stats.get(key, {})
        if not isinstance(bloc, dict):
            return 0.0
        return safe_float(bloc.get(pov, 0.0))

    return {
        "gs": gs, "gc": gc,
        "possession": s("Possession"),
        "shots_on_target": s("Shots on Goal"),
        "shot_attempts": s("Shot Attempts"),
        "saves": s("Saves"),
        "corners": s("Corner Kicks"),
        "yellow_cards": s("Yellow Cards"),
    }


def compute_form_features(recent_matches, team_name):
    wins = draws = losses = clean_sheets = big_wins = 0
    possession_l, shots_l, scored_l, conceded_l, saves_l, corners_l = [], [], [], [], [], []

    for m in (recent_matches or []):
        if not isinstance(m, dict):
            continue
        s = get_team_stats_from_match(m, team_name)
        gs, gc = s["gs"], s["gc"]

        if gs > gc:   wins += 1
        elif gs == gc: draws += 1
        else:          losses += 1

        if gc == 0:        clean_sheets += 1
        if gs - gc >= 2:   big_wins += 1

        scored_l.append(gs)
        conceded_l.append(gc)
        if s["possession"] > 0:    possession_l.append(s["possession"])
        if s["shots_on_target"] > 0: shots_l.append(s["shots_on_target"])
        saves_l.append(s["saves"])
        corners_l.append(s["corners"])

    n = len(recent_matches) if recent_matches else 1
    avg = lambda lst: round(sum(lst) / len(lst), 4) if lst else 0.0

    return {
        "wins": wins, "draws": draws, "losses": losses,
        "win_rate":  round(wins  / n, 4),
        "draw_rate": round(draws / n, 4),
        "loss_rate": round(losses / n, 4),
        "avg_possession":      avg(possession_l),
        "avg_shots_on_target": avg(shots_l),
        "avg_saves":           avg(saves_l),
        "avg_corners":         avg(corners_l),
        "avg_scored":          avg(scored_l),
        "avg_conceded":        avg(conceded_l),
        "clean_sheet_rate":    round(clean_sheets / n, 4),
        "big_win_rate":        round(big_wins / n, 4),
        "total_goals_avg":     avg([s + c for s, c in zip(scored_l, conceded_l)]),
        # Pas de cotes dans recent_form
        "avg_odds_home": 0.0, "avg_odds_draw": 0.0,
        "avg_odds_away": 0.0, "avg_implied_prob_winner": 0.0,
    }


def get_standing(league_standing, team_name):
    empty = {k: 0 for k in ["position", "gp", "wins", "draws", "losses",
                             "goals_for", "goals_against", "goal_diff", "points"]}
    if not league_standing:
        return empty
    team_lower = team_name.lower()
    for entry in league_standing:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not name:
            continue
        if name.lower() == team_lower:
            s = entry.get("stats") or {}
            gp = s.get("GP", 0) or 0
            return {
                "position":      entry.get("position", 0) or 0,
                "gp":            gp,
                "wins":          s.get("W", 0) or 0,
                "draws":         s.get("D", 0) or 0,
                "losses":        s.get("L", 0) or 0,
                "goals_for":     s.get("F", 0) or 0,
                "goals_against": s.get("A", 0) or 0,
                "goal_diff":     s.get("GD", 0) or 0,
                "points":        s.get("P", 0) or 0,
            }
    return empty


def compute_h2h_features(h2h_matches, home_team, away_team):
    home_wins = away_wins = draws = 0
    total_goals = []

    for m in (h2h_matches or []):
        if not isinstance(m, dict):
            continue
        g1, g2 = parse_score(m.get("score", "0 - 0"))
        t1 = m.get("team1", "")
        total_goals.append(g1 + g2)

        if home_team.lower() in t1.lower():
            if g1 > g2:   home_wins += 1
            elif g1 < g2: away_wins += 1
            else:          draws += 1
        else:
            if g2 > g1:   home_wins += 1
            elif g2 < g1: away_wins += 1
            else:          draws += 1

    n = len(h2h_matches) if h2h_matches else 1
    avg = lambda lst: round(sum(lst) / len(lst), 4) if lst else 0.0

    return {
        "h2h_count":            n,
        "h2h_home_win_rate":    round(home_wins / n, 4),
        "h2h_away_win_rate":    round(away_wins / n, 4),
        "h2h_draw_rate":        round(draws / n, 4),
        "h2h_avg_total_goals":  avg(total_goals),
    }


def build_prediction_entry(match):
    home_team = match["home"]["team"]
    away_team = match["away"]["team"]
    odds = match.get("odds") or {}
    recent_form = match.get("recent_form") or {}
    league_standing = match.get("league_standing") or []
    h2h = match.get("h2h") or []

    form_home = compute_form_features(recent_form.get("home", []), home_team)
    form_away = compute_form_features(recent_form.get("away", []), away_team)

    standing_home = get_standing(league_standing, home_team)
    standing_away = get_standing(league_standing, away_team)

    h2h_features = compute_h2h_features(h2h, home_team, away_team)

    odds_home = safe_float(odds.get("home", 0))
    odds_draw = safe_float(odds.get("draw", 0))
    odds_away = safe_float(odds.get("away", 0))

    raw_ph = 1 / odds_home if odds_home else 0
    raw_pd = 1 / odds_draw if odds_draw else 0
    raw_pa = 1 / odds_away if odds_away else 0
    total_raw = raw_ph + raw_pd + raw_pa or 1
    imp_home = round(raw_ph / total_raw, 4)
    imp_draw = round(raw_pd / total_raw, 4)
    imp_away = round(raw_pa / total_raw, 4)

    sh_gp = standing_home["gp"]
    sa_gp = standing_away["gp"]

    features = {
        # Stats moyennes (alignées dataset entraînement)
        "moy_possession_home":      form_home["avg_possession"],
        "moy_possession_away":      form_away["avg_possession"],
        "moy_shots_ontarget_home":  form_home["avg_shots_on_target"],
        "moy_shots_ontarget_away":  form_away["avg_shots_on_target"],
        "moy_buts_marques_home":    form_home["avg_scored"],
        "moy_buts_marques_away":    form_away["avg_scored"],
        "moy_buts_encaisses_home":  form_home["avg_conceded"],
        "moy_buts_encaisses_away":  form_away["avg_conceded"],
        # Différentiels
        "diff_possession":      round(form_home["avg_possession"]      - form_away["avg_possession"],      4),
        "diff_shots_ontarget":  round(form_home["avg_shots_on_target"] - form_away["avg_shots_on_target"], 4),
        "diff_buts_marques":    round(form_home["avg_scored"]          - form_away["avg_scored"],          4),
        "diff_buts_encaisses":  round(form_home["avg_conceded"]        - form_away["avg_conceded"],        4),
        # Forme home
        "home_wins":                    form_home["wins"],
        "home_draws":                   form_home["draws"],
        "home_losses":                  form_home["losses"],
        "home_win_rate":                form_home["win_rate"],
        "home_draw_rate":               form_home["draw_rate"],
        "home_loss_rate":               form_home["loss_rate"],
        "home_avg_odds_home":           form_home["avg_odds_home"],
        "home_avg_odds_draw":           form_home["avg_odds_draw"],
        "home_avg_odds_away":           form_home["avg_odds_away"],
        "home_avg_implied_prob_winner": form_home["avg_implied_prob_winner"],
        # Forme away
        "away_wins":                    form_away["wins"],
        "away_draws":                   form_away["draws"],
        "away_losses":                  form_away["losses"],
        "away_win_rate":                form_away["win_rate"],
        "away_draw_rate":               form_away["draw_rate"],
        "away_loss_rate":               form_away["loss_rate"],
        "away_avg_odds_home":           form_away["avg_odds_home"],
        "away_avg_odds_draw":           form_away["avg_odds_draw"],
        "away_avg_odds_away":           form_away["avg_odds_away"],
        "away_avg_implied_prob_winner": form_away["avg_implied_prob_winner"],
        # Scores récents
        "home_avg_scored":        form_home["avg_scored"],
        "home_avg_conceded":      form_home["avg_conceded"],
        "home_clean_sheet_rate":  form_home["clean_sheet_rate"],
        "home_big_win_rate":      form_home["big_win_rate"],
        "home_total_goals_avg":   form_home["total_goals_avg"],
        "away_avg_scored":        form_away["avg_scored"],
        "away_avg_conceded":      form_away["avg_conceded"],
        "away_clean_sheet_rate":  form_away["clean_sheet_rate"],
        "away_big_win_rate":      form_away["big_win_rate"],
        "away_total_goals_avg":   form_away["total_goals_avg"],
        # Pos adversaires
        "home_vaincu_count":    form_home["wins"],
        "home_vaincu_avg_pos":  0.0,
        "home_vaincu_min_pos":  0,
        "away_vaincu_count":    form_away["wins"],
        "away_vaincu_avg_pos":  0.0,
        "away_vaincu_min_pos":  0,
        "home_invaincu_count":  form_home["wins"] + form_home["draws"],
        "home_invaincu_avg_pos": 0.0,
        "away_invaincu_count":  form_away["wins"] + form_away["draws"],
        "away_invaincu_avg_pos": 0.0,
        # Cotes
        "odds_home":      odds_home,
        "odds_draw":      odds_draw,
        "odds_away":      odds_away,
        "imp_prob_home":  imp_home,
        "imp_prob_draw":  imp_draw,
        "imp_prob_away":  imp_away,
        # Classement
        "home_position":       standing_home["position"],
        "home_points":         standing_home["points"],
        "home_goal_diff":      standing_home["goal_diff"],
        "home_season_win_rate": round(standing_home["wins"] / sh_gp, 4) if sh_gp else 0.0,
        "away_position":       standing_away["position"],
        "away_points":         standing_away["points"],
        "away_goal_diff":      standing_away["goal_diff"],
        "away_season_win_rate": round(standing_away["wins"] / sa_gp, 4) if sa_gp else 0.0,
        "diff_position":       standing_home["position"] - standing_away["position"],
        "diff_points":         standing_home["points"]   - standing_away["points"],
        # H2H
        **h2h_features,
        # Méta
        "gameId": match.get("gameId", ""),
        "league": match.get("league", ""),
        "date":   match.get("date", ""),
        "team1":  home_team,
        "team2":  away_team,
    }

    header = {
        "gameId":    match.get("gameId"),
        "date":      match.get("date"),
        "time_utc":  match.get("time_utc"),
        "league":    match.get("league"),
        "match_url": match.get("match_url"),
        "home":      match["home"],
        "away":      match["away"],
        "odds":      odds,
    }

    return {"header": header, "features": features}


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    root = Path(__file__).parent.parent
    input_path  = root / "data" / "football" / "games_of_day.json"
    output_path = root / "data" / "football" / "prediction_input.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Lecture de {input_path} ...")
    with open(input_path, "r", encoding="utf-8") as f:
        matches = json.load(f)

    results = []
    for match in matches:
        if not isinstance(match, dict):
            continue
        try:
            entry = build_prediction_entry(match)
            results.append(entry)
        except Exception as e:
            gid = match.get("gameId", "?")
            print(f"⚠️  Erreur gameId={gid} : {e}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✅  {len(results)} matchs convertis → {output_path}")


if __name__ == "__main__":
    main()
