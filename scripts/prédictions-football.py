import os
import json
from datetime import datetime
import time
import requests

# === CONFIG ===
INPUT_DIR = "data/football/predictions"
API_KEY = os.environ.get("Groq1")  # API GroqCloud
MODEL_ID = "openai/gpt-oss-120b"

# === UTILITAIRES ===
def get_today_filename():
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    return f"stats_football-{today_str}.json", f"prédictions-{today_str}.json"

def load_matches(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_predictions(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def query_model(match):
    """
    Envoie le match à GPT-OSS 120B pour analyse et prédiction.
    Une seule prédiction par match, analyse détaillée incluse.
    """
    prompt = f"""
    Analyse ce match de football et fais une seule prédiction :
    Match : {match['team1']} vs {match['team2']}
    Date : {match['date']}
    Ligue : {match['league']}
    Score actuel : {match.get('score', 'N/A')}
    
    Données disponibles :
    - Cotes moneyline : {match.get('odds', {}).get('moneyline', {})}
    - Meilleurs buteurs et passeurs : {match.get('odds', {}).get('key_players', {})}
    - Classement ligue : {match.get('league_standings', [])}
    - Forme récente des équipes : {match.get('recent_form', {})}
    
    En fonction des données, fais une prédiction réaliste sur :
    1. Vainqueur ou double chance (1X, 2X, etc.) selon la certitude
    2. Total de buts (+2.5, -3.5)
    3. Nombre de corners (+7.5, -10.5)
    4. Les combinaisons pertinentes (victoire + total, double chance + total, BTTS)
    
    Fournis également une analyse complète expliquant la prédiction.
    Répond en JSON de la forme :
    {{
      "prediction": "exemple",
      "confidence": "exemple",
      "explanation": "détail complet du raisonnement basé sur les données"
    }}
    """

    url = f"https://api.groq.com/openai/v1/responses"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_ID,
        "input": prompt,
        "max_output_tokens": 8192
    }

    while True:
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            # On récupère la sortie texte
            if "output" in data and len(data["output"]) > 0:
                text = data["output"][0].get("content", "")
                return json.loads(text)  # Transformer en dict
            else:
                raise ValueError("Réponse vide de l'API")
        except Exception as e:
            print(f"Erreur API, nouvelle tentative dans 5s : {e}")
            time.sleep(5)  # retry après 5 secondes

# === MAIN ===
def main():
    input_file, output_file = get_today_filename()
    input_path = os.path.join(INPUT_DIR, input_file)
    output_path = os.path.join(INPUT_DIR, output_file)

    if not os.path.exists(input_path):
        print(f"Fichier introuvable : {input_path}")
        return

    matches = load_matches(input_path)
    print(f"{len(matches)} matchs à analyser...")

    for idx, match in enumerate(matches):
        print(f"\nAnalyse du match {idx+1}/{len(matches)} : {match['team1']} vs {match['team2']}")
        prediction = query_model(match)
        match["prediction"] = prediction
        print(f"Prédiction ajoutée : {prediction.get('prediction')}")

    save_predictions(output_path, matches)
    print(f"\nToutes les prédictions sauvegardées dans : {output_path}")

if __name__ == "__main__":
    main()