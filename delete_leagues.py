#!/usr/bin/env python3
"""
Script pour supprimer tous les fichiers JSON du dossier data/football/leagues/
"""

import os
import subprocess
import sys

LEAGUES_DIR = "data/football/leagues"

def delete_json_files():
    """Supprime tous les fichiers JSON du dossier data/football/leagues/"""
    
    if not os.path.exists(LEAGUES_DIR):
        print(f"❌ Le dossier '{LEAGUES_DIR}' n'existe pas!")
        return False
    
    # Lister tous les fichiers JSON
    json_files = [f for f in os.listdir(LEAGUES_DIR) if f.endswith('.json')]
    
    if not json_files:
        print(f"⚠️ Aucun fichier JSON trouvé dans '{LEAGUES_DIR}'")
        return True
    
    print(f"📋 Fichiers à supprimer ({len(json_files)}):")
    for file in sorted(json_files):
        print(f"  - {file}")
    
    print(f"\n🗑️ Suppression de {len(json_files)} fichiers...")
    
    # Supprimer chaque fichier avec git
    for file in json_files:
        file_path = os.path.join(LEAGUES_DIR, file)
        try:
            subprocess.run(['git', 'rm', file_path], check=True, capture_output=True)
            print(f"  ✓ {file} supprimé")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Erreur lors de la suppression de {file}: {e}")
            return False
    
    # Commit les changements
    try:
        subprocess.run(
            ['git', 'config', 'user.email', 'action@github.com'],
            check=True,
            capture_output=True
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'GitHub Action'],
            check=True,
            capture_output=True
        )
        subprocess.run(
            ['git', 'commit', '-m', f'Delete all JSON files from {LEAGUES_DIR}'],
            check=True,
            capture_output=True
        )
        print(f"\n✅ Commit réalisé avec succès!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors du commit: {e}")
        return False
    
    # Push les changements
    try:
        subprocess.run(
            ['git', 'push', 'origin', 'HEAD'],
            check=True,
            capture_output=True
        )
        print(f"✅ Push réalisé avec succès!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors du push: {e}")
        return False

if __name__ == "__main__":
    success = delete_json_files()
    sys.exit(0 if success else 1)
