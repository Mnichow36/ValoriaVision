# V0.6.6 — Gestion des catégories

## Objectif

Ajouter une gestion centralisée des catégories dans Paramètres.

## Inclus

- onglet `Paramètres > Catégories` ;
- ajout d'une catégorie ;
- modification d'une catégorie ;
- suppression d'une catégorie ;
- type de catégorie : Dépense, Revenu, Neutre, Investissement, Épargne ;
- option `Disponible dans le module Budgets` ;
- répercussion des renommages dans :
  - transactions ;
  - récurrences ;
  - budgets ;
- suppression sécurisée : transactions/récurrences replacées en `À catégoriser`, budgets concernés retirés des budgets actifs.

## Impact Budget

Le module Budgets utilise maintenant les catégories actives de type Dépense et disponibles pour les budgets.

## Impact Transactions / Prévisionnel

Les listes déroulantes utilisent les catégories centralisées.
