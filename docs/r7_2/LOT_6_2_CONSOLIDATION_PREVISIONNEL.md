# Lot 6.2 — Consolidation du Prévisionnel

## Objectif

Consolider le socle standard du Prévisionnel après validation du Lot 6.1, sans enrichissement du module Scénarios Premium.

## Périmètre

- cohérence Prudent / Réaliste / Optimiste dans Prévisionnel et Dashboard ;
- suppression des reliquats de filtrage des récurrences par scénario exclusif ;
- vérification de l'absence de scénarios personnalisés exposés en édition Free ;
- harmonisation des libellés et aides ;
- tests de non-régression du moteur prévisionnel ;
- recette courte avant passage au Lot 7 Rapprochements.

## Première correction

Le filtrage historique qui excluait certaines récurrences selon leur ancien champ scénario a été supprimé du moteur `forecast_events()`.

Désormais :
- toutes les récurrences standards appartiennent à la base commune ;
- les événements générés portent la portée technique `Tous` ;
- les différences Prudent / Réaliste / Optimiste proviennent uniquement du service d'hypothèses validé au Lot 6.1.

## Version

`V0.6.6-R7.2.4 Lot 6.2 Consolidation prévisionnel`

## Issue de suivi

#64

## Statut

**LOT 6.2 DÉMARRÉ.**


## Consolidation Dashboard

Le Dashboard consomme le même moteur `cash_forecast()` que le Prévisionnel.

La carte d'alertes affiche désormais explicitement les soldes projetés à 60 jours pour :
- Prudent ;
- Réaliste ;
- Optimiste.

Réaliste reste la référence pour les alertes et indicateurs de synthèse, tandis que la comparaison des trois scénarios devient visible.

## Tests de non-régression ajoutés

- `tools/test_r7_2_dashboard_scenario_consistency.py`
  - vérifie que le Dashboard reprend les trois projections ;
  - vérifie que Réaliste reste la référence d'alerte ;
  - vérifie l'ordre Prudent < Réaliste < Optimiste dans un cas contrôlé.

- `tools/test_r7_2_common_recurrence_forecast.py`
  - vérifie qu'une ancienne récurrence historiquement marquée Optimiste reste présente dans les projections Réaliste, Prudent et Optimiste ;
  - vérifie que la portée exposée par le moteur est désormais `Tous`.

Ces tests sont intégrés au build local du Lot 6.2.

## Build local

Lanceur dédié :

`build_local_lot6_2.bat`

Archive attendue :

`ValoriaVision_INSTALLABLE_V0_6_6_R7_2_4_LOT6_2_CONSOLIDATION_PREVISIONNEL_<date_heure>.zip`

## Recette locale courte Lot 6.2

1. Vérifier la version : `V0.6.6-R7.2.4 Lot 6.2 Consolidation prévisionnel`.
2. Ouvrir le Dashboard.
3. Vérifier la ligne **Comparaison des scénarios à 60 jours** avec Prudent / Réaliste / Optimiste.
4. Vérifier que les trois soldes sont distincts lorsqu'il existe au moins une récurrence et des coefficients non nuls.
5. Vérifier que Réaliste reste cohérent avec la valeur de référence affichée dans le Prévisionnel sur le même horizon.
6. Ouvrir Prévisionnel et contrôler qu'une même récurrence apparaît dans les trois scénarios.
7. En édition Free, vérifier que seuls Prudent / Réaliste / Optimiste sont proposés dans Prévisionnel.
8. Vérifier qu'aucun ancien rattachement de récurrence à Optimiste/Prudent/Réaliste ne la fait disparaître d'une projection.

## Critères de sortie

- [x] filtrage historique des récurrences supprimé ;
- [x] portée commune `Tous` exposée par le moteur ;
- [x] comparaison Dashboard des trois scénarios ajoutée ;
- [x] tests de non-régression ajoutés au build ;
- [x] build local Lot 6.2 préparé ;
- [ ] recette locale utilisateur validée.

## Statut

**LOT 6.2 IMPLÉMENTÉ — en attente de recette locale utilisateur.**
