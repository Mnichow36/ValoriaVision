# Règle produit — Prévisionnel standard / Scénarios Premium

Date de décision : 26/08/2026

## Principe

Valoria Vision distingue désormais clairement deux niveaux de simulation.

### Socle standard

Le module **Prévisionnel** reste disponible dans l'édition standard avec trois hypothèses simples :

- Prudent ;
- Réaliste ;
- Optimiste.

Ces hypothèses modifient la lecture d'une même base prévisionnelle. Elles n'ont pas vocation à devenir des projets autonomes.

Les récurrences courantes appartiennent à cette base commune et ne doivent pas être rattachées exclusivement à un scénario standard.

### Premium

Le module **Scénarios** est réservé aux éditions Premium.

Il est destiné aux simulations avancées et personnalisées :

- achat immobilier ;
- travaux ;
- changement de revenus ;
- retraite ;
- investissement ;
- crédit ;
- changement de situation ;
- tout autre projet composé d'événements spécifiques.

Un scénario Premium peut contenir ses propres événements ponctuels ou récurrents et être comparé à la situation de référence.

## Règle UX

Dans l'édition gratuite :

- l'entrée **Scénarios — PREMIUM** reste visible dans la navigation ;
- l'ouverture affiche une page explicative Premium ;
- aucun écran de création, modification ou simulation personnalisée n'est accessible.

Dans une édition Premium :

- l'entrée ouvre le véritable module Scénarios ;
- les scénarios personnalisés sont accessibles normalement.

## Règle technique

Le contrôle d'accès est centralisé dans :

`app/services/feature_access_service.py`

Clé de paramétrage actuelle :

`product.edition`

Valeur par défaut :

`free`

Éditions autorisant le module Scénarios :

- `premium`
- `premium_personnel`
- `patrimoine_expert`
- `pro`

Cette couche est volontairement indépendante d'un futur moteur de licence commerciale afin de pouvoir être raccordée plus tard sans réécrire l'interface.

## Conséquence Lot 6

Le Lot 6 conserve les hypothèses Prudent / Réaliste / Optimiste dans Prévisionnel.

Les fonctionnalités avancées de scénarios personnalisés restent développées mais sont désormais classées **Premium**.

## Statut

**RÈGLE PRODUIT VALIDÉE ET IMPLÉMENTÉE.**


## Récurrences standards

Les récurrences du Prévisionnel constituent une **base commune** et ne sont jamais rattachées exclusivement à un scénario.

Le champ de scénario est donc supprimé de leur interface. La valeur technique `Tous` est utilisée pour assurer la compatibilité avec le schéma existant.

Les variantes Prudent / Réaliste / Optimiste modifient cette base commune par hypothèses. Les simulations spécifiques restent du ressort du module Scénarios Premium et de ses propres événements.
