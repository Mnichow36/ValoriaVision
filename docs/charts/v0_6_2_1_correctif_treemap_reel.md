# V0.6.6 — Correctif Treemap réel Plotly

## Problème

Dans `Paramètres > Charts réels`, le Treemap patrimoine pouvait rester blanc alors que les autres graphiques Plotly fonctionnaient.

## Cause probable

Avec les données réelles, certains libellés peuvent être dupliqués ou ambigus entre catégories et éléments.  
Plotly Treemap est plus robuste lorsque chaque nœud dispose d’un identifiant unique (`ids`) et que les parents pointent vers ces identifiants.

## Correction

- ajout d’`ids` uniques pour la racine, les catégories et les éléments patrimoniaux ;
- parents raccordés par identifiants plutôt que par libellés ;
- conservation de valeurs positives via `abs()` pour les passifs ;
- valeurs arrondies ;
- `maxdepth=3` pour une lecture plus propre.

## Impact

Aucun impact sur les données.  
Le correctif concerne uniquement l’affichage Plotly du Treemap réel.
