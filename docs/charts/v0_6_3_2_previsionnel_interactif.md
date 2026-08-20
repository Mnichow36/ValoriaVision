# V0.6.6 — Prévisionnel interactif restauré

## Problème

Le remplacement Plotly du graphique Prévisionnel supprimait des fonctions métier essentielles :

- détail des opérations au survol / clic ;
- popup des opérations du jour ;
- clic droit sur un jour ;
- menu contextuel pour modifier, supprimer ou gérer les récurrences.

## Décision

Le Prévisionnel doit rester sur un graphique natif PySide6 interactif tant que Plotly ne permet pas de reproduire complètement ces interactions métier.

## Correction

- restauration de `ForecastDailyChart` dans l’écran Prévisionnel ;
- restauration du `set_forecast(data)` ;
- restauration du texte d’aide sur survol/clic/clic droit ;
- suppression du composant Plotly sur cet écran uniquement.

## Architecture retenue

Approche hybride :

- Plotly pour les graphiques premium de lecture : Dashboard, Budgets, Patrimoine, analyses ;
- graphique natif PySide6 pour les graphiques métier fortement interactifs : Prévisionnel.
