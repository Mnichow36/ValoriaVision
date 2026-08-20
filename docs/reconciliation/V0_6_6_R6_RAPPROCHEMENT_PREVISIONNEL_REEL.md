# V0.6.6-R6 — Rapprochement prévisionnel / réalisé

## Objectif

Ajouter un socle de rapprochement entre les occurrences prévisionnelles issues des récurrences et les transactions réelles importées.

## Fonctions incluses

- table `forecast_occurrences` ;
- génération d'occurrences depuis les récurrences ;
- service `ForecastReconciliationService` ;
- scoring compte / sens / montant / date / libellé / catégorie ;
- rapprochement automatique après import bancaire ;
- statut `À vérifier` pour les rapprochements probables ;
- statut `En retard` pour les occurrences dépassées sans réel ;
- écran `Rapprochements` ;
- actions utilisateur : confirmer, refuser, ignorer ;
- correction anti double comptage dans le prévisionnel pour les occurrences rapprochées.

## Validation rapide

1. Lancer `install.bat`, puis `run.bat`.
2. Vérifier le Dashboard.
3. Ouvrir `Rapprochements`.
4. Cliquer sur `Générer / mettre à jour`.
5. Importer une transaction correspondant à une récurrence.
6. Vérifier le statut `Rapprochée automatiquement` ou `À vérifier`.
7. Vérifier que le prévisionnel ne double pas prévu + réalisé.
