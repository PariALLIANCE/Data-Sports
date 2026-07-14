# 🏆 Data-Sports

> **Une base de données complète des matchs de football historiques avec des helpers pour accéder facilement aux derniers résultats par ligue.**

[![npm version](https://img.shields.io/npm/v/@jonnhy225/sports-data)](https://www.npmjs.com/package/@jonnhy225/sports-data)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📋 Table des matières

- [À propos](#-à-propos)
- [Caractéristiques](#-caractéristiques)
- [Installation](#-installation)
- [Utilisation](#-utilisation)
- [Structure des données](#-structure-des-données)
- [Ligues disponibles](#-ligues-disponibles)
- [API](#-api)
- [Contribution](#-contribution)
- [Licence](#-licence)

---

## 🎯 À propos

**Data-Sports** est un package NPM qui fournit un accès facile à une vaste collection de données de matchs de football. Parfait pour :

- 🔍 Analyser les résultats historiques
- 📊 Développer des applications de prédiction sportive
- 📱 Créer des dashboards et statistiques
- 🤖 Entraîner des modèles de machine learning
- 🎲 Construire des applications de paris sportifs

---

## ✨ Caractéristiques

✅ **43+ ligues mondiales** - Premier League, La Liga, Bundesliga, Serie A, Ligue 1, etc.

✅ **Données historiques complètes** - Matchs, scores, dates, équipes

✅ **API simple** - Accès facile aux derniers matchs d'une ligue

✅ **Pas de dépendances externes** - Léger et rapide

✅ **Format JSON** - Facile à intégrer dans n'importe quel projet

✅ **Type module ES6** - Utilisable avec import/export moderne

---

## 📦 Installation

```bash
npm install @jonnhy225/sports-data
```

ou avec yarn :

```bash
yarn add @jonnhy225/sports-data
```

---

## 🚀 Utilisation

### Importer la librairie

```javascript
import { LEAGUES, getLastMatches } from '@jonnhy225/sports-data';
```

### Récupérer les 15 derniers matchs d'une ligue

```javascript
// Derniers matchs de la Premier League anglaise
const lastMatches = getLastMatches('England_Premier_League');
console.log(lastMatches);
```

**Résultat :**

```json
[
  {
    "gameId": "641856",
    "date": "Friday, February 10, 2023",
    "team1": "Manchester United",
    "team2": "Arsenal",
    "score": "2 - 1",
    "title": "Manchester United VS Arsenal",
    "match_url": "https://www.espn.com/soccer/match/_/gameId/641856/...",
    "stats": {}
  }
]
```

### Personnaliser le nombre de matchs

```javascript
// Récupérer les 5 derniers matchs
const lastFive = getLastMatches('France_Ligue_1', { limit: 5 });
```

### Exclure les statistiques

```javascript
// Récupérer les matchs sans les stats
const matchesNoStats = getLastMatches('Germany_Bundesliga', { includeStats: false });
```

### Lister toutes les ligues disponibles

```javascript
import { LEAGUES } from '@jonnhy225/sports-data';

Object.keys(LEAGUES).forEach(league => {
  console.log(league);
});
```

---

## 📊 Structure des données

Chaque match contient les informations suivantes :

```javascript
{
  gameId: "641856",                    // ID unique du match
  date: "Friday, February 10, 2023",   // Date du match
  team1: "Manchester United",          // Équipe 1
  team2: "Arsenal",                    // Équipe 2
  score: "2 - 1",                      // Score final
  title: "Manchester United VS Arsenal", // Titre du match
  match_url: "https://...",            // Lien vers le match sur ESPN
  stats: {}                            // Statistiques détaillées
}
```

---

## ⚽ Ligues disponibles

### 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Angleterre
- `England_Premier_League` - Premier League
- `England_National_League` - National League

### 🇪🇸 Espagne
- `Spain_Laliga` - La Liga

### 🇩🇪 Allemagne
- `Germany_Bundesliga` - Bundesliga

### 🇮🇹 Italie
- `Italy_Serie_A` - Serie A

### 🇫🇷 France
- `France_Ligue_1` - Ligue 1

### 🇵🇹 Portugal
- `Portugal_Primeira_Liga` - Primeira Liga

### 🇳🇱 Pays-Bas
- `Netherlands_Eredivisie` - Eredivisie

### 🇧🇷 Brésil
- `Brazil_Serie_A` - Série A
- `Brazil_Serie_B` - Série B

### 🇲🇽 Mexique
- `Mexico_Liga_MX` - Liga MX

### 🇺🇸 États-Unis
- `USA_Major_League_Soccer` - MLS

### 🇯🇵 Japon
- `Japan_J1_League` - J1 League

### 🇦🇷 Argentine
- `Argentina_Primera_Nacional` - Primera Nacional

### 🇦🇹 Autriche
- `Austria_Bundesliga` - Bundesliga

### 🇧🇪 Belgique
- `Belgium_Jupiler_Pro_League` - Jupiler Pro League

### 🇨🇱 Chili
- `Chile_Primera_Division` - Primera División

### 🇨🇳 Chine
- `China_Super_League` - Super League

### 🇨🇴 Colombie
- `Colombia_Primera_A` - Primera A

### 🇬🇷 Grèce
- `Greece_Super_League_1` - Super League 1

### 🇵🇾 Paraguay
- `Paraguay_Division_Profesional` - División Profesional

### 🇵🇪 Pérou
- `Peru_Primera_Division` - Primera División

### 🇷🇴 Roumanie
- `Romania_Liga_I` - Liga I

### 🇷🇺 Russie
- `Russia_Premier_League` - Premier League

### 🇸🇦 Arabie Saoudite
- `Saudi_Arabia_Pro_League` - Pro League

### 🇸🇪 Suède
- `Sweden_Allsvenskan` - Allsvenskan

### 🇨🇭 Suisse
- `Switzerland_Super_League` - Super League

### 🇹🇷 Turquie
- `Turkey_Super_Lig` - Super Lig

### 🇻🇪 Venezuela
- `Venezuela_Primera_Division` - Primera División

### 🏆 Compétitions internationales
- `UEFA_Champions_League` - Ligue des Champions
- `UEFA_Europa_League` - Ligue Europa
- `FIFA_Club_World_Cup` - Coupe du Monde des Clubs

---

## 🔧 API

### `getLastMatches(leagueKey, options)`

Récupère les derniers matchs joués d'une ligue.

**Paramètres :**

| Paramètre | Type | Par défaut | Description |
|-----------|------|-----------|-------------|
| `leagueKey` | `string` | **Obligatoire** | Clé de la ligue (voir liste ci-dessus) |
| `options` | `object` | `{}` | Options supplémentaires |
| `options.limit` | `number` | `15` | Nombre de matchs à retourner |
| `options.includeStats` | `boolean` | `true` | Inclure les statistiques détaillées |

**Exemples :**

```javascript
// Défaut : 15 derniers matchs avec stats
getLastMatches('England_Premier_League');

// 10 derniers matchs
getLastMatches('Spain_Laliga', { limit: 10 });

// 20 matchs sans stats
getLastMatches('Germany_Bundesliga', { limit: 20, includeStats: false });
```

---

## 📝 Exemples pratiques

### Exemple 1 : Afficher les résultats récents

```javascript
import { getLastMatches } from '@jonnhy225/sports-data';

const matches = getLastMatches('England_Premier_League', { limit: 5 });

matches.forEach(match => {
  console.log(`${match.title}: ${match.score}`);
});
```

### Exemple 2 : Analyser les scores

```javascript
import { getLastMatches } from '@jonnhy225/sports-data';

const matches = getLastMatches('France_Ligue_1');

const highScoringMatches = matches.filter(match => {
  const [score1, score2] = match.score.split(' - ').map(Number);
  return (score1 + score2) > 3;
});

console.log(`Matchs à plus de 3 buts : ${highScoringMatches.length}`);
```

### Exemple 3 : Comparer plusieurs ligues

```javascript
import { getLastMatches, LEAGUES } from '@jonnhy225/sports-data';

const topLeagues = ['England_Premier_League', 'Spain_Laliga', 'Germany_Bundesliga'];

topLeagues.forEach(league => {
  const matches = getLastMatches(league, { limit: 1 });
  console.log(`${league}: ${matches[0].title}`);
});
```

---

## 🤝 Contribution

Les contributions sont les bienvenues ! 🎉

**Pour contribuer :**

1. Fork le repository
2. Créez une branche (`git checkout -b feature/AmazingFeature`)
3. Commitez vos changements (`git commit -m 'Add AmazingFeature'`)
4. Poussez vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une Pull Request

---

## 🐛 Signaler un bug

Si vous trouvez un bug, veuillez ouvrir une [issue](https://github.com/PariALLIANCE/Data-Sports/issues) avec :

- Une description claire du problème
- Les étapes pour reproduire le bug
- Le comportement attendu vs réel

---

## 📄 Licence

Ce projet est sous licence **MIT**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## 👨‍💻 Auteur

**Jonnhy Billions**

- GitHub: [@jonnhy225](https://github.com/jonnhy225)
- NPM: [@jonnhy225/sports-data](https://www.npmjs.com/package/@jonnhy225/sports-data)

---

## 📞 Support

Besoin d'aide ? 

- 📖 Consultez la [documentation](https://github.com/PariALLIANCE/Data-Sports#readme)
- 🐛 Ouvrez une [issue](https://github.com/PariALLIANCE/Data-Sports/issues)
- 💬 Rejoignez les discussions

---

<div align="center">

**Fait avec ❤️ par [PariALLIANCE](https://github.com/PariALLIANCE)**

[⬆ Retour en haut](#-data-sports)

</div>
