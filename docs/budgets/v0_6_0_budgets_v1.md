# V0.6.0 — Budgets V1

## Objectif

Créer le premier vrai module Budgets de Valoria Vision.

## Inclus

- budgets mensuels par catégorie ;
- prévu / réalisé ;
- reste disponible ;
- taux d’utilisation ;
- alertes de dépassement ;
- seuils d’alerte par catégorie ;
- reprise automatique du mois précédent ;
- exclusions métier :
  - transferts internes ;
  - investissements ;
  - revenus.

## Règles métier

Réalisé budget = somme des transactions débitrices du mois rattachées à la catégorie.

Les catégories exclues des dépenses courantes ne sont pas intégrées :
- Transferts ;
- Investissement ;
- Revenus.

## Onglets

- Vue d’ensemble ;
- Catégories ;
- Alertes & règles.

## Non inclus

- budgets par compte ;
- budgets annuels ;
- enveloppes avancées ;
- graphiques premium dédiés.
