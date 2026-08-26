# Lot 6.1 — Scénarios standards : hypothèses et impact prévisionnel

## Objectif

Démarrer le Lot 6 issu de l'issue #63 en supprimant le caractère décoratif des scénarios standards du Prévisionnel.

Les choix **Prudent**, **Réaliste** et **Optimiste** doivent produire des projections réellement différentes et l'utilisateur doit pouvoir comprendre et paramétrer l'hypothèse appliquée.

## Hypothèses standards initiales

| Scénario | Revenus prévisionnels | Dépenses prévisionnelles |
|---|---:|---:|
| Prudent | -5 % | +10 % |
| Réaliste | 0 % | 0 % |
| Optimiste | +5 % | -5 % |

Les valeurs Prudent et Optimiste sont modifiables depuis l'interface. Réaliste reste la référence à **0 % / 0 %**.

Les coefficients sont persistés dans la table générique `settings`, sans migration supplémentaire du schéma.

## Interface Lot 6.1

Dans **Prévisionnel**, à côté du sélecteur **Scénario**, un bouton **Paramétrer** ouvre la fenêtre **Hypothèses de projection**.

Cette fenêtre permet de :

- modifier la variation des revenus de Prudent ;
- modifier la variation des dépenses de Prudent ;
- consulter Réaliste à 0 % / 0 %, non modifiable ;
- modifier la variation des revenus d'Optimiste ;
- modifier la variation des dépenses d'Optimiste ;
- réinitialiser les valeurs par défaut ;
- enregistrer les coefficients.

Après enregistrement, le Prévisionnel est recalculé immédiatement.

## Règle de sécurité métier

Les coefficients s'appliquent uniquement aux **récurrences prévisionnelles**.

Ils ne modifient jamais :

- une transaction bancaire réelle ;
- une transaction future déjà enregistrée dans Transactions ;
- le montant stocké du modèle de récurrence.

L'ajustement est appliqué uniquement à l'occurrence calculée pour la projection.

## Explicabilité

Le panneau **Analyse de la période** du Prévisionnel affiche une ligne **Hypothèse appliquée** indiquant les coefficients actifs.

Les événements ajustés transportent également :

- le montant d'origine ;
- le pourcentage d'ajustement ;
- la règle de scénario appliquée.

## Scénarios personnalisés

Le mécanisme existant des scénarios personnalisés et de leurs événements est conservé. Les scénarios personnalisés restent alimentés par leurs propres événements, sans appliquer automatiquement les coefficients Prudent / Réaliste / Optimiste.

## Correction UX associée

Le dialogue de création / modification d'un scénario contenait un appel résiduel à une méthode de durée utilisant des champs inexistants. Le patch Lot 6.1 neutralise ce blocage afin de rendre à nouveau la création et la modification accessibles.

## Fichiers Lot 6.1

- `app/services/scenario_hypothesis_service.py`
- `app/r7_2/scenario_hypotheses_patch.py`
- `main.py`
- `tools/test_r7_2_scenario_hypotheses.py`
- `tools/build_r7_2_3_installable.ps1`
- `build_local_lot6_1.bat`

## Version visible

`V0.6.6-R7.2.4 Lot 6.1 Scénarios paramétrables`

## Recette ciblée

1. Construire la version avec `build_local_lot6_1.bat`.
2. Ouvrir Prévisionnel avec une période contenant au moins une recette ou dépense récurrente.
3. Sélectionner **Réaliste** et noter le cash final, le point bas, les entrées et les sorties.
4. Sélectionner **Prudent** : la projection doit refléter les coefficients configurés.
5. Sélectionner **Optimiste** : la projection doit refléter les coefficients configurés.
6. Ouvrir **Paramétrer** et modifier au moins un coefficient Prudent ou Optimiste.
7. Enregistrer : la projection doit être recalculée immédiatement.
8. Rouvrir **Paramétrer** : les valeurs enregistrées doivent être conservées.
9. Cliquer **Réinitialiser les valeurs**, enregistrer et vérifier le retour aux valeurs initiales.
10. Ouvrir **Analyse de la période** et vérifier la ligne **Hypothèse appliquée**.
11. Vérifier qu'une transaction réelle conserve strictement son montant quel que soit le scénario.
12. Vérifier qu'une transaction future enregistrée conserve strictement son montant.
13. Vérifier que le montant source d'une récurrence n'est pas modifié en base.
14. Ouvrir Scénarios et vérifier que Nouveau scénario / Modifier ne provoque pas d'erreur liée à `frequency` ou `duration`.

## Critères de sortie Lot 6.1

- [x] scénarios standards dotés d'hypothèses chiffrées ;
- [x] impact réel sur les récurrences du moteur prévisionnel ;
- [x] transactions réelles protégées ;
- [x] transaction future enregistrée protégée ;
- [x] coefficients persistés dans les paramètres ;
- [x] interface d'édition Prudent / Optimiste ;
- [x] Réaliste verrouillé comme référence ;
- [x] hypothèse active expliquée dans Prévisionnel ;
- [x] test technique dédié intégré au script de build ;
- [ ] recette utilisateur locale validée.

## Suite du Lot 6

Après validation de ce sous-lot :

- association plus explicite des récurrences et événements aux scénarios ;
- enrichissement des hypothèses personnalisées ;
- cohérence complète Prévisionnel / Scénarios / Paramètres ;
- traitement des autres critères de l'issue #63.

## Statut

**LOT 6.1 IMPLÉMENTÉ — en attente de recette locale utilisateur.**


## Récurrences communes

Décision métier complémentaire du 26/08/2026 :

- les récurrences standards n'appartiennent plus à un scénario exclusif ;
- le champ Scénario est retiré de la fiche et de la liste des récurrences ;
- toute nouvelle récurrence est enregistrée avec la portée technique `Tous` ;
- les anciennes valeurs Prudent / Réaliste / Optimiste / personnalisées sont normalisées vers `Tous` au démarrage ;
- cette normalisation ne modifie ni montant, ni date, ni fréquence, ni compte ;
- Prudent / Réaliste / Optimiste agissent ensuite sur cette même base commune via les hypothèses du Lot 6.1.

Dans l'édition Free, le sélecteur de scénario du Prévisionnel n'affiche que Prudent / Réaliste / Optimiste. Les scénarios personnalisés restent réservés au module Scénarios Premium.

### Recette complémentaire

15. Ouvrir une récurrence existante : aucun champ Scénario ne doit être proposé.
16. Créer une nouvelle récurrence puis basculer entre Prudent, Réaliste et Optimiste : la récurrence doit exister dans les trois projections.
17. Vérifier qu'une ancienne récurrence historiquement rattachée à Optimiste apparaît également en Réaliste et Prudent après migration.
18. En édition Free, vérifier qu'aucun scénario personnalisé n'apparaît dans le sélecteur du Prévisionnel.
