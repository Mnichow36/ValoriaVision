# V0.6.6 — Laboratoire charts Plotly

## Objectif

Créer un laboratoire isolé pour tester Plotly dans Valoria Vision sans modifier les graphiques existants.

## Décision technique

Plotly devient le moteur principal des futurs graphiques premium de Valoria Vision.

Affichage desktop :
- PySide6 ;
- QWebEngineView ;
- rendu HTML Plotly embarqué.

## Phase 1 — Prototype isolé

Ajout dans :
- Paramètres ;
- onglet Laboratoire charts.

Graphiques de test :
- donut ;
- treemap ;
- courbe ;
- graphique budget prévu / réalisé.

## Données

Les graphiques utilisent volontairement des données fictives.

## Objectif de recette

Valider :
- rendu visuel ;
- lisibilité ;
- intégration dans PySide6 ;
- absence d’impact sur les écrans existants ;
- comportement avec install.bat.

## Phase suivante

V0.6.6 — Raccord Plotly aux vraies données.
