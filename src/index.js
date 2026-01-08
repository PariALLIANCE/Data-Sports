// data/football/leagues/index.js

import fs from "fs";
import path from "path";

/**
 * Registre minimal des ligues
 */
export const LEAGUES = {
  England_Premier_League: "England_Premier_League.json",
  Spain_Laliga: "Spain_Laliga.json",
  Germany_Bundesliga: "Germany_Bundesliga.json",
  Argentina_Primera_Nacional: "Argentina_Primera_Nacional.json",
  Austria_Bundesliga: "Austria_Bundesliga.json",
  Belgium_Jupiler_Pro_League: "Belgium_Jupiler_Pro_League.json",
  Brazil_Serie_A: "Brazil_Serie_A.json",
  Brazil_Serie_B: "Brazil_Serie_B.json",
  Chile_Primera_Division: "Chile_Primera_Division.json",
  China_Super_League: "China_Super_League.json",
  Colombia_Primera_A: "Colombia_Primera_A.json",
  England_National_League: "England_National_League.json",
  France_Ligue_1: "France_Ligue_1.json",
  Greece_Super_League_1: "Greece_Super_League_1.json",
  Italy_Serie_A: "Italy_Serie_A.json",
  Japan_J1_League: "Japan_J1_League.json",
  Mexico_Liga_MX: "Mexico_Liga_MX.json",
  Netherlands_Eredivisie: "Netherlands_Eredivisie.json",
  Paraguay_Division_Profesional: "Paraguay_Division_Profesional.json",
  Peru_Primera_Division: "Peru_Primera_Division.json",
  Portugal_Primeira_Liga: "Portugal_Primeira_Liga.json",
  Romania_Liga_I: "Romania_Liga_I.json",
  Russia_Premier_League: "Russia_Premier_League.json",
  Saudi_Arabia_Pro_League: "Saudi_Arabia_Pro_League.json",
  Sweden_Allsvenskan: "Sweden_Allsvenskan.json",
  Switzerland_Super_League: "Switzerland_Super_League.json",
  Turkey_Super_Lig: "Turkey_Super_Lig.json",
  USA_Major_League_Soccer: "USA_Major_League_Soccer.json",
  Venezuela_Primera_Division: "Venezuela_Primera_Division.json",
  UEFA_Champions_League: "UEFA_Champions_League.json",
  UEFA_Europa_League: "UEFA_Europa_League.json",
  FIFA_Club_World_Cup: "FIFA_Club_World_Cup.json"
};

const BASE_PATH = "data/football/leagues";

/**
 * Retourne les 15 derniers matchs joués d'une ligue
 */
export function getLastMatches(
  leagueKey,
  { limit = 15, includeStats = true } = {}
) {
  const file = LEAGUES[leagueKey];
  if (!file) throw new Error("Ligue inconnue");

  const filePath = path.join(BASE_PATH, file);
  const data = JSON.parse(fs.readFileSync(filePath, "utf-8"));

  const playedMatches = data
    .filter(
      m =>
        m.score &&
        m.score !== "-" &&
        !m.score.toLowerCase().includes("vs")
    )
    .slice(-limit);

  if (includeStats) return playedMatches;

  return playedMatches.map(({ stats, ...rest }) => rest);
}