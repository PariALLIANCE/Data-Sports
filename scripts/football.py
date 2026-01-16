import os
import json
import requests
from datetime import datetime

# ================== CONFIG ==================
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or "REMPLACE_PAR_TA_CLE_API"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_ID = "openai/gpt-oss-120b"

INPUT_FILE = "data/football/games_of_day.json"
OUTPUT_DIR = "data/football/predictions"
# ===========================================


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Fichier sauvegardé : {os.path.abspath(path)}")


def ask_gpt_oss(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL_ID,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Tu es un analyste football professionnel. "
                    "Fournis une analyse détaillée du match, en expliquant la forme des équipes, "
                    "les forces, faiblesses, tendances tactiques, impact des statistiques, "
                    "et termine par une prédiction claire et argumentée. "
                    "Réponds uniquement en texte, pas en JSON."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.4
    }

    r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def build_prompt(match):
    return f"""
Analyse ce match de manière approfondie :

{json.dumps(match, indent=2, ensure_ascii=False)}

Je veux :
- une analyse tactique,
- une lecture de la forme récente,
- une interprétation des statistiques,
- une prise en compte des cotes,
- une conclusion avec un scénario probable.
"""


def main():
    print("📂 Chargement de games_of_day.json...")
    games = load_json(INPUT_FILE)

    enriched_games = []

    for match in games:
        print(f"⚽ Analyse IA : {match['team1']} vs {match['team2']}")

        prompt = build_prompt(match)

        try:
            analysis_text = ask_gpt_oss(prompt)
            match["Analyse"] = analysis_text
        except Exception as e:
            print(f"❌ Erreur GPT : {e}")
            match["Analyse"] = f"Erreur lors de l’analyse IA : {e}"

        enriched_games.append(match)

    today = datetime.now().strftime("%Y-%m-%d")
    output_file = os.path.join(OUTPUT_DIR, f"games-{today}.json")

    save_json(output_file, enriched_games)

    print("===================================")
    print("✅ ANALYSE FOOTBALL IA TERMINÉE")
    print(f"📁 Fichier final : {output_file}")
    print(f"⚽ Matchs analysés : {len(enriched_games)}")
    print("===================================")


if __name__ == "__main__":
    main()