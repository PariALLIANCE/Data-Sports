import os
import json

# 📁 Chemin vers ton dossier cloné GitHub
BASE_DIR = "data/football/leagues"  # adapte si besoin

with_stats = []
without_stats = []

def process_file(filepath):
    global with_stats, without_stats
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            if isinstance(data, list):
                for match in data:
                    stats = match.get("stats", {})
                    
                    if stats and isinstance(stats, dict) and len(stats) > 0:
                        with_stats.append(match)
                    else:
                        without_stats.append(match)

    except Exception as e:
        print(f"Erreur avec {filepath}: {e}")


# 🔄 Parcours récursif de tous les fichiers
for root, dirs, files in os.walk(BASE_DIR):
    for file in files:
        if file.endswith(".json"):
            full_path = os.path.join(root, file)
            process_file(full_path)


# 💾 Sauvegarde des résultats
with open("data-with-stats.json", "w", encoding="utf-8") as f:
    json.dump(with_stats, f, ensure_ascii=False, indent=2)

with open("data-without-stats.json", "w", encoding="utf-8") as f:
    json.dump(without_stats, f, ensure_ascii=False, indent=2)


# 📊 Résumé
print("Terminé ✅")
print(f"Matchs avec stats: {len(with_stats)}")
print(f"Matchs sans stats: {len(without_stats)}")