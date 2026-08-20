# V0.6.6-R5.1 — Correctif messages console Qt

## Problème

Lors du lancement, la console pouvait afficher :

```text
QFont::setPointSize: Point size <= 0 (-1), must be greater than 0
Could not parse stylesheet of object QPushButton(...)
```

## Nature du problème

Ce sont des avertissements Qt liés au parsing des stylesheets.
Ils ne concernent pas les données, ni les graphiques Plotly, ni SQLite.

## Correction

- remplacement des `font-weight` numériques par des valeurs compatibles Qt ;
- suppression des `line-height` non supportés par Qt stylesheets ;
- aucune modification du moteur graphique ;
- aucune modification de la base métier.

## Installation

Utiliser `install.bat`, puis `run.bat`.
