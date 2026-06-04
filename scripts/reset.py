import json
import os

OUTPUT_DIR = "data/football/leagues"

JOURNEE_FIELDS = {"journee", "saison_offset", "saison", "saison_terminee"}

def reset_journees():
    files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".json")]

    for filename in sorted(files):
        path = os.path.join(OUTPUT_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                matches = json.load(f)
        except Exception as e:
            print(f"⚠️  Lecture échouée : {filename} → {e}")
            continue

        changed = 0
        cleaned = []
        for m in matches:
            original_keys = set(m.keys())
            for field in JOURNEE_FIELDS:
                m.pop(field, None)
            if set(m.keys()) != original_keys:
                changed += 1
            cleaned.append(m)

        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)

        print(f"  ✅ {filename} : {changed}/{len(cleaned)} matchs nettoyés")

    print("\n✅ Reset journées terminé.")

if __name__ == "__main__":
    reset_journees()