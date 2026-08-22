# Valoria Vision — Lot 4 — Validation recette ciblée

Date de validation utilisateur : 2026-08-22
Version testée : V0.6.6-R7.2.4 Lot 4 Cycle Vie Imports
Archive : ValoriaVision_INSTALLABLE_V0_6_6_R7_2_4_LOT4_CYCLE_VIE_IMPORTS

## Objectif du Lot 4

Valider le cycle de vie complet d'un import bancaire :

1. Importer un fichier bancaire réel.
2. Annuler le lot d'import depuis l'historique des imports.
3. Vérifier que seules les transactions du lot sont supprimées.
4. Réimporter le même fichier après annulation.
5. Vérifier que les transactions réapparaissent correctement.
6. Réimporter une seconde fois sans annulation.
7. Vérifier que le fichier est reconnu en doublons à 100 %.

## Fichier de test

- Fichier : `00050384255.csv`
- Banque : Société Générale
- Compte : SG CC — SG
- Volume attendu : 314 opérations

## Résultat de recette utilisateur

| Contrôle | Résultat |
|---|---:|
| Importer `00050384255.csv` | OK |
| Annuler cet import dans Derniers imports | OK |
| Vérifier que les transactions disparaissent | OK |
| Réimporter le même fichier | OK |
| Vérifier que les transactions reviennent | OK |
| Réimporter encore une fois | OK |
| Vérifier que tout passe en doublons | OK |

## Observations validées par capture

- Le lot importé affiche `Statut : Importé` avec 314 opérations liées.
- Après annulation, le lot affiche `Statut : Annulé` avec 0 opération liée.
- Les transactions SG disparaissent après annulation lorsque le compte SG est filtré.
- Après réimport, 314 transactions SG réapparaissent.
- Un nouvel import du même fichier affiche :
  - `Nouvelles : 0`
  - `Doublons : 314`
  - `Erreurs : 0`
  - message métier `Fichier déjà importé`.

## Décision

La recette ciblée du Lot 4 est validée.

Le périmètre suivant peut être préparé, sous réserve de ne pas rouvrir le Lot 4 sans anomalie bloquante :

- Lot 5 — Prévisionnel / Récurrences
- préparation de la gestion effective du bouton `Gérer les récurrences`
- stabilisation des occurrences prévisionnelles avant rapprochements avancés
