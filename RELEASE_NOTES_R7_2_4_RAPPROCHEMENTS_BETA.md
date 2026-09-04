# Valoria Vision V0.6.6-R7.2.4 — Recette consolidée

## Objet

Version candidate consacrée à la recette consolidée de la chaîne Transactions → Prévisionnel → Rapprochements. Elle ne doit être déclarée conforme qu'après exécution de la recette fonctionnelle #52.

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
- paramétrage des tolérances de date, montant en euros, montant en pourcentage, similarité de libellé et seuils de décision (#57) ;
- protections obligatoires contre les rapprochements entre comptes ou sens opposés ;
- score, justification et audit conservés pour les rapprochements automatiques ;
- remise à traiter d'une occurrence ignorée, annulation motivée et restauration cohérente (#58, #59) ;
- fiche métier détaillée avec liens actifs/annulés et chronologie (#60) ;
- filtres de statut cohérents entre transactions et occurrences (#61).

## Correctifs après recette écran

- disposition conforme à la maquette sur deux lignes : listes en haut, proposition et statuts en bas ;
- montants et informations métier visibles sans défilement horizontal à la largeur de recette ;
- statuts et compteurs présentés sur deux colonnes pour éviter leur écrasement ;
- calcul automatique des meilleures propositions avant toute sélection manuelle ;
- présélection de la meilleure proposition pour validation ou rejet explicite ;
- une proposition rejetée n'est pas recréée lors de l'actualisation suivante ;
- prise en compte des transactions réelles quelle que soit leur origine, y compris les données de démonstration ;
- en cas de scores identiques, priorité au montant exact puis à la date exacte.
- la modification d'une transaction conserve explicitement son sens Débit / Crédit, y compris après plusieurs modifications (#2) ;
- le Dashboard utilise un accueil neutre sans prénom codé en dur (#78).

## Recette attendue

Vérifier les trois zones Transactions réalisées, Occurrences prévisionnelles et Proposition de rapprochement, ainsi que les règles configurables, filtres, compteurs, validations, rejets, annulations et rapprochements partiels. Le verdict final est porté par l'issue #52.

## Traçabilité

- #49 : périmètre exhaustif et KPI cohérents ;
- #57 à #61 : moteur paramétrable, cycle de vie, historique et filtres ;
- #82 : pré-rapprochement aligné avec l'écran cible bêta ;
- #2 et #78 : régressions Transactions et Dashboard.
