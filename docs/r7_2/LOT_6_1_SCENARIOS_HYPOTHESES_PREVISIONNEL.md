# Lot 6.1 — Scénarios standards : hypothèses et impact prévisionnel

## Objectif

Démarrer le Lot 6 issu de l'issue #63 en supprimant le caractère décoratif des scénarios standards du Prévisionnel.

Les choix **Prudent**, **Réaliste** et **Optimiste** doivent produire des projections réellement différentes et l'utilisateur doit pouvoir comprendre l'hypothèse appliquée.

## Périmètre Lot 6.1

### Hypothèses standards initiales

| Scénario | Revenus prévisionnels | Dépenses prévisionnelles |
|---|---:|---:|
| Prudent | -5 % | +10 % |
| Réaliste | 0 % | 0 % |
| Optimiste | +5 % | -5 % |

Ces valeurs sont des valeurs initiales. Elles sont lues depuis la table générique `settings` afin de préparer leur modification depuis l'interface sans migration supplémentaire de la base.

### Règle de sécurité métier

Les coefficients s'appliquent uniquement aux **récurrences prévisionnelles**.

Ils ne modifient jamais :

- une transaction bancaire réelle ;
- une transaction future déjà enregistrée dans la table Transactions ;
- le montant stocké du modèle de récurrence.

L'ajustement est appliqué uniquement à l'occurrence calculée pour la projection.

### Explicabilité

Le panneau d'information du Prévisionnel affiche désormais une ligne **Hypothèse appliquée** indiquant les variations utilisées par le scénario sélectionné.

Les événements ajustés transportent également :

- le montant d'origine ;
- le pourcentage d'ajustement ;
- la règle de scénario appliquée.

### Scénarios personnalisés

Le mécanisme existant des scénarios personnalisés et de leurs événements reste conservé. Le Lot 6 poursuivra leur raccord complet et la cohérence des associations avec les récurrences / événements.

## Correction UX associée

Le dialogue de création / modification d'un scénario contenait un appel résiduel à une méthode de durée utilisant des champs inexistants. Le patch Lot 6.1 neutralise ce blocage afin de rendre à nouveau la création et la modification accessibles.

## Fichiers ajoutés / modifiés

- `app/services/scenario_hypothesis_service.py`
- `app/r7_2/scenario_hypotheses_patch.py`
- `main.py`
- `tools/test_r7_2_scenario_hypotheses.py`

## Version visible

`V0.6.6-R7.2.4 Lot 6.1 Scénarios paramétrables`

## Recette ciblée

1. Lancer Valoria Vision sur la version Lot 6.1.
2. Ouvrir Prévisionnel avec une période contenant au moins une recette ou dépense récurrente.
3. Sélectionner **Réaliste** et noter le cash final / point bas.
4. Sélectionner **Prudent** : le cash final doit se dégrader si la période contient des flux prévisionnels concernés.
5. Sélectionner **Optimiste** : le cash final doit s'améliorer dans le même cas.
6. Vérifier que **Hypothèse appliquée** décrit les coefficients utilisés.
7. Vérifier que les transactions réelles ne changent pas de montant.
8. Ouvrir Scénarios et vérifier que Nouveau scénario / Modifier ne provoque pas d'erreur liée à `frequency` ou `duration`.

## Suite du Lot 6

- exposer dans l'interface la modification des pourcentages des scénarios standards ;
- rendre les hypothèses personnalisées plus riches (date, montant, activation d'événements) ;
- permettre l'association explicite des récurrences / événements aux scénarios ;
- garantir la cohérence entre Prévisionnel, Scénarios et Paramètres ;
- compléter les tests de non-régression.

## Statut

**DÉVELOPPEMENT DÉMARRÉ — Lot 6.1 implémenté sur la branche `dev/r7.2.4-lot6-scenarios-parametrables`.**

Recette locale à effectuer avant validation du sous-lot.
