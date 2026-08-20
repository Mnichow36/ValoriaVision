# V0.6.6 — Catégories avec sens Recette / Dépense

## Objectif

Ajouter un sens métier aux catégories afin de ne plus obliger l'utilisateur à saisir des montants signés.

## Règle métier

- Catégorie de sens `Recette` : le montant manuel est automatiquement positif.
- Catégorie de sens `Dépense` : le montant manuel est automatiquement négatif.
- Catégorie de sens `Neutre` : le signe est conservé pour les transferts ou corrections.

## Écrans impactés

- Paramètres > Catégories : ajout de la colonne `Sens`.
- Transactions : saisie d'un montant positif, signe appliqué par la catégorie.
- Prévisionnel / Récurrences : saisie d'un montant positif, signe appliqué par la catégorie.
- Budgets : seules les catégories de sens Dépense et activées budget sont proposées.

## Imports bancaires

Les imports bancaires conservent les signes fournis par les fichiers des banques.
La règle de sens s'applique aux saisies manuelles et aux récurrences.
