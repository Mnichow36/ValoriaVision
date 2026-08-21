# Valoria Vision — V0.6.6-R7.2.4 Lot 3
## UX Import, Comptes bancaires et Rapports centralisés

## Nature de la version

Version groupée de recette destinée à valider le Lot 3 du correctif R7.2.

Cette version consolide les correctifs d'import déjà validés en R7.2.3 et ajoute les améliorations UX / comptes / rapports préparées pendant le Lot 3.

Cette version ne correspond pas encore à la livraison complète du CDC R7.2 v1.1.

---

## Périmètre consolidé des lots précédents

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
- Message clair en cas de réimport 100 % doublon.

### Transactions

- Maintien de la cohérence des transactions importées.
- Maintien du contrôle de doublon avant écriture.
- Préparation de la traçabilité technique des décisions d'import.

### Confidentialité / affichage

- Masquage homogène des identifiants de comptes dans les vues sensibles.
- Version visible mise à jour en `V0.6.6-R7.2.4 Lot 3 UX Import Comptes Rapports`.

---

## Nouveautés Lot 3

### UX import

- Ajout d'une fenêtre de progression pendant l'import.
- Affichage des étapes de traitement : préparation, lot d'import, écriture, contrôle, règles automatiques, rapprochement, rafraîchissement, fin.
- Affichage des compteurs pendant le traitement : lignes traitées, importées, doublons, erreurs / rejets.
- Protection contre le double clic pendant le traitement.

### Gestion des comptes bancaires

- Préparation du champ `N° de compte / RIB`.
- Préparation du champ `IBAN` distinct.
- Normalisation des IBAN saisis avec espaces.
- Validation des IBAN internationaux complets selon structure et clé mod 97.
- Maintien de l'ancien champ `identifier` pour compatibilité avec les imports existants.
- Modification contrôlée des champs autorisés : nom, banque, type, N° de compte / RIB, IBAN, devise, statut.
- Protection du solde initial et de la date initiale hors écran dédié.
- Suppression possible des comptes vides.
- Archivage ou blocage des comptes contenant des données liées.

### Rapports centralisés

- Remplacement du placeholder `Rapports` par une première vraie page.
- Consultation des rapports d'import générés dans `data/reports/imports/`.
- Affichage des informations clés : fichier, compte, lignes importées, doublons, erreurs, lignes auditées.
- Actions prévues : ouvrir le rapport et ouvrir le dossier des rapports.

---

## Tests techniques intégrés au build manuel

- `tools/test_r7_2_import_sg.py`
- `tools/test_r7_2_false_duplicate_53.py`
- `tools/test_r7_2_import_report.py`
- `tools/test_r7_2_all_duplicate_import_message.py`
- `tools/test_r7_2_account_management.py`
- `tools/test_r7_2_reports_page.py`

---

## Fichiers principaux concernés

- `app/r7_2/import_integrity.py`
- `app/r7_2/import_report_patch.py`
- `app/r7_2/import_progress_patch.py`
- `app/r7_2/import_ui_feedback_patch.py`
- `app/r7_2/ui_privacy_patch.py`
- `app/r7_2/account_management_patch.py`
- `app/ui/reports_page.py`
- `app/main_window.py`
- `main.py`
- `tools/build_r7_2_3_installable.ps1`
- `docs/r7_2/LOT_3_UX_IMPORT_ET_GESTION_COMPTES.md`
- `docs/r7_2/LOT_3_IMPORT_PROGRESS_IMPLEMENTATION.md`
- `docs/r7_2/LOT_3_RAPPORTS_CENTRALISES.md`
- `docs/r7_2/LOT_3_CONTROLE_TECHNIQUE_GLOBAL.md`

---

## Points à tester en recette ciblée Lot 3

1. Démarrage de l'application.
2. Titre de fenêtre R7.2.4 Lot 3 visible.
3. Identifiants de comptes toujours masqués.
4. Création d'un compte avec N° de compte / RIB et IBAN.
5. Reconnaissance d'IBAN internationaux valides.
6. Modification contrôlée d'un compte sans modifier le solde initial.
7. Suppression d'un compte vide.
8. Blocage ou archivage d'un compte contenant des transactions.
9. Import CSV Société Générale.
10. Affichage de la progression pendant import.
11. Rapport d'import généré après validation.
12. Rapport visible dans le menu Rapports.
13. Réimport identique détecté en 100 % doublon.
14. Cohérence des listes Transactions après import.
15. Annulation d'import à vérifier comme point fonctionnel restant.

---

## Hors périmètre R7.2.4 Lot 3

Les éléments suivants restent à traiter dans les lots suivants :

- annulation d'import complètement durcie ;
- recalculs synchronisés complets après annulation ;
- modèle de rapprochement N↔N ;
- groupes de rapprochement ;
- fiche historique complète ;
- transitions avancées Ignorée / Annulée / Remise à traiter ;
- rollback migration complet ;
- recette complète REC-01 à REC-28 ;
- livraison CDC R7.2 finale.

---

## Statut

Version groupée de recette prévue : **R7.2.4 Lot 3**.

Build automatique désactivé. L'archive doit être générée manuellement uniquement quand le Lot 3 est jugé prêt.
