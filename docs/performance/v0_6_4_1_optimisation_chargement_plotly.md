# V0.6.6 — Optimisation chargement Plotly

## Problème

Les graphiques Plotly pouvaient afficher une latence visible au chargement des pages.

## Cause principale

Les premières versions chargeaient Plotly.js via CDN pour chaque graphique QWebEngineView.  
Ce comportement dépend du réseau et du cache navigateur.

## Corrections

- ajout de `app/ui/plotly_runtime.py` ;
- matérialisation locale de `plotly.min.js` dans `data/runtime/` ;
- chargement local de Plotly.js par les vues QWebEngineView ;
- rendu différé de quelques millisecondes pour laisser les KPI et la page apparaître immédiatement ;
- placeholder `Chargement du graphique…` pendant la construction du graphique ;
- application aux cartes Plotly réutilisables, au laboratoire charts et au graphique combiné du Prévisionnel.

## Résultat attendu

- première ouverture plus stable ;
- chargements suivants plus rapides ;
- dépendance réseau supprimée ;
- meilleure impression de réactivité.
