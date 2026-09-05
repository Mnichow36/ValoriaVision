# R7.2.5c — P0 Création transaction manuelle

## Constat
Le formulaire Nouvelle transaction s'ouvre, mais la validation peut ne produire aucun résultat visible.

## Issue / PR
- Issue anomalie : #89
- PR correctif : #90

## Qualification Project attendue

### #89 — Issue anomalie
- Status : En cours / Backlog selon état réel de traitement
- Type : Anomalie
- Module principal : Transactions
- Version cible : V0.6.6-R7.2 — Imports & Rapprochements
- Priorité : Critique
- Validation : À retester
- Label : priorité-P0
- Milestone : V0.6.6-R7.2 — Imports & Rapprochements

### #90 — PR correctif
- Status : En cours tant que le correctif n'est pas validé
- Type : Dette technique si le Project ne propose pas Correctif
- Module principal : Transactions
- Version cible : V0.6.6-R7.2 — Imports & Rapprochements
- Priorité : Critique
- Validation : À retester
- Label : priorité-P0
- Milestone : V0.6.6-R7.2 — Imports & Rapprochements

## Correctif visé
- exploiter le booléen retourné par `Database.insert_transaction()` ;
- afficher un message explicite si la transaction est rejetée comme doublon ;
- afficher une confirmation après création réussie ;
- afficher l'exception si l'insertion échoue ;
- sceller immédiatement la base dans le vault chiffré après création manuelle réussie.

## Recette minimale obligatoire
1. Créer une transaction manuelle avec une combinaison compte/date/libellé/montant inédite.
2. Vérifier le message « Transaction enregistrée. ».
3. Vérifier sa présence dans Transactions (désactiver le filtre de période si nécessaire).
4. Redémarrer l'application et vérifier que la transaction est toujours présente.
5. Vérifier l'impact sur le solde du compte.
6. Recréer exactement la même transaction et vérifier le message de doublon sans nouvelle ligne.
7. Modifier la transaction et vérifier la non-régression de l'issue #2.

## Ordre de reprise
P0 création transaction → mini-recette Transactions → issue #49 Rapprochements.

## Point de vigilance
Une issue ou PR Valoria Vision ne doit plus être considérée comme prête au pilotage tant que les champs Project ne sont pas renseignés : Status, Type, Module principal, Version cible, Priorité, Validation.
