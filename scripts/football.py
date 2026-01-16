import os
import json
import requests
from datetime import datetime
import re
import time

# ================== CONFIG ==================
API_KEY = os.getenv("GROQ1")
MODEL_ID = "openai/gpt-oss-120b"

INPUT_FILE = "data/football/games_of_day.json"
OUTPUT_DIR = "data/football/predictions"

MAX_TOKENS = 4000
TEMPERATURE = 0.4
RETRY_DELAY = 5      # secondes avant de réessayer
MAX_RETRIES = 15     # nombre maximal de tentatives

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# ===========================================

def load_json(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Fichier sauvegardé : {os.path.abspath(path)}")

def build_structured_prompt(match):
    return f"""
Tu es un analyste football professionnel spécialisé dans les pronostics sportifs. Analyse ce match en profondeur à partir de toutes les données disponibles :

- Forme récente des équipes
- Confrontations directes (H2H)
- Statistiques clés et tendances
- Impact des joueurs clés
- Cotes et probabilités implicites
- Classements détaillés

Tâches à réaliser :

1️⃣ Fournis **une seule prédiction textuelle humaine**, parmi les options suivantes :

- Victoire {match['team1']}
- Victoire {match['team2']}
- Victoire {match['team1']} ou Nul
- Victoire {match['team2']} ou Nul
- Total +1.5 buts
- Total -3.5 buts
- Les deux équipes marquent Oui
- Les deux équipes marquent Non
- Total corners +7.5
- Total corners -10.5

2️⃣ Tu peux combiner si les données le justifient :
- Résultat principal + total de buts
- Résultat principal + total de corners
- Double chance + total de buts

3️⃣ Justifie la prédiction de manière détaillée : tactique, forme récente, H2H, joueurs clés, cotes.

4️⃣ Fournis **une partie JSON stricte** à la fin :
- `prediction_textuelle` : la prédiction humaine complète
- `confidence` : entier 0–100 reflétant la fiabilité
⚠️ Important : La partie JSON doit **uniquement contenir** `prediction_textuelle` et `confidence`.

Exemple attendu :
{{
    "prediction_textuelle": "Victoire probable de {match['team1']}",
    "confidence": 87
}}

Données du match :
{json.dumps(match, indent=2, ensure_ascii=False)}
"""

def call_gpt_oss(prompt):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": (
                "Tu es un expert en analyse football, orienté data science et pronostics. "
                "Tes réponses doivent être professionnelles, détaillées, structurées et exploitables."
            )},
            {"role": "user", "content": prompt}
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS
    }

    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=120)
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                raise Exception(f"❌ Erreur API ({response.status_code}) : {response.text}")
        except Exception as e:
            retries += 1
            print(f"{e}\n🔄 Tentative {retries}/{MAX_RETRIES} dans {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

    raise Exception("❌ Échec répété de l'API après plusieurs tentatives.")

def extract_json_from_response(text):
    match = re.search(r"\{(?:.|\s)*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None

def main():
    if not API_KEY:
        raise ValueError("❌ La clé API GROQ1 n’est pas définie dans l’environnement.")

    print("📂 Chargement des matchs...")
    games = load_json(INPUT_FILE)

    results = []
    today = datetime.now().strftime("%Y-%m-%d")
    output_file = os.path.join(OUTPUT_DIR, f"games-{today}.json")

    for i, match in enumerate(games, start=1):
        print(f"\n⚽ Analyse du match {i}/{len(games)} : {match.get('team1')} vs {match.get('team2')}")

        prompt = build_structured_prompt(match)

        try:
            analysis_text = call_gpt_oss(prompt)
        except Exception as e:
            print(e)
            analysis_text = "Analyse indisponible (erreur API)."

        enriched_match = dict(match)
        enriched_match["Analyse"] = analysis_text

        prediction_json = extract_json_from_response(analysis_text)
        if prediction_json:
            prediction_json["model_id"] = MODEL_ID
            enriched_match["Prediction_JSON"] = prediction_json
        else:
            enriched_match["Prediction_JSON"] = {"error": "JSON non trouvé", "model_id": MODEL_ID}

        results.append(enriched_match)

    print(f"\n📝 Sauvegarde des prédictions dans : {output_file}")
    save_json(output_file, results)

    print("====================================")
    print("✅ ANALYSES GÉNÉRÉES AVEC SUCCÈS")
    print(f"📊 Matchs traités : {len(results)}")
    print(f"🧠 Modèle utilisé : {MODEL_ID}")
    print(f"🧾 Max tokens : {MAX_TOKENS}")
    print("====================================")

if __name__ == "__main__":
    main()