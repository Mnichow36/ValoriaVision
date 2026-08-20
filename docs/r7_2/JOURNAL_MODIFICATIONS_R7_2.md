# Valoria Vision — R7.2 CDC v1.1
## Journal des modifications techniques

Branche : dev/r7.2-cdc-v1.1-imports-rapprochements  
Base stable : Valoria Vision V0.6.6-R7.2.2.1  
CDC : docs/cdc/Valoria_Vision_R7.2_CDC_correctif_complet.pdf

---

## 1. Objectif

Ce journal sert à suivre toutes les modifications réalisées pendant le développement du correctif complet R7.2.

Chaque changement doit être relié :

- à un lot du CDC ;
- à une exigence ;
- à un fichier modifié ;
- à un test ou une preuve ;
- à une décision si nécessaire.

Aucune modification métier importante ne doit rester non documentée.

---

## 2. Règle de tenue du journal

Pour chaque modification, renseigner :

| Champ | Description |
|---|---|
| Date | Date de la modification |
| Lot | Lot CDC concerné |
| Exigence | Exigence CDC liée |
| Fichier modifié | Fichier ou dossier concerné |
| Nature | Création / modification / suppression / migration / test |
| Résumé | Description courte du changement |
| Test associé | REC ou test technique associé |
| Résultat | Non testé / OK / KO / À reprendre |
| Commentaire | Information complémentaire |

---

## 3. Journal

| Date | Lot | Exigence | Fichier modifié | Nature | Résumé | Test associé | Résultat | Commentaire |
|---|---|---|---|---|---|---|---|---|
| 21/08/2026 | Lot 0 | CDC v1.1 | docs/cdc/Valoria_Vision_R7.2_CDC_correctif_complet.pdf | Création | Ajout du CDC officiel dans le dépôt | N/A | OK | Document de référence du chantier |
| 21/08/2026 | Lot 0 | Lot 0 | docs/r7_2/LOT_0_ETAT_INITIAL.md | Création | Ajout de l’état initial et des règles de sécurisation | N/A | OK | Préparation avant développement |
| 21/08/2026 | Lot 0 | REC-01 à REC-28 | docs/r7_2/MATRICE_REC_01_A_REC_28.md | Création | Ajout de la matrice de recette contractuelle | REC-01 à REC-28 | Non testé | Matrice à compléter pendant le développement |
| 21/08/2026 | Lot 0 | Migration / rollback | docs/r7_2/RAPPORT_MIGRATION_ROLLBACK_R7_2.md | Création | Ajout du rapport de migration, sauvegarde et rollback | REC-26 / REC-27 | Non testé | Contrôles à compléter pendant les lots de migration |
| 21/08/2026 | Lot 0 technique | Audit dépôt | docs/r7_2/LOT_0_AUDIT_TECHNIQUE.md | Création | Audit architecture, modules, migrations, packaging, tests et écarts CDC | N/A | OK | Lot 0 technique terminé |
| 21/08/2026 | Lot 1 | #53 / doublons | app/r7_2/__init__.py | Création | Création du package isolé des correctifs CDC R7.2 | N/A | OK | Préparation des correctifs progressifs |
| 21/08/2026 | Lot 1 | #53 / IMP / AUD | app/r7_2/import_integrity.py | Création | Signature d’import enrichie, discriminants bancaires, table import_line_audit | REC-02 / REC-06 | À exécuter | Test ajouté mais non lancé sur poste Windows |
| 21/08/2026 | Lot 1 | Initialisation correctifs | main.py | Modification | Activation du correctif d’intégrité import avant initialisation de la base | Smoke test | À exécuter | À vérifier au prochain lancement local |
| 21/08/2026 | Lot 1 | REC-02 | tools/test_r7_2_false_duplicate_53.py | Création test | Test technique du faux doublon SG #53 avec deux opérations légitimes de 7,76 € | REC-02 | À exécuter | Attendu : deux lignes conservées, réimport identique rejeté |
| 21/08/2026 | Lot 1 | Documentation | docs/r7_2/LOT_1_IMPORT_INTEGRITE.md | Création | Documentation du correctif Lot 1 et du test #53 | REC-02 | Non testé | Sert de trace d’exigence |

---

## 4. Fichiers sensibles à ne pas modifier sans nécessité

Les fichiers suivants ne doivent être modifiés qu’avec justification explicite :

- app/database.py
- app/services/forecast_reconciliation_service.py
- app/ui/reconciliation_page.py
- app/ui/transactions_page.py
- app/imports/import_service.py
- app/imports/csv_parser.py
- app/imports/format_detector.py
- app/imports/bank_profiles.py
- requirements.txt
- requirements-lock.txt
- build_exe.bat
- install.bat
- run.bat

---

## 5. Fichiers ou dossiers à ne jamais versionner avec des données réelles

Ne jamais ajouter volontairement au dépôt :

- .venv/
- data/valoria_vision.db
- data/secure/
- data/security/
- data/backups/
- fichiers .vvdb
- fichiers .key
- relevés bancaires réels non anonymisés
- exports personnels non anonymisés

---

## 6. Points d’attention

Points à surveiller pendant le développement R7.2 :

- faux doublon SG #53 ;
- contrôle du compte bancaire source ;
- cohérence aperçu / import ;
- audit ligne par ligne ;
- contrôle des soldes ;
- rollback après erreur ;
- transactions manuelles éligibles au rapprochement ;
- absence de double comptage prévu/réalisé ;
- modèle de rapprochement N↔N ;
- scoring automatique explicable ;
- statuts Ignorée / Annulée / Remise à traiter ;
- historique des groupes ;
- synchronisation sans redémarrage ;
- packaging exécutable final.

---

## 7. Statut du journal

Statut actuel :

```text
Mis à jour — Lot 0 technique consigné et Lot 1 engagé. Tests locaux à exécuter.
```
