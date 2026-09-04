# Valoria Vision V0.6.6-R7.2.4 - Rapprochements bêta

## Objet

Version de recette consacrée à la consolidation du périmètre Rapprochements après validation de l'issue #49 et mise en œuvre progressive de l'issue #82.

## Évolutions principales

- chargement exhaustif des transactions et occurrences avant filtres ;
- suppression de la troncature silencieuse à 500 lignes ;
- exclusion de la file active des transactions sans prévision candidate cohérente ;
- conservation intégrale de ces transactions dans le module Transactions et les calculs de réalisé ;
- création d'une zone Proposition de rapprochement avec score, raisons, écart et reste à couvrir ;
- validation ou rejet explicite des propositions ambiguës ;
- prise en charge des rapprochements multi-liens et partiels ;
- statut métier Partiellement rapprochée ;
- calcul du réalisé cumulé, du reste à couvrir et du dépassement ;
- recalcul après annulation d'un lien.

## Correctifs après recette écran

- disposition conforme à la maquette sur deux lignes : listes en haut, proposition et statuts en bas ;
- montants et informations métier visibles sans défilement horizontal à la largeur de recette ;
- statuts et compteurs présentés sur deux colonnes pour éviter leur écrasement ;
- calcul immédiat de la proposition après sélection d'une transaction et d'une occurrence.

## Recette attendue

Vérifier les trois zones Transactions à rapprocher, Prévisions à traiter et Proposition de rapprochement, ainsi que les filtres, compteurs, validations, rejets et rapprochements partiels.

## Traçabilité

- #49 : périmètre exhaustif et KPI cohérents ;
- #82 : pré-rapprochement aligné avec l'écran cible bêta.
