# Rapport de tests techniques — Valoria Vision V0.6.6-R7.2

## Tests exécutés dans l'environnement de développement

### Import CSV Société Générale réel fourni

Résultat :

- encodage détecté : `cp1252` ;
- séparateur détecté : `;` ;
- véritable ligne d'en-tête détectée : ligne 3 ;
- profil détecté : `Société Générale CSV` ;
- opérations reconnues : 314 ;
- lignes rejetées : 0 ;
- montants français correctement convertis ;
- débits négatifs et crédits positifs conservés.

### Fixture Société Générale anonymisée incluse

Commande :

```bat
python tools\test_r7_2_import_sg.py
```

Résultat obtenu :

- profil : `Société Générale CSV` ;
- encodage : `cp1252` ;
- séparateur : `;` ;
- en-tête ligne : 3 ;
- opérations reconnues : 25 ;
- lignes rejetées : 0.

### Import en base de test

Sur une base de test initialisée depuis le socle R7.1 :

- opérations SG reconnues : 314 ;
- import en base : 313 nouvelles opérations + 1 doublon préexistant dans le jeu seedé ;
- contrôle après import : 314 signatures reconnues comme déjà présentes ;
- catégorisation automatique exécutée ;
- transactions hors règle restées à catégoriser ;
- moteur de rapprochement appelé après import.

### Rapprochement manuel / annulation

Scénario technique :

- création d'une transaction réelle `Loyer` ;
- génération des occurrences de juillet 2026 ;
- rapprochement manuel avec l'occurrence `Loyer` ;
- disparition de l'occurrence de la vue active ;
- compteur `confirmed` passé à 1 dans l'historique ;
- annulation du rapprochement ;
- compteur `confirmed` revenu à 0 ;
- occurrence restaurée en `overdue` dans la vue active.

## Contrôles statiques

- Compilation Python des fichiers `app/**/*.py` : OK.
- Présence du fichier Plotly local : OK.
- Absence de `.venv` dans l'archive finale : OK.
- Absence de base SQLite personnelle dans l'archive finale : OK.
- Absence de coffre chiffré / clé locale dans l'archive finale : OK.

## Points à vérifier en recette utilisateur

- Parcours UI complet avec sélection du fichier SG depuis le bouton de l'application.
- Affichage exact des diagnostics dans le volet import sur Windows.
- Rapprochement par menus contextuels avec les vraies données de recette.
- Rafraîchissement visuel inter-modules après création d'un compte ou d'une récurrence.
