# Points ouverts — Valoria Vision V0.6.6-R7.2

Ces points ne bloquent pas la livraison technique candidate, mais doivent être contrôlés pendant la recette utilisateur.

## 1. Tests UI interactifs Windows

Les tests techniques ont validé le parseur, la base et les services. Les clics réels dans l'interface Windows restent à rejouer pendant la recette.

## 2. Profils bancaires futurs

L'architecture permet d'ajouter d'autres banques, mais R7.2 ne valide officiellement que :

- CSV générique robuste ;
- CSV Société Générale.

## 3. QIF / OFX / XLSX

Ces formats restent supportés par compatibilité historique, mais R7.2 n'ajoute pas de nouvelle promesse fonctionnelle sur ces formats.

## 4. Statut `to_review`

`À vérifier` reste visible dans la vue active. Il ne devient pas une finalisation métier tant qu'un rapprochement n'est pas confirmé ou annulé.

## 5. Suppression / archivage de compte

Le moteur R7.2 respecte les comptes actifs pour la sélection. La politique complète de suppression/archivage de compte reste à traiter dans le module Comptes si nécessaire.
