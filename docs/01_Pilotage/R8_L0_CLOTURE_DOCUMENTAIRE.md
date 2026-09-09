# R8 — Clôture documentaire du lot L0

**Issue de pilotage :** #120  
**Date de consolidation :** 9 septembre 2026  
**Statut :** référence de travail après remise à plat des PR  
**Commit de référence :** `ffe181526ce3729af132624cee9378bfaffc091f`

## 1. Documents de fondation validés

Les documents suivants constituent le référentiel R8 :

- `docs/03_Cahier_des_Charges/R8_RAPPROCHEMENTS_SPECIFICATION_FONCTIONNELLE.md` ;
- `docs/reconciliation/R8_RAPPROCHEMENTS_MACHINE_ETATS.md` ;
- `docs/04_ADR/ADR_R8_MODELE_RAPPROCHEMENTS.md` ;
- `docs/05_Recette/R8_RAPPROCHEMENTS_PLAN_RECETTE.md` ;
- `docs/05_Recette/R8_RAPPROCHEMENTS_MATRICE_RECETTE.csv` ;
- `docs/reconciliation/R8_LOT1_MODELE_MIGRATION.md`.

Cette validation porte sur la cohérence des fondations et du plan de recette. Elle ne signifie pas que l’ensemble des scénarios fonctionnels et UI est déjà livré.

## 2. Historique d’intégration

| Ordre | Référence | Résultat |
|---:|---|---|
| 1 | PR #92 | Fondations fonctionnelles et recette fusionnées |
| 2 | PR #93 | Schéma, migration et tests P0 fusionnés |
| 3 | PR #94 | Moteur, scoring et qualification fusionnés |
| 4 | PR #97 | Persistance, audit et réévaluation fusionnés |
| Exclue | PR #95 | Doublon fermé, non compté |

## 3. Décisions techniques consolidées

- `main` est l’unique base des prochains travaux ;
- les nouvelles branches doivent partir du commit de référence ci-dessus ou d’un descendant ;
- les PR empilées #94 et #97 ont été remises à plat et fusionnées dans l’ordre ;
- les montants sont normalisés au centime avant scoring ;
- les décisions de qualification, propositions, expirations et rapprochements automatiques sont auditables ;
- la persistance utilise un savepoint et son rollback est testé ;
- les PR ne doivent pas être comptées comme des issues produit dans le pilotage.

## 4. Validation technique constatée

Au commit précédant la fusion de #97 :

- 36 tests R8 réussis ;
- workflow GitHub Actions `R8 reconciliation tests` vert ;
- aucun conflit de fusion ;
- diff de chaque PR limité à son périmètre annoncé.

## 5. Travaux restant hors de cette validation documentaire

- branchement du moteur dans les flux réels d’import et de saisie manuelle ;
- réévaluation après modification des transactions et prévisions ;
- annulation métier complète ;
- UI R8, KPI, filtres et scénarios E2E ;
- volumétrie et recette sur copie anonymisée d’une base R7.2.

Ces travaux relèvent des lots fonctionnels suivants et ne doivent pas être considérés comme livrés par L0.
