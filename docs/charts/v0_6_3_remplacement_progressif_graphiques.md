# V0.6.6 — Remplacement progressif des graphiques

## Objectif

Commencer le remplacement des anciens graphiques par Plotly dans les écrans métiers, tout en conservant le laboratoire.

## Remplacements réalisés

### Dashboard

Remplacement par Plotly :
- courbe de trésorerie prévisionnelle ;
- donut répartition du patrimoine ;
- donut répartition des dépenses du mois.

### Budgets

Ajout/remplacement par Plotly :
- graphique prévu / réalisé ;
- graphique d’utilisation par catégorie.

## Socle technique

Ajout d’un composant réutilisable :
- `app/ui/plotly_components.py`
- `PlotlyFigureCard`

## Important

Le remplacement reste progressif.  
Les autres écrans seront migrés dans les versions suivantes.
