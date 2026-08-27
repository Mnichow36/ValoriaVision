# Lot 7.2 — Rapprochements : statuts, filtres et cycle de vie

## Objectif

Corriger ensemble les issues #61, #58 et #59 afin de rendre le module Rapprochements cohérent dans ses filtres, ses actions et le cycle de vie des occurrences.

## Règles fonctionnelles

### Filtres de statut

Les deux panneaux doivent toujours représenter le même contexte métier.

- **Rapprochée manuelle** : seules les occurrences rapprochées manuellement et leurs transactions liées sont affichées.
- **Rapprochée auto** : seules les occurrences rapprochées automatiquement et leurs transactions liées sont affichées.
- **À vérifier** : seules les propositions visibles et leurs transactions liées sont affichées.
- **Ignorée** : aucune transaction sans rapport n'est affichée.
- **Annulée** : aucune transaction sans rapport n'est affichée.
- **Prévue / En retard / À traiter** : seules les transactions encore disponibles pour un rapprochement restent visibles.
- **Historique complet** : le jeu complet reste consultable.

### Cycle de vie

Une occurrence :
- Prévue ou En retard peut être **Ignorée** ;
- Prévue ou En retard peut être **Annulée** ;
- Ignorée ou Annulée peut être **Remise à traiter** ;
- Rapprochée manuellement, automatiquement ou À vérifier ne propose **Annuler rapprochement** que si un lien transaction existe réellement.

Lors d'une remise à traiter :
- date passée → statut En retard ;
- date future → statut Prévue.

Les motifs d'ignorance et d'annulation restent conservés.

## Menu contextuel

Le clic droit est désormais dépendant du statut réel de l'occurrence :

- Prévue / En retard :
  - Rapprocher avec la transaction cochée
  - Ignorer l'occurrence
  - Annuler l'occurrence
- À vérifier :
  - Annuler rapprochement si un lien existe
  - Ignorer l'occurrence
- Rapprochée auto / manuelle :
  - Annuler rapprochement si un lien existe
- Ignorée / Annulée :
  - Remettre à traiter
- Tous les statuts :
  - Afficher les informations

## Traçabilité minimale

Ajout sur `forecast_occurrences` :
- `cancelled_reason`
- `cancelled_at`
- `reactivated_at`

L'historique métier détaillé reste prévu dans l'issue #60.

## Tests techniques

- `tools/test_r7_2_reconciliation_status_filters.py`
  - vérifie l'alignement du panneau Transactions avec le statut d'occurrence sélectionné.
- `tools/test_r7_2_occurrence_lifecycle.py`
  - vérifie Annuler, Remettre à traiter, Ignorer et les protections contre les états incompatibles.

Ces tests sont intégrés au build local.

## Version

`V0.6.6-R7.2.4 Lot 7.2 Cycle de vie rapprochements`

## Branche

`dev/r7.2.4-lot7.2-rapprochements-cycle-vie`

## Build local

`build_local_lot7_2.bat`

Archive attendue :

`ValoriaVision_INSTALLABLE_V0_6_6_R7_2_4_LOT7_2_CYCLE_VIE_RAPPROCHEMENTS_<date_heure>.zip`

## Recette ciblée

1. Vérifier la version Lot 7.2.
2. Réaliser ou utiliser un rapprochement manuel existant.
3. Cliquer **Rapprochée manuelle** :
   - l'occurrence liée doit être isolée ;
   - seule la transaction liée doit apparaître à gauche.
4. Tester de la même façon **Rapprochée auto** et **À vérifier** si des cas existent.
5. Sur une occurrence Prévue ou En retard, clic droit :
   - **Annuler rapprochement** ne doit pas apparaître s'il n'existe aucun lien ;
   - **Ignorer l'occurrence** doit être disponible ;
   - **Annuler l'occurrence** doit être disponible.
6. Ignorer une occurrence puis ouvrir le filtre **Ignorée** :
   - l'occurrence doit être retrouvée ;
   - **Remettre à traiter** doit être proposé ;
   - **Ignorer l'occurrence** ne doit plus être proposé.
7. Cliquer **Remettre à traiter** :
   - si la date est passée → En retard ;
   - sinon → Prévue ;
   - compteurs mis à jour immédiatement.
8. Annuler une occurrence Prévue/En retard :
   - elle disparaît de À traiter ;
   - le compteur Annulée augmente ;
   - elle reste dans Historique complet ;
   - le filtre Annulée la retrouve.
9. Sur une occurrence Annulée :
   - **Remettre à traiter** doit être proposé.
10. Vérifier qu'aucune transaction sans rapport n'apparaît lorsque Ignorée ou Annulée est sélectionné.
11. Vérifier que la navigation reste fluide.

## Critères de sortie

- [x] filtre transaction/occurrence cohérent par statut ;
- [x] réactivation des occurrences ignorées ;
- [x] annulation explicite des occurrences ;
- [x] menu contextuel dépendant du statut ;
- [x] traçabilité minimale ajoutée ;
- [x] tests intégrés au build ;
- [ ] recette locale utilisateur validée.

## Statut

**LOT 7.2 IMPLÉMENTÉ — en attente de recette locale utilisateur.**
