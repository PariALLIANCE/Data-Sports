#!/usr/bin/env python3
"""
transform_dataset.py
Lit dataset_ml.json à la racine et génère 4 JSON d'entraînement dans ./dataset/
"""

import json
import os
import re
from pathlib import Path


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_form_with_odds(form_list):
    """
    ['V:2.8,3.3,2.6', 'D:2.45,3.3,2.85', ...]
    → features agrégées sur les 7 derniers matchs
    """
    results = {"W": 0, "D": 0, "L": 0}
    odds_home_list, odds_draw_list, odds_away_list = [], [], []
    implied_prob_winner_list = []

    result_map = {"V": "W", "N": "D", "D": "L"}

    for entry in form_list:
        if ":" not in entry:
            continue
        result_char, odds_str = entry.split(":", 1)
        result_key = result_map.get(result_char.strip(), "D")
        results[result_key] += 1

        parts = odds_str.strip().split(",")
        if len(parts) == 3:
            try:
                o1, od, o2 = float(parts[0]), float(parts[1]), float(parts[2])
                odds_home_list.append(o1)
                odds_draw_list.append(od)
                odds_away_list.append(o2)
                if result_key == "W":
                    implied_prob_winner_list.append(1 / o1)
                elif result_key == "D":
                    implied_prob_winner_list.append(1 / od)
                else:
                    implied_prob_winner_list.append(1 / o2)
            except ValueError:
                pass

    n = len(form_list) or 1
    avg = lambda lst: round(sum(lst) / len(lst), 4) if lst else 0.0

    return {
        "wins": results["W"],
        "draws": results["D"],
        "losses": results["L"],
        "win_rate": round(results["W"] / n, 4),
        "draw_rate": round(results["D"] / n, 4),
        "loss_rate": round(results["L"] / n, 4),
        "avg_odds_home": avg(odds_home_list),
        "avg_odds_draw": avg(odds_draw_list),
        "avg_odds_away": avg(odds_away_list),
        "avg_implied_prob_winner": avg(implied_prob_winner_list),
    }


def parse_pos_adv(pos_list):
    """
    ['24', '2', '6'] → stats sur les positions des adversaires
    """
    if not pos_list:
        return {"count": 0, "avg_pos": 0.0, "min_pos": 0, "max_pos": 0}
    vals = [int(x) for x in pos_list if str(x).isdigit()]
    if not vals:
        return {"count": 0, "avg_pos": 0.0, "min_pos": 0, "max_pos": 0}
    return {
        "count": len(vals),
        "avg_pos": round(sum(vals) / len(vals), 4),
        "min_pos": min(vals),
        "max_pos": max(vals),
    }


def parse_recent_scores(scores_str, perspective="home"):
    """
    '1 - 0 | 1 - 0 | 2 - 2 | ...' (score du point de vue de l'équipe)
    → buts marqués/encaissés moyens, clean sheets, big wins
    """
    if not scores_str:
        return {}
    matches = scores_str.split("|")
    scored, conceded, clean_sheets, big_wins = [], [], 0, 0

    for m in matches:
        m = m.strip()
        parts = re.findall(r"\d+", m)
        if len(parts) >= 2:
            gs, gc = int(parts[0]), int(parts[1])
            scored.append(gs)
            conceded.append(gc)
            if gc == 0:
                clean_sheets += 1
            if gs - gc >= 2:
                big_wins += 1

    n = len(scored) or 1
    avg = lambda lst: round(sum(lst) / len(lst), 4) if lst else 0.0

    return {
        "avg_scored": avg(scored),
        "avg_conceded": avg(conceded),
        "clean_sheet_rate": round(clean_sheets / n, 4),
        "big_win_rate": round(big_wins / n, 4),
        "total_goals_avg": avg([s + c for s, c in zip(scored, conceded)]),
    }


def extract_base_features(match):
    """Construit le vecteur de features commun à tous les modèles."""
    m7 = match.get("Moy_7derniersmatchs", {})
    cotes = match.get("cotes_match", {})

    form_home = parse_form_with_odds(match.get("Form_recents_with_odds_home", []))
    form_away = parse_form_with_odds(match.get("Form_recents_with_odds_away", []))

    pos_vaincu_home = parse_pos_adv(match.get("pos_adv_vaincu_home", []))
    pos_vaincu_away = parse_pos_adv(match.get("pos_adv_vaincu_away", []))
    pos_invaincu_home = parse_pos_adv(match.get("pos_adv_invaincu_home", []))
    pos_invaincu_away = parse_pos_adv(match.get("pos_adv_invaincu_away", []))

    scores_home = parse_recent_scores(match.get("scores_finaux_recents_home", ""), "home")
    scores_away = parse_recent_scores(match.get("scores_finaux_recents_away", ""), "away")

    odds_home = cotes.get("odds_home", 0)
    odds_draw = cotes.get("odds_draw", 0)
    odds_away = cotes.get("odds_away", 0)

    raw_ph = 1 / odds_home if odds_home else 0
    raw_pd = 1 / odds_draw if odds_draw else 0
    raw_pa = 1 / odds_away if odds_away else 0
    total_raw = raw_ph + raw_pd + raw_pa or 1
    imp_home = round(raw_ph / total_raw, 4)
    imp_draw = round(raw_pd / total_raw, 4)
    imp_away = round(raw_pa / total_raw, 4)

    features = {
        "moy_possession_home": m7.get("moy_possession_home", 0),
        "moy_possession_away": m7.get("moy_possession_away", 0),
        "moy_shots_ontarget_home": m7.get("moy_shots_ontarget_home", 0),
        "moy_shots_ontarget_away": m7.get("moy_shots_ontarget_away", 0),
        "moy_buts_marques_home": m7.get("moy_buts_marques_home", 0),
        "moy_buts_marques_away": m7.get("moy_buts_marques_away", 0),
        "moy_buts_encaisses_home": m7.get("moy_buts_encaisses_home", 0),
        "moy_buts_encaisses_away": m7.get("moy_buts_encaisses_away", 0),
        "diff_possession": round(m7.get("moy_possession_home", 0) - m7.get("moy_possession_away", 0), 4),
        "diff_shots_ontarget": round(m7.get("moy_shots_ontarget_home", 0) - m7.get("moy_shots_ontarget_away", 0), 4),
        "diff_buts_marques": round(m7.get("moy_buts_marques_home", 0) - m7.get("moy_buts_marques_away", 0), 4),
        "diff_buts_encaisses": round(m7.get("moy_buts_encaisses_home", 0) - m7.get("moy_buts_encaisses_away", 0), 4),
        "home_wins": form_home["wins"],
        "home_draws": form_home["draws"],
        "home_losses": form_home["losses"],
        "home_win_rate": form_home["win_rate"],
        "home_draw_rate": form_home["draw_rate"],
        "home_loss_rate": form_home["loss_rate"],
        "home_avg_odds_home": form_home["avg_odds_home"],
        "home_avg_odds_draw": form_home["avg_odds_draw"],
        "home_avg_odds_away": form_home["avg_odds_away"],
        "home_avg_implied_prob_winner": form_home["avg_implied_prob_winner"],
        "away_wins": form_away["wins"],
        "away_draws": form_away["draws"],
        "away_losses": form_away["losses"],
        "away_win_rate": form_away["win_rate"],
        "away_draw_rate": form_away["draw_rate"],
        "away_loss_rate": form_away["loss_rate"],
        "away_avg_odds_home": form_away["avg_odds_home"],
        "away_avg_odds_draw": form_away["avg_odds_draw"],
        "away_avg_odds_away": form_away["avg_odds_away"],
        "away_avg_implied_prob_winner": form_away["avg_implied_prob_winner"],
        "home_vaincu_count": pos_vaincu_home["count"],
        "home_vaincu_avg_pos": pos_vaincu_home["avg_pos"],
        "home_vaincu_min_pos": pos_vaincu_home["min_pos"],
        "away_vaincu_count": pos_vaincu_away["count"],
        "away_vaincu_avg_pos": pos_vaincu_away["avg_pos"],
        "away_vaincu_min_pos": pos_vaincu_away["min_pos"],
        "home_invaincu_count": pos_invaincu_home["count"],
        "home_invaincu_avg_pos": pos_invaincu_home["avg_pos"],
        "away_invaincu_count": pos_invaincu_away["count"],
        "away_invaincu_avg_pos": pos_invaincu_away["avg_pos"],
        "home_avg_scored": scores_home.get("avg_scored", 0),
        "home_avg_conceded": scores_home.get("avg_conceded", 0),
        "home_clean_sheet_rate": scores_home.get("clean_sheet_rate", 0),
        "home_big_win_rate": scores_home.get("big_win_rate", 0),
        "home_total_goals_avg": scores_home.get("total_goals_avg", 0),
        "away_avg_scored": scores_away.get("avg_scored", 0),
        "away_avg_conceded": scores_away.get("avg_conceded", 0),
        "away_clean_sheet_rate": scores_away.get("clean_sheet_rate", 0),
        "away_big_win_rate": scores_away.get("big_win_rate", 0),
        "away_total_goals_avg": scores_away.get("total_goals_avg", 0),
        "odds_home": odds_home,
        "odds_draw": odds_draw,
        "odds_away": odds_away,
        "imp_prob_home": imp_home,
        "imp_prob_draw": imp_draw,
        "imp_prob_away": imp_away,
        "gameId": match.get("gameId", ""),
        "league": match.get("league", ""),
        "date": match.get("date", ""),
        "team1": match.get("team1", ""),
        "team2": match.get("team2", ""),
    }

    return features


def determine_1x2(targets):
    """Retourne 0=Home, 1=Draw, 2=Away"""
    sh = targets.get("target_score_home", 0)
    sa = targets.get("target_score_away", 0)
    if sh > sa:
        return 0
    elif sh == sa:
        return 1
    else:
        return 2


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    root = Path(__file__).parent.parent  # scripts/ → racine du repo
    input_path = root / "dataset_ml.json"
    output_dir = root / "dataset"
    output_dir.mkdir(exist_ok=True)

    print(f"Lecture de {input_path} ...")
    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        matches = raw.get("matches", list(raw.values()))
    else:
        matches = raw

    print(f"{len(matches)} matchs trouvés.")

    ds_1x2, ds_ou25, ds_btts, ds_score = [], [], [], []
    skipped = 0

    for match in matches:
        targets = match.get("targets", {})
        if not targets:
            skipped += 1
            continue

        features = extract_base_features(match)

        # ── Modèle 1 : 1X2 ──────────────────────────────────────────────────
        label_1x2 = determine_1x2(targets)
        ds_1x2.append({**features, "label": label_1x2})

        # ── Modèle 2 : Over/Under 2.5 ───────────────────────────────────────
        ou = targets.get("target_over_under_2_5", {})
        label_ou = ou.get("Over_2_5", None)
        if label_ou is not None:
            ds_ou25.append({**features, "label": int(label_ou)})

        # ── Modèle 3 : BTTS ─────────────────────────────────────────────────
        btts = targets.get("target_btts", {})
        label_btts = btts.get("Yes", None)
        if label_btts is not None:
            ds_btts.append({**features, "label": int(label_btts)})

        # ── Modèle 4 : Score exact ───────────────────────────────────────────
        sh = targets.get("target_score_home")
        sa = targets.get("target_score_away")
        if sh is not None and sa is not None:
            ds_score.append({
                **features,
                "label_score_home": int(sh),
                "label_score_away": int(sa),
            })

    outputs = {
        "model_1x2.json": ds_1x2,
        "model_over_under_2_5.json": ds_ou25,
        "model_btts.json": ds_btts,
        "model_score_exact.json": ds_score,
    }

    for filename, dataset in outputs.items():
        path = output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        print(f"✅  {filename:35s} → {len(dataset):>5} samples  ({path})")

    if skipped:
        print(f"⚠️  {skipped} matchs ignorés (targets manquants)")

    print("\nTransformation terminée.")


if __name__ == "__main__":
    main()