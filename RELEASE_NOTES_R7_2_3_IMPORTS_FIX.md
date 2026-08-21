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
- Création de l'audit ligne par ligne avec table `import_line_audit`.
- Audit des lignes importées, doublonnées et rejetées.
- Génération automatique d'un rapport d'import après validation.
- Affichage utilisateur du chemin du rapport généré.
- Maintien de la détection du compte bancaire source.
- Maintien de l'enrichissement des libellés Société Générale.

### Transactions

- Maintien de la cohérence des transactions importées.
- Maintien du contrôle de doublon avant écriture.
- Préparation de la traçabilité technique des décisions d'import.

### Confidentialité / affichage

- Correction du titre de fenêtre pour afficher `V0.6.6-R7.2.3 Imports Fix`.
- Masquage homogène des identifiants de comptes dans les vues sensibles.

### Tests techniques

- Test ciblé contre le faux doublon #53.
- Test d'import Société Générale existant.
- Test de génération du rapport d'import avec ligne importée et ligne rejetée.

---

## Fichiers principaux concernés

- `app/r7_2/import_integrity.py`
- `app/r7_2/import_report_patch.py`
- `app/r7_2/import_ui_feedback_patch.py`
- `app/r7_2/ui_privacy_patch.py`
- `main.py`
- `tools/test_r7_2_false_duplicate_53.py`
- `tools/test_r7_2_import_report.py`
- `tools/test_r7_2_import_sg.py`
- `docs/r7_2/LOT_1_IMPORT_INTEGRITE.md`
- `docs/r7_2/LOT_2_IMPORT_RAPPORT_AUDIT.md`
- `docs/r7_2/ANOMALIES_R7_2_3_IMPORTS_FIX.md`

---

## Points à tester en recette ciblée

1. Démarrage de l'application.
2. Titre de fenêtre R7.2.3 visible.
3. Identifiants de comptes masqués après création d'un nouveau compte.
4. Import CSV Société Générale.
5. Refus d'un import vers un mauvais compte si l'identifiant source ne correspond pas.
6. Non-fusion de deux opérations légitimes similaires.
7. Détection d'un vrai doublon lors d'un réimport identique.
8. Rapport d'import généré après validation.
9. Ligne importée présente dans le rapport.
10. Ligne rejetée présente dans le rapport si le fichier contient une ligne invalide.
11. Affichage correct des montants et dates.
12. Libellés enrichis sur opérations carte.
13. Annulation d'import.
14. Cohérence avec les règles automatiques.

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

Dernière mise à jour : correctifs Lot 2 — audit d'import, rapport utilisateur, masquage identifiants et libellé de version.
