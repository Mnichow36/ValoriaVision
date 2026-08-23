# Lot 5 — ANO-001 — Persistance récurrences non fonctionnelle

## Constat recette

Version testée : `V0.6.6-R7.2.4 Lot 5 Prévisionnel Récurrences`.

Résultats utilisateur :

| Test | Résultat |
|---|---:|
| Prévisionnel > Gérer les récurrences | OK |
| Bouton Ajouter présent | OK |
| Modifier une récurrence existante | NOK |
| Modification visible après fermeture / réouverture | NOK |
| Ajouter un événement ponctuel | NOK |
| Apparition dans la liste | NOK |
| Apparition dans la courbe / période concernée | NOK |

## Diagnostic

Le patch Lot 5 initial améliore l'affichage et ajoute la date de fin, mais le raccord fonctionnel entre la boîte de dialogue, la liste des récurrences, la base SQLite et le rafraîchissement du prévisionnel n'est pas suffisamment robuste.

Le problème est fonctionnel majeur : l'utilisateur pense modifier ou créer un événement, mais l'action n'est pas conservée dans l'application.

## Décision corrective

Ne pas poursuivre le Lot 5 tant que la persistance n'est pas validée.

Correctif attendu :

- méthodes Lot 5 dédiées pour ajouter / modifier / désactiver une récurrence ;
- écriture SQLite explicite ;
- scellement de la base après mutation ;
- audit des actions ;
- rafraîchissement forcé de la liste et de la page Prévisionnel ;
- test technique couvrant modification existante + création ponctuelle + relecture en base.
