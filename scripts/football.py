import os
import json
import requests
from datetime import datetime
import re
import time

# ================== CONFIG ==================

API_KEY_1 = os.getenv("GROQ1")
API_KEY_2 = os.getenv("GROQ2")

MODEL_ID = "openai/gpt-oss-120b"

INPUT_FILE = "data/football/games_of_day.json"
OUTPUT_DIR = "data/football/predictions"

MAX_TOKENS = 4000
TEMPERATURE = 0.4
RETRY_DELAY = 5
MAX_RETRIES = 15

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


# ===================== NOUVEAU PROMPT STRUCTURÉ =====================

def build_structured_prompt(match):
    return f"""
Tu es un analyste football professionnel spécialisé dans les pronostics sportifs.  
Analyse ce match en profondeur à partir de toutes les données disponibles, en traitant chaque facteur séparément avant de les regrouper :

- Forme récente des équipes (analyse séparée)
- Confrontations directes (H2H) (analyse séparée)
- Statistiques clés et tendances (analyse séparée)
- Impact des joueurs clés (analyse séparée)
- Cotes et probabilités implicites (analyse séparée)
- Classements détaillés (analyse séparée)

Tâches à réaliser :

1️⃣ Analyse chaque donnée individuellement et explique son impact sur le match.  

2️⃣ Regroupe ensuite ces analyses pour produire une seule prédiction finale parmi les options suivantes  
(⚠️ aucune combinaison n’est autorisée) :

- Victoire {match['team1']}
- Victoire {match['team2']}
- Victoire {match['team1']} ou Nul
- Victoire {match['team2']} ou Nul
- Total +2.5 buts
- Total -3.5 buts
- Les deux équipes marquent Oui
- Les deux équipes marquent Non
- Total corners +7.5
- Total corners -10.5

3️⃣ Justifie la prédiction finale de manière détaillée :  
tactique, forme récente, H2H, joueurs clés, cotes(assez importants), facteurs domicile/extérieur(des matchs passés +confrontations historiques), classement.

4️⃣ Fournis une partie JSON stricte à la fin :

- prediction_textuelle : la prédiction humaine complète  
- confidence : entier 0–96 reflétant la fiabilité  

⚠️ Règles pour le confidence :
- Ne jamais dépasser 96  
- 40–55 : données contradictoires ou incertaines  
- 56–70 : tendance claire mais pas garantie  
- 71–85 : forte probabilité basée sur plusieurs facteurs convergents  
- 86–96 : quasi-certitude (jamais 100)

Exemple attendu :
{{
  "prediction_textuelle": "Victoire probable de {match['team1']}",
  "confidence": 56
}}

Données du match :
{json.dumps(match, indent=2, ensure_ascii=False)}
"""


# ===================== Appel API GROQ (alternance clés) =====================

api_toggle = 0  # 0 = GROQ1, 1 = GROQ2


def call_gpt_oss(prompt):
    global api_toggle

    api_key = API_KEY_1 if api_toggle == 0 else API_KEY_2
    api_toggle = 1 - api_toggle

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL_ID,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Tu es un expert en analyse football orienté data science et pronostics et gestion financière. "
                    "Analyse rigoureuse(par énumération pas de tableau ), raisonnement structuré, aucune combinaison interdite, "
                    "JSON final strict et exploitable."
                )
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS
    }

    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.post(
                GROQ_URL,
                headers=headers,
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]

            raise Exception(f"❌ Erreur API {response.status_code} : {response.text}")

        except Exception as e:
            retries += 1
            print(f"{e}\n🔄 Tentative {retries}/{MAX_RETRIES} dans {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

    raise Exception("❌ Échec API après plusieurs tentatives.")


# ===================== Extraction JSON stricte =====================

def extract_json_from_response(text):
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None

    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


# ===================== MAIN =====================

def main():
    if not API_KEY_1 or not API_KEY_2:
        raise ValueError("❌ Les clés GROQ1 et GROQ2 doivent être définies.")

    print("📂 Chargement des matchs...")
    games = load_json(INPUT_FILE)

    results = []
    today = datetime.now().strftime("%Y-%m-%d")
    output_file = os.path.join(OUTPUT_DIR, f"games-{today}.json")

    for i, match in enumerate(games, start=1):
        print(f"\n⚽ Match {i}/{len(games)} : {match.get('team1')} vs {match.get('team2')}")

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
            enriched_match["Prediction_JSON"] = {
                "error": "JSON non extrait",
                "model_id": MODEL_ID
            }

        results.append(enriched_match)

    print(f"\n📝 Sauvegarde : {output_file}")
    save_json(output_file, results)

    print("====================================")
    print("✅ ANALYSES TERMINÉES")
    print(f"📊 Matchs traités : {len(results)}")
    print(f"🧠 Modèle : {MODEL_ID}")
    print("====================================")


if __name__ == "__main__":
    main()