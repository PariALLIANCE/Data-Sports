import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import re


def extract_team_full_name(href):
    """
    Extrait le nom complet de l'équipe depuis un lien href
    Exemple: /nhl/team/_/name/bos/boston-bruins -> Boston Bruins
    """
    if not href:
        return ""

    # Format: /nhl/team/_/name/ABBR/full-team-name
    match = re.search(r'/nhl/team/_/name/[^/]+/(.+)$', href)
    if match:
        team_slug = match.group(1)
        # Convertir le slug en nom (remplacer tirets par espaces et capitaliser)
        team_name = team_slug.replace('-', ' ').title()
        return team_name
    return ""


def scrape_nhl_games_today():
    """
    Scrape les matchs NHL du jour depuis ESPN et sauvegarde dans un fichier JSON.
    Ne garde QUE les matchs qui n'ont pas encore été joués.
    Écrase toujours le fichier JSON existant, même s'il n'y a aucun match.
    Retourne le chemin du fichier créé ou None en cas d'erreur.
    """

    # Date du jour
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    date_formatted = today.strftime("%Y-%m-%d")

    # Formater la date en jour de la semaine en anglais
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    months = ["", "January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]

    target_date = f"{weekdays[today.weekday()]}, {months[today.month]} {today.day}, {today.year}"

    # URL ESPN avec la date du jour
    url = f"https://www.espn.com/nhl/schedule/_/date/{date_str}"

    print(f"🏒 Récupération des matchs NHL pour le {today.strftime('%d/%m/%Y')}...")
    print(f"📅 Date cible: {target_date}")
    print(f"🌐 URL: {url}")

    # Headers pour simuler un navigateur
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    # Déterminer le répertoire de base (racine du projet)
    # Si on est dans GitHub Actions, GITHUB_WORKSPACE est défini
    # Sinon, on utilise le répertoire courant
    base_dir = os.environ.get('GITHUB_WORKSPACE', os.getcwd())
    
    # Créer le chemin absolu pour le dossier de destination
    output_dir = os.path.join(base_dir, "data", "hockey")
    
    print(f"📂 Répertoire de base: {base_dir}")
    print(f"📁 Dossier de destination: {output_dir}")
    
    # Créer le dossier de destination si nécessaire (avant toute opération)
    os.makedirs(output_dir, exist_ok=True)
    print(f"✅ Dossier créé/vérifié: {output_dir}")
    
    output_file = os.path.join(output_dir, "games_of_days_nhl.json")
    print(f"📄 Fichier de sortie: {output_file}")

    # Initialiser la liste des matchs (vide par défaut)
    games_data = []

    try:
        # Requête HTTP
        print("📡 Envoi de la requête HTTP...")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        print(f"✅ Réponse reçue: {response.status_code}")

        # Parser le HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Trouver tous les blocs de tables avec leur titre de date
        schedule_blocks = soup.find_all('div', class_='ScheduleTables')

        print(f"📊 {len(schedule_blocks)} blocs de planning trouvés")

        for block in schedule_blocks:
            # Vérifier le titre de la date
            title_elem = block.find('div', class_='Table__Title')
            if not title_elem:
                continue

            date_title = title_elem.get_text(strip=True)

            # Ne traiter que les matchs du jour ciblé
            if target_date not in date_title:
                continue

            print(f"\n✅ Section trouvée: {date_title}")

            # Trouver les tables dans ce bloc
            tables = block.find_all('table', class_='Table')

            for table in tables:
                # Vérifier si c'est une table avec des matchs à venir (pas de résultats)
                thead = table.find('thead')
                if not thead:
                    continue

                # FILTRE CRITIQUE: Chercher les en-têtes pour distinguer matchs à venir vs matchs terminés
                th_elements = thead.find_all('th')
                headers_text = ' '.join([th.get_text().upper() for th in th_elements])

                # Si on trouve "RESULT" ou "TOP PLAYER" ou "WINNING GOALIE", c'est une table de résultats
                if any(keyword in headers_text for keyword in ['RESULT', 'TOP PLAYER', 'WINNING GOALIE', 'ATT']):
                    print("⏭️  Table de résultats ignorée (matchs déjà joués)")
                    continue

                # Si on ne trouve pas "TIME", ce n'est pas une table de matchs à venir
                if 'TIME' not in headers_text:
                    print("⏭️  Table sans horaires ignorée")
                    continue

                print("📋 Traitement de la table des matchs à venir...")

                # Parser les lignes de matchs
                tbody = table.find('tbody')
                if not tbody:
                    continue

                rows = tbody.find_all('tr', class_='Table__TR')
                print(f"🔍 {len(rows)} lignes trouvées")

                for row in rows:
                    try:
                        # Extraire la cellule des matchs
                        events_col = row.find('td', class_='events__col')
                        colspan_col = row.find('td', class_='colspan__col')

                        if not events_col or not colspan_col:
                            continue

                        # Équipe visiteuse (away)
                        away_links = events_col.find_all('a', class_='AnchorLink')
                        away_team_name = ""
                        away_team_abbr = ""
                        away_logo_url = ""

                        for link in away_links:
                            href = link.get('href', '')
                            if '/nhl/team/' in href:
                                # Extraire le nom complet depuis le href
                                full_name = extract_team_full_name(href)
                                if full_name:
                                    away_team_name = full_name

                            # Récupérer l'abréviation aussi
                            text = link.get_text(strip=True)
                            if text and len(text) <= 4:
                                away_team_abbr = text

                            # Logo
                            img = link.find('img', class_='Logo')
                            if img and 'src' in img.attrs:
                                full_url = img['src']
                                if 'img=/i/teamlogos' in full_url:
                                    logo_match = re.search(r'img=(/i/teamlogos/nhl/500/[^&]+)', full_url)
                                    if logo_match:
                                        away_logo_url = f"https://a.espncdn.com{logo_match.group(1)}"
                                else:
                                    away_logo_url = full_url

                        # Équipe domicile (home)
                        home_links = colspan_col.find_all('a', class_='AnchorLink')
                        home_team_name = ""
                        home_team_abbr = ""
                        home_logo_url = ""

                        for link in home_links:
                            href = link.get('href', '')
                            if '/nhl/team/' in href:
                                # Extraire le nom complet depuis le href
                                full_name = extract_team_full_name(href)
                                if full_name:
                                    home_team_name = full_name

                            # Récupérer l'abréviation aussi
                            text = link.get_text(strip=True)
                            if text and len(text) <= 4:
                                home_team_abbr = text

                            # Logo
                            img = link.find('img', class_='Logo')
                            if img and 'src' in img.attrs:
                                full_url = img['src']
                                if 'img=/i/teamlogos' in full_url:
                                    logo_match = re.search(r'img=(/i/teamlogos/nhl/500/[^&]+)', full_url)
                                    if logo_match:
                                        home_logo_url = f"https://a.espncdn.com{logo_match.group(1)}"
                                else:
                                    home_logo_url = full_url

                        if not away_team_name or not home_team_name:
                            continue

                        # Heure du match
                        time_col = row.find('td', class_='date__col')
                        if not time_col:
                            continue

                        time_link = time_col.find('a')
                        if not time_link:
                            continue

                        time_text = time_link.get_text(strip=True)

                        # Game ID (depuis le lien)
                        game_link = time_link.get('href', '')
                        game_id = ""
                        if '/gameId/' in game_link:
                            game_id_match = re.search(r'/gameId/(\d+)/', game_link)
                            if game_id_match:
                                game_id = game_id_match.group(1)

                        # Créer l'objet match avec noms complets
                        game = {
                            "game_id": game_id,
                            "date": date_formatted,
                            "time": time_text,
                            "away_team": {
                                "name": away_team_name,
                                "abbreviation": away_team_abbr,
                                "logo_url": away_logo_url
                            },
                            "home_team": {
                                "name": home_team_name,
                                "abbreviation": home_team_abbr,
                                "logo_url": home_logo_url
                            }
                        }

                        games_data.append(game)
                        print(f"   ✅ {away_team_name} @ {home_team_name} à {time_text} (ID: {game_id})")

                    except Exception as e:
                        print(f"   ⚠️  Erreur lors du parsing d'une ligne: {e}")
                        continue

    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de la requête HTTP: {e}")
        print("💡 Vérifiez votre connexion Internet ou les paramètres réseau")
        # On continue quand même pour sauvegarder un JSON vide
        print("📝 Sauvegarde d'un fichier JSON vide malgré l'erreur...")

    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        # On continue quand même pour sauvegarder un JSON vide
        print("📝 Sauvegarde d'un fichier JSON vide malgré l'erreur...")

    # TOUJOURS sauvegarder le fichier JSON, même s'il est vide ou en cas d'erreur
    try:
        result = {
            "date": date_formatted,
            "total_games": len(games_data),
            "games": games_data,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        print(f"\n💾 Tentative de sauvegarde dans: {output_file}")
        
        # Vérifier que le dossier existe bien avant d'écrire
        if not os.path.exists(output_dir):
            print(f"⚠️  Le dossier n'existe pas, recréation...")
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        # Vérifier que le fichier a bien été créé
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"✅ Fichier sauvegardé avec succès ({file_size} octets)")
        else:
            print(f"❌ Le fichier n'a pas été créé!")
            return None

        if len(games_data) > 0:
            print(f"\n🎉 {len(games_data)} matchs à venir sauvegardés dans: {output_file}")
        else:
            print(f"\n📭 Aucun match à venir trouvé. Fichier JSON vide créé: {output_file}")

        return output_file

    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde du fichier JSON: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    output_file = scrape_nhl_games_today()

    if output_file:
        print("\n✨ Script terminé avec succès!")
        print(f"📁 Fichier créé/mis à jour: {output_file}")

        # Afficher le contenu du fichier pour vérification
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"\n📊 Résumé du fichier JSON:")
            print(f"   - Date: {data.get('date', 'N/A')}")
            print(f"   - Nombre de matchs: {data.get('total_games', 0)}")
            print(f"   - Dernière mise à jour: {data.get('last_updated', 'N/A')}")
        except Exception as e:
            print(f"⚠️  Impossible de lire le fichier pour vérification: {e}")
    else:
        print("\n❌ Le script a échoué")
        exit(1)
