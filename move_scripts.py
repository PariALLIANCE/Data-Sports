name: Move Python Scripts to Folder

on:
  workflow_dispatch: # Permet de lancer manuellement

jobs:
  move-scripts:
    runs-on: ubuntu-latest

    steps:
      # 1️⃣ Checkout complet du dépôt
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      # 2️⃣ Setup Python
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      # 3️⃣ Exécuter le script de déplacement
      - name: Move Python scripts
        run: python move_scripts.py

      # 4️⃣ Commit & push des changements
      - name: Commit & push changes
        run: |
          git config --local user.name "github-actions[bot]"
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git add scripts/*.py
          git commit -m "📂 Déplacer les scripts Python dans scripts/" || echo "Rien à commit"
          git push origin main