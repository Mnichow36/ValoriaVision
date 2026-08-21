# Valoria Vision — R7.2 Correctifs Lot 3
## Centralisation des rapports techniques et métiers

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`

---

## Contexte

L'écran `Rapports` existe déjà dans l'application mais restait jusqu’ici un écran placeholder.

Pendant le correctif R7.2.3, Valoria Vision génère désormais des rapports d'import dans :

`data/reports/imports/`

Ces rapports sont signalés depuis le volet d'import. Le besoin métier exprimé est qu’ils soient également retrouvables durablement dans le menu `Rapports`.

---

## Décision produit

Le module `Rapports` doit progressivement devenir le point central de consultation des rapports générés par les différents modules de Valoria Vision.

Ce module ne doit donc pas être limité aux exports PDF/Excel futurs. Il doit regrouper :

- rapports techniques ;
- rapports métiers ;
- historiques d'import ;
- contrôles de cohérence ;
- audits de rapprochement ;
- rapports de budget ;
- rapports de patrimoine ;
- rapports de scénarios ;
- exports utilisateur.

---

## Première application : rapports d'import

### Comportement attendu

Dans une première version, l'écran `Rapports` affiche les rapports d'import générés automatiquement.

Informations minimales à afficher :

- date de génération ;
- nom du fichier importé ;
- compte concerné ;
- statut du rapport ;
- nombre de lignes importées ;
- doublons ;
- erreurs / rejets ;
- chemin du rapport ;
- action `Ouvrir le rapport` ;
- action `Ouvrir le dossier`.

---

## Implémentation Lot 3 réalisée côté branche

### Fichiers ajoutés / modifiés

- `app/ui/reports_page.py`
- `app/main_window.py`
- `tools/test_r7_2_reports_page.py`

### Comportement implémenté

- Remplacement du placeholder `Rapports` par une vraie page `ReportsPage`.
- Scan automatique du dossier `data/reports/imports/`.
- Affichage des rapports `.txt` générés par les imports.
- Cartes de synthèse par rapport.
- KPIs : nombre de rapports, lignes importées, doublons, erreurs/rejets.
- Bouton `Ouvrir le rapport`.
- Bouton `Ouvrir le dossier`.
- État vide lisible si aucun rapport n’existe encore.
- Test technique de parsing des rapports d’import.

### Limite volontaire

Cette première version centralise uniquement les rapports d’import bancaire.

Les futurs rapports de rapprochement, budget, patrimoine, prévisionnel, scénarios et exports seront ajoutés ensuite au même centre de rapports.

---

## Organisation cible du module Rapports

À terme, l'écran pourrait être structuré par sections :

1. `Imports bancaires`
2. `Transactions`
3. `Rapprochements`
4. `Prévisionnel`
5. `Budgets`
6. `Patrimoine`
7. `Scénarios`
8. `Exports`

Chaque section pourrait afficher :

- les rapports disponibles ;
- leur date ;
- leur module source ;
- leur statut ;
- une action d'ouverture ;
- une action d'export ou de suppression contrôlée si applicable.

---

## Règle importante

Le module `Rapports` ne doit pas remplacer les messages contextuels dans les modules.

Exemple : après un import, le volet `Transactions > Importer` doit continuer à afficher que le rapport a été généré.

Mais le rapport doit aussi être retrouvable plus tard dans `Rapports`.

---

## Tests à prévoir en recette

- Importer un fichier bancaire générant un rapport.
- Aller dans `Rapports`.
- Vérifier que le rapport d'import apparaît.
- Vérifier que le fichier peut être ouvert.
- Vérifier que le dossier des rapports peut être ouvert.
- Vérifier que l'absence de rapport affiche un état vide lisible.
- Vérifier que les rapports restent consultables après redémarrage de l'application.

---

## Statut

Statut : **implémenté côté branche — à vérifier dans la prochaine archive groupée Lot 3**.

Décision : le menu `Rapports` devient le centre de consultation des rapports techniques et métiers générés par Valoria Vision.
