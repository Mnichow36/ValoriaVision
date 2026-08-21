# Valoria Vision — R7.2 Correctifs Lot 3
## Centralisation des rapports techniques et métiers

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`

---

## Contexte

L'écran `Rapports` existe déjà dans l'application mais reste actuellement un écran placeholder.

Pendant le correctif R7.2.3, Valoria Vision génère désormais des rapports d'import dans :

`data/reports/imports/`

Ces rapports sont pour l'instant signalés depuis le volet d'import, mais ils ne sont pas encore consultables depuis le module `Rapports`.

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

Dans une première version, l'écran `Rapports` doit afficher les rapports d'import générés automatiquement.

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

## Priorité

Ce point est à traiter après :

1. stabilisation du rapport d'import ;
2. progression visuelle de l'import ;
3. gestion des comptes RIB / IBAN.

Il peut faire partie de la prochaine archive groupée si le Lot 3 reste stable, ou être livré juste après comme sous-lot `Rapports V1 technique`.

---

## Tests à prévoir

- Importer un fichier bancaire générant un rapport.
- Aller dans `Rapports`.
- Vérifier que le rapport d'import apparaît.
- Vérifier que le fichier peut être ouvert.
- Vérifier que le dossier des rapports peut être ouvert.
- Vérifier que l'absence de rapport affiche un état vide lisible.
- Vérifier que les rapports restent consultables après redémarrage de l'application.

---

## Statut

Statut : **cadré — à développer après stabilisation Lot 3 courant**.

Décision : le menu `Rapports` devient le centre de consultation des rapports techniques et métiers générés par Valoria Vision.
