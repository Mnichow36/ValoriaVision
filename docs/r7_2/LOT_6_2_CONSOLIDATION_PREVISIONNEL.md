# Lot 6.2 — Consolidation du Prévisionnel

## Objectif

Consolider le socle standard du Prévisionnel après validation du Lot 6.1, sans enrichissement du module Scénarios Premium.

## Périmètre

- cohérence Prudent / Réaliste / Optimiste dans Prévisionnel et Dashboard ;
- suppression des reliquats de filtrage des récurrences par scénario exclusif ;
- vérification de l'absence de scénarios personnalisés exposés en édition Free ;
- harmonisation des libellés et aides ;
- tests de non-régression du moteur prévisionnel ;
- recette courte avant passage au Lot 7 Rapprochements.

## Première correction

Le filtrage historique qui excluait certaines récurrences selon leur ancien champ scénario a été supprimé du moteur `forecast_events()`.

Désormais :
- toutes les récurrences standards appartiennent à la base commune ;
- les événements générés portent la portée technique `Tous` ;
- les différences Prudent / Réaliste / Optimiste proviennent uniquement du service d'hypothèses validé au Lot 6.1.

## Version

`V0.6.6-R7.2.4 Lot 6.2 Consolidation prévisionnel`

## Issue de suivi

#64

## Statut

**LOT 6.2 DÉMARRÉ.**
