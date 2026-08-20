# V0.6.6 — Correctif Treemap Plotly

## Problème

Dans le laboratoire charts Plotly, le graphique `Treemap — patrimoine fictif` pouvait rester blanc.

## Cause

Le treemap utilisait `branchvalues="total"` avec une valeur racine égale à 0.

Avec ce mode, Plotly attend que chaque parent ait une valeur supérieure ou égale à la somme de ses enfants.  
Le parent racine `Patrimoine` devait donc porter le total fictif.

## Correction

- valeur racine `Patrimoine` corrigée ;
- valeurs parents cohérentes avec les enfants ;
- ajout d’un affichage label + valeur + pourcentage ;
- ajout d’un hover clair en euros.

## Impact

Aucun impact sur les données réelles.  
Aucun écran existant n’est modifié.
