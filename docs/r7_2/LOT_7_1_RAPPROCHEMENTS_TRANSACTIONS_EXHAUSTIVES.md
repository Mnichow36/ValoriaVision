# Lot 7.1 — Rapprochements : exhaustivité des transactions réelles

## Objectif

Corriger l'issue #56 : toutes les transactions réelles présentes dans le registre Transactions doivent être éligibles au module Rapprochements, indépendamment de leur origine technique.

## Diagnostic

Le moteur filtrait encore les transactions avec la condition :

`source IN ('Import bancaire', 'Manuel')`

Cette règle excluait les transactions historiques utilisant d'autres valeurs de source, par exemple :

- `Démo` ;
- anciens imports ou anciennes étiquettes de source ;
- transactions sans source renseignée.

Cela expliquait qu'un compte puisse afficher des transactions dans le module Transactions tout en présentant une liste vide dans Rapprochements.

## Règle métier Lot 7.1

Une transaction enregistrée dans le registre Transactions est une transaction réelle éligible au rapprochement si :

- elle n'est pas supprimée ;
- son compte est actif ;
- sa date appartient à la période sélectionnée ;
- elle correspond au filtre de compte éventuel ;
- elle n'est pas déjà consommée par un rapprochement actif/final lorsque la vue de travail l'exclut.

**L'origine technique de la transaction ne constitue plus un critère d'éligibilité.**

## Correction

Dans `ForecastReconciliationService._eligible_transactions()` :

- suppression du filtre sur `t.source` ;
- ajout explicite de `t.deleted_at IS NULL` ;
- maintien des filtres compte, période et compte actif ;
- maintien de la logique de masquage des transactions déjà liées.

L'interface est également renommée de **Transactions bancaires** vers **Transactions réalisées** afin de refléter que les opérations manuelles et historiques font partie du même périmètre métier.

## Test technique

`tools/test_r7_2_reconciliation_all_transaction_sources.py`

Le test vérifie qu'une même période retourne des transactions ayant comme sources :

- `Import bancaire` ;
- `Manuel` ;
- `Démo` ;
- une ancienne source d'import ;
- aucune source renseignée.

Une transaction supprimée ne doit pas remonter.

## Version

`V0.6.6-R7.2.4 Lot 7.1 Rapprochements exhaustifs`

## Branche

`dev/r7.2.4-lot7.1-rapprochements-transactions-exhaustives`

## Build local

`build_local_lot7_1.bat`

Archive attendue :

`ValoriaVision_INSTALLABLE_V0_6_6_R7_2_4_LOT7_1_RAPPROCHEMENTS_EXHAUSTIFS_<date_heure>.zip`

## Recette locale ciblée

1. Vérifier la version affichée.
2. Ouvrir Transactions et choisir un compte contenant des opérations créées manuellement ou historiquement.
3. Noter au moins une transaction, sa date et son montant.
4. Ouvrir Rapprochements.
5. Sélectionner le même compte et une période couvrant cette transaction.
6. Vérifier que la transaction apparaît dans **Transactions réalisées**.
7. Répéter avec un compte contenant des transactions issues d'un import bancaire.
8. Vérifier que les transactions importées restent présentes.
9. Vérifier qu'une transaction déjà utilisée par un rapprochement actif/final reste masquée dans la vue À traiter.
10. Vérifier que la navigation du module reste fluide après cette correction.

## Critères de sortie

- [x] filtre de source supprimé ;
- [x] transactions supprimées exclues ;
- [x] test multi-origines ajouté ;
- [x] build Lot 7.1 préparé ;
- [x] recette locale utilisateur validée.

## Statut

**LOT 7.1 VALIDÉ ET CLÔTURÉ — recette utilisateur validée le 27/08/2026.**


## Validation finale

Validation utilisateur du 27/08/2026.

Cas recettés :

1. Compte contenant des transactions manuelles / historiques : **OK**.
2. Compte contenant des transactions issues d'un import bancaire : **OK**.

Conclusion :
- les transactions réelles remontent désormais dans Rapprochements indépendamment de leur origine technique ;
- l'issue #56 est considérée corrigée ;
- aucune régression fonctionnelle signalée sur ces deux cas.

**LOT 7.1 VALIDÉ ET CLÔTURÉ.**
