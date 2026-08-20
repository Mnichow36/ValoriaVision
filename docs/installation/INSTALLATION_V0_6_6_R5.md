# Valoria Vision V0.6.6-R5 — Version normalement installable

## Contenu

Cette archive est une base consolidée installable.

Elle reprend la base graphique fonctionnelle et les récupérations validées :

- R1 : paramètres ;
- R2 : catégories / palette couleurs, inclus dans R1 ;
- R3 : scénarios personnalisés ;
- R4 : règles de catégorisation automatique ;
- R4 : annulation d’imports corrigée ;
- R5 : Dashboard validé avec treemap budgétaire et barres revenus/dépenses.

## Moteur graphique

Le moteur graphique Plotly validé est conservé.

Le fichier local suivant est inclus :

```text
data/runtime/plotly.min.js
```

## Installation

1. Décompresser l’archive.
2. Lancer `install.bat`.
3. Quand l’installation est terminée, lancer `run.bat`.

## Important

Ne pas copier de patch à la main dans cette version.
Ne pas remplacer les fichiers Plotly.
Ne pas utiliser de versions ouvertes de dépendances.

Les dépendances sont verrouillées dans :

```text
requirements-lock.txt
```

## Diagnostic

En cas de souci, lancer :

```text
diagnostic_installation.bat
```
