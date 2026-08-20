# Valoria Vision V0.6.6-R7.2.2 — Changelog

## Objectif

Fiabiliser la chaîne critique : import bancaire réel → transactions → prévisionnel → rapprochement.

## Lot A — Import bancaire réel

- Ajout d'une architecture d'import extensible : modèles normalisés, détection CSV, profils bancaires, parseur CSV robuste.
- Ajout du profil **Société Générale CSV**.
- Détection de l'encodage `cp1252` / `latin-1` / `utf-8-sig`.
- Détection du séparateur `;`, `,` ou tabulation.
- Recherche de la vraie ligne d'en-tête au lieu de supposer la première ligne.
- Gestion des lignes techniques et lignes vides avant l'en-tête.
- Normalisation des dates françaises et montants français à virgule décimale.
- Conservation de la devise, du détail, de la ligne source, du profil source et du payload source utile au diagnostic.
- Diagnostic enrichi dans le volet import.
- Sélection de fichier visible immédiatement avant l'analyse.
- Maintien de la détection des doublons sur transaction normalisée.
- Maintien de la catégorisation automatique après import.

## Lot B — Rapprochement prévisionnel / réalisé

- Refactor du moteur pour construire un jeu complet de transactions et occurrences avant filtrage d'interface.
- Génération des occurrences pour tous les comptes actifs sur la période utile.
- Les transactions manuelles et importées sont éligibles au rapprochement.
- La vue active masque les éléments finalisés tout en les conservant dans l'historique par filtre.
- Suppression du statut métier ambigu `Confirmée` sans transaction réelle liée.
- Annulation par l'action **Annuler rapprochement**.
- Restauration des états après annulation : occurrence repasse en `Prévue` ou `En retard` selon sa date.
- Compteurs recalculés depuis la même source que les listes.
- Actions de ligne par menu contextuel clic droit.

## Données / migrations

- Schéma cible : `SCHEMA_VERSION = 14`.
- Ajout de colonnes de traçabilité import dans `transactions` et `import_batches`.
- Ajout de `match_type` dans `forecast_occurrences`.
- Migration non destructive de `planned_confirmed` vers un statut métier sûr.

## Limites volontairement conservées

- R7.2 ne promet pas de nouveau support bancaire au-delà du CSV robuste et du profil Société Générale.
- QIF/OFX/XLSX restent en non-régression historique, sans extension fonctionnelle majeure.
- Pas d'OCR PDF ni d'Open Banking.
