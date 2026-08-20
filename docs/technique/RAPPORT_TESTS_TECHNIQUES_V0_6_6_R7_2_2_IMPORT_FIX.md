# Rapport de tests techniques — Valoria Vision V0.6.6-R7.2.2 Import Fix

## Tests exécutés

- Compilation Python de tous les fichiers `app/*.py` : OK.
- Analyse du CSV Société Générale réel fourni : OK.
- Nombre d'opérations détectées : 314.
- Lignes rejetées : 0.
- Identifiants de compte détectés : `0389000050384255`, `00050384255`, variantes longues/courtes.
- Libellés carte enrichis : OK.
  - Exemple : `CARTE X6425 18/06 — SC-INTERMARCHE`.
- Format monétaire : `-26,58 €`, `1 200,00 €` : OK.
- Format date : `19/06/2026` : OK.

## Tests UI à rejouer sur poste Windows

- Sélection du CSV SG.
- Vérification du message de compte détecté.
- Blocage si Boursobank est sélectionné alors que le fichier contient un identifiant SG.
- Création ou modification du compte SG avec l'identifiant attendu.
- Import sur le compte cohérent.
- Vérification des libellés enrichis dans la table Transactions.
- Vérification des montants avec deux décimales.
- Vérification du filtre `Du / Au`.
