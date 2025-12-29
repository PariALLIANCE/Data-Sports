import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

/* ===== Résolution chemins ESM ===== */
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/* ===== Dossiers ===== */
const leaguesDir = path.resolve(__dirname, '../data/football/leagues');
const leagueIdsPath = path.resolve(__dirname, '../data/football/league-ids.json');

/* ===== Utils ===== */
function readJSON(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
}

/* =========================================================
   1️⃣ Lister les ligues disponibles (nom + id ESPN)
   ========================================================= */
export function listLeagues() {
  if (!fs.existsSync(leagueIdsPath)) {
    throw new Error('league-ids.json introuvable');
  }

  const leagueIds = readJSON(leagueIdsPath);

  return Object.entries(leagueIds).map(([name, data]) => ({
    name,
    id: data.id
  }));
}

/* =========================================================
   2️⃣ Récupérer les N derniers matchs d’une ligue
      ⚠️ Ici on suppose que le serveur connaît le mapping
      entre id et fichier JSON réel côté serveur.
   ========================================================= */
export function getLastMatches(leagueId, n = 5) {
  // Mapping interne côté serveur
  const leagueFiles = {
    'eng.1': 'England_Premier_League.json',
    'esp.1': 'Spain_Laliga.json',
    'ger.1': 'bundesliga.json',
    'arg.2': 'Argentina_Primera_Nacional.json',
    'aut.1': 'Austria_Bundesliga.json',
    'bel.1': 'Belgium_Jupiler_Pro_League.json',
    'bra.1': 'Brazil_Serie_A.json',
    'bra.2': 'Brazil_Serie_B.json',
    'chi.1': 'Chile_Primera_Division.json',
    'chn.1': 'China_Super_League.json',
    'col.1': 'Colombia_Primera_A.json',
    'eng.5': 'England_National_League.json',
    'fra.1': 'France_Ligue_1.json',
    'gre.1': 'Greece_Super_League_1.json',
    'ita.1': 'Italy_Serie_A.json',
    'jpn.1': 'Japan_J1_League.json',
    'mex.1': 'Mexico_Liga_MX.json',
    'ned.1': 'Netherlands_Eredivisie.json',
    'par.1': 'Paraguay_Division_Profesional.json',
    'per.1': 'Peru_Primera_Division.json',
    'por.1': 'Portugal_Primeira_Liga.json',
    'rou.1': 'Romania_Liga_I.json',
    'rus.1': 'Russia_Premier_League.json',
    'ksa.1': 'Saudi_Arabia_Pro_League.json',
    'swe.1': 'Sweden_Allsvenskan.json',
    'sui.1': 'Switzerland_Super_League.json',
    'tur.1': 'Turkey_Super_Lig.json',
    'usa.1': 'USA_Major_League_Soccer.json',
    'ven.1': 'Venezuela_Primera_Division.json',
    'uefa.champions': 'UEFA_Champions_League.json',
    'uefa.europa': 'UEFA_Europa_League.json',
    'fifa.cwc': 'FIFA_Club_World_Cup.json'
  };

  const fileName = leagueFiles[leagueId];
  if (!fileName) {
    throw new Error(`Aucun fichier trouvé pour l'id ${leagueId}`);
  }

  const filePath = path.join(leaguesDir, fileName);
  if (!fs.existsSync(filePath)) {
    throw new Error(`Fichier JSON introuvable côté serveur : ${fileName}`);
  }

  const matches = readJSON(filePath);
  if (!Array.isArray(matches)) {
    throw new Error('Format JSON invalide (attendu: tableau)');
  }

  return matches.slice(-n).reverse(); // les derniers n matchs
}

/* =========================================================
   🔧 Test direct en CLI
   ========================================================= */
if (process.argv[1] === __filename) {
  console.log('\n📋 Ligues disponibles :');
  console.table(listLeagues());

  console.log('\n⚽ 3 derniers matchs – Premier League');
  console.table(getLastMatches('eng.1', 3));
}
