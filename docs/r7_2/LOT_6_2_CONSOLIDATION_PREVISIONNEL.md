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

## Corrections et consolidation réalisées

Le filtrage historique qui excluait certaines récurrences selon leur ancien champ scénario a été supprimé du moteur `forecast_events()`.

Désormais :
- toutes les récurrences standards appartiennent à la base commune ;
- les événements générés portent la portée technique `Tous` ;
- les différences Prudent / Réaliste / Optimiste proviennent uniquement du service d'hypothèses validé au Lot 6.1 ;
- le Dashboard consomme le même moteur `cash_forecast()` que le Prévisionnel ;
- le Dashboard affiche explicitement la comparaison Prudent / Réaliste / Optimiste à 60 jours ;
- Réaliste reste la référence pour les alertes et indicateurs de synthèse ;
- en édition Free, aucun scénario personnalisé n'est exposé dans le Prévisionnel.

## Version

`V0.6.6-R7.2.4 Lot 6.2 Consolidation prévisionnel`

## Issue de suivi

#64

## Tests de non-régression

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

Archive :

`ValoriaVision_INSTALLABLE_V0_6_6_R7_2_4_LOT6_2_CONSOLIDATION_PREVISIONNEL_<date_heure>.zip`

## Recette utilisateur — validation du 27/08/2026

Résultats communiqués pendant la recette :

1. Version Lot 6.2 affichée correctement : **OK**.
2. Dashboard — comparaison des scénarios à 60 jours présente : **OK**.
3. Prudent / Réaliste / Optimiste produisent des valeurs cohérentes : **OK**.
4. Réaliste correspond à la référence du Prévisionnel : **OK**.
5. Une même récurrence reste présente dans les trois scénarios et son montant projeté est corrigé selon l'hypothèse choisie, sans modifier le montant source : **OK**.
6. En édition Free, seuls Prudent / Réaliste / Optimiste sont proposés dans Prévisionnel : **OK**.
7. Aucun ancien rattachement de récurrence à un scénario standard ne la fait disparaître d'une projection : **OK**.
8. La lisibilité de la comparaison Dashboard a été contrôlée : la comparaison est fonctionnelle.
9. Une lenteur de navigation observée autour du module Rapprochements a été traitée séparément et déclarée résolue avant clôture administrative du Lot 6.2.

## Critères de sortie

- [x] filtrage historique des récurrences supprimé ;
- [x] portée commune `Tous` exposée par le moteur ;
- [x] comparaison Dashboard des trois scénarios ajoutée ;
- [x] tests de non-régression ajoutés au build ;
- [x] build local Lot 6.2 préparé ;
- [x] recette locale utilisateur validée ;
- [x] aucune régression bloquante de navigation maintenue ouverte au moment de la clôture.

## Conclusion

**LOT 6.2 VALIDÉ ET CLÔTURÉ ADMINISTRATIVEMENT — 27/08/2026.**

Suite prévue : **Lot 7.1 — Rapprochements, exhaustivité des transactions réelles**, avec priorité à l'issue #56, puis cohérence des statuts/filtres (#61) et recette globale #52.
