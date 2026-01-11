import os
import shutil

# Chemin racine du dépôt (le dossier courant)
ROOT_DIR = os.getcwd()
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")

# Créer le dossier scripts s'il n'existe pas
os.makedirs(SCRIPTS_DIR, exist_ok=True)

# Lister tous les fichiers à la racine
for file_name in os.listdir(ROOT_DIR):
    file_path = os.path.join(ROOT_DIR, file_name)

    # Déplacer uniquement les fichiers .py (sauf celui-ci si besoin)
    if file_name.endswith(".py") and file_name != "move_scripts.py":  # nom du script actuel
        dest_path = os.path.join(SCRIPTS_DIR, file_name)
        shutil.move(file_path, dest_path)
        print(f"✅ {file_name} déplacé vers {SCRIPTS_DIR}")