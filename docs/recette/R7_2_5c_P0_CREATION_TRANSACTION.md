# R7.2.5c — P0 Création transaction manuelle

## Constat
Le formulaire Nouvelle transaction s'ouvre, mais la validation peut ne produire aucun résultat visible.

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
