# Valoria Vision — V0.6.6-R7.2.3 Imports Fix

## Nature de la version

Version intermédiaire installable destinée à la recette ciblée des imports bancaires et des transactions.

Cette version ne correspond pas encore à la livraison complète du CDC R7.2 v1.1.

---

## Périmètre inclus

### Imports bancaires

- Renforcement de la signature technique des transactions importées.
- Prévention du faux doublon SG #53.
- Prise en compte des références bancaires discriminantes lorsque disponibles.
- Prise en compte du payload source bancaire pour distinguer deux opérations similaires.
- Préparation de l'audit ligne par ligne avec table `import_line_audit`.
- Maintien de la détection du compte bancaire source.
- Maintien de l'enrichissement des libellés Société Générale.

### Transactions

- Maintien de la cohérence des transactions importées.
- Maintien du contrôle de doublon avant écriture.
- Préparation de la traçabilité technique des décisions d'import.

### Tests techniques

- Ajout d'un test ciblé contre le faux doublon #53.
- Conservation du test d'import Société Générale existant.

---

## Fichiers principaux concernés

- `app/r7_2/import_integrity.py`
- `app/r7_2/__init__.py`
- `main.py`
- `tools/test_r7_2_false_duplicate_53.py`
- `tools/test_r7_2_import_sg.py`
- `docs/r7_2/LOT_1_IMPORT_INTEGRITE.md`

---

## Points à tester en recette

1. Démarrage de l'application.
2. Import CSV Société Générale.
3. Refus d'un import vers un mauvais compte si l'identifiant source ne correspond pas.
4. Non-fusion de deux opérations légitimes similaires.
5. Détection d'un vrai doublon lors d'un réimport identique.
6. Affichage correct des montants et dates.
7. Libellés enrichis sur opérations carte.
8. Annulation d'import.
9. Cohérence avec les règles automatiques.

---

## Hors périmètre R7.2.3

Les éléments suivants restent à traiter dans les lots suivants :

- modèle de rapprochement N↔N ;
- groupes de rapprochement ;
- fiche historique complète ;
- transitions avancées Ignorée / Annulée / Remise à traiter ;
- rollback migration complet ;
- recette complète REC-01 à REC-28 ;
- livraison CDC R7.2 finale.

---

## Statut

Version de recette intermédiaire : **R7.2.3 Imports Fix**.
