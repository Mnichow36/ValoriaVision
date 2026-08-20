# Valoria Vision — R7.2 CDC v1.1
## Lot 0 — Audit technique du dépôt

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`  
Base stable : `main — Valoria Vision V0.6.6-R7.2.2.1`  
CDC : `docs/cdc/Valoria_Vision_R7.2_CDC_correctif_complet.pdf`

---

## 1. Objectif

Ce document consigne l’audit technique initial réalisé avant tout développement métier du correctif complet R7.2.

Le développement doit se poursuivre lot par lot, dans l’ordre du CDC, sans modifier `main` et sans toucher aux fichiers de référence placés sous `sources/` si ce dossier apparaît ultérieurement.

---

## 2. Architecture technique existante

| Zone | Constat |
|---|---|
| Application | Application desktop Python |
| Interface | PySide6 |
| Base de données | SQLite locale |
| Graphiques | Plotly local via ressources `data/runtime/plotly.min.js` |
| Sécurité locale | Coffre chiffré `.vvdb`, sauvegardes, service crypto |
| Packaging actuel | `install.bat`, `run.bat`, `build_exe.bat` avec PyInstaller |
| Dépendances | Verrouillées dans `requirements-lock.txt` |
| Version de schéma actuelle | `SCHEMA_VERSION = 14` |

---

## 3. Modules localisés

| Domaine CDC | Fichiers principaux identifiés |
|---|---|
| Démarrage | `main.py`, `app/main_window.py` |
| Base / migrations | `app/database.py` |
| Imports | `app/imports/import_service.py`, `csv_parser.py`, `format_detector.py`, `bank_profiles.py`, `import_models.py` |
| Transactions | `app/ui/transactions_page.py`, méthodes transactionnelles dans `app/database.py` |
| Catégorisation | `app/services/categorization_rule_service.py` |
| Prévisionnel / récurrences | `app/ui/forecast_page.py`, `recurring_items`, `forecast_occurrences` |
| Rapprochements | `app/services/forecast_reconciliation_service.py`, `app/ui/reconciliation_page.py` |
| Packaging | `build_exe.bat`, `requirements-lock.txt`, `install.bat`, `run.bat` |
| Tests techniques existants | `tools/test_r7_2_import_sg.py` |

---

## 4. État actuel des imports

Le moteur R7.2.2.1 contient déjà :

- un parseur CSV robuste ;
- un détecteur d’encodage et de séparateur ;
- un profil Société Générale ;
- un modèle `ImportedTransaction` enrichi ;
- une détection d’identifiants de compte source ;
- un aperçu avant import ;
- un blocage si le compte cible est incohérent ;
- une intégration avec les règles automatiques ;
- une intégration avec le rapprochement après import.

Limites constatées par rapport au CDC v1.1 :

| Point | Écart |
|---|---|
| Décision ligne par ligne | Les lignes valides/rejetées sont distinguées, mais il manque une table d’audit persistante complète par ligne. |
| Faux doublon #53 | La signature actuelle dépend de `account_id/date/montant/libellé`, mais n’exploite pas encore suffisamment les références bancaires discriminantes. |
| Aperçu / import | Les deux utilisent le même moteur d’analyse, mais il faut persister les décisions de l’aperçu pour garantir la preuve contractuelle. |
| Atomicité import | L’import écrit ligne par ligne ; il faut sécuriser par transaction atomique explicite et rollback testé. |
| Rapport d’import | Les compteurs existent, mais pas encore de rapport d’audit complet lignes/décisions/motifs. |
| Contrôle de solde | Non identifié comme contrôle obligatoire post-écriture sur transactions réellement enregistrées. |

---

## 5. État actuel des transactions

Constats :

- Les transactions manuelles et importées sont toutes stockées dans `transactions`.
- Les montants sont stockés en `REAL`.
- Les imports enrichissent déjà `source_line`, `source_profile`, `raw_payload`, `source_identifier`.
- La modification de transaction passe par `update_transaction`.

Écarts CDC :

- Les règles de modification non financière doivent être durcies : catégorie/statut/libellé ne doivent jamais modifier montant, signe, date, compte ou identité bancaire.
- La traçabilité de changement de champs critiques doit être auditée.
- Le faux doublon #53 doit empêcher la fusion de deux opérations légitimes similaires.

---

## 6. État actuel du prévisionnel et des récurrences

Constats :

- Les récurrences sont stockées dans `recurring_items`.
- Les occurrences prévisionnelles sont stockées dans `forecast_occurrences`.
- La génération d’occurrences existe dans `ForecastReconciliationService.generate_occurrences`.

Écarts CDC :

- Il faut compléter les transitions de statut : `Ignorée`, `Annulée`, `Remise à traiter`.
- Il faut garantir l’absence de double comptage prévu/réalisé.
- Le CRUD récurrences #55 doit être repris en recette après stabilisation.

---

## 7. État actuel des rapprochements

Constats :

- Le moteur actuel fonctionne encore sur un lien direct `forecast_occurrences.actual_transaction_id`.
- Il supporte principalement le 1↔1.
- L’écran rapprochements affiche transactions et occurrences côte à côte.
- Les menus contextuels existent.
- Les compteurs sont recalculés depuis le dataset.

Écarts CDC majeurs :

| Exigence | Écart actuel |
|---|---|
| Groupe N↔N | Absent. Pas de `ReconciliationGroup`. |
| 1↔N, N↔1, N↔N | Non supportés par le modèle actuel. |
| Historique métier #60 | Très insuffisant : les fiches info affichent seulement l’ID. |
| Annulation groupe #59 | Annulation seulement au niveau occurrence 1↔1. |
| Remise à traiter #58 | Non formalisée comme transition métier complète. |
| Scoring #57 | Scoring existant mais non persisté dans un groupe explicable et paramétrable. |

Conclusion : le CDC impose une évolution de modèle métier, pas seulement une correction UX.

---

## 8. Migrations existantes

Constats :

- Les migrations sont centralisées dans `Database.apply_migrations`.
- La version actuelle est `SCHEMA_VERSION = 14`.
- Les fondations R7.2 ajoutent déjà des colonnes d’import et un nettoyage du statut `planned_confirmed`.

Migrations à prévoir :

- passage à un nouveau numéro de schéma ;
- création de tables d’audit d’import ligne par ligne ;
- création du modèle de groupes de rapprochement ;
- migration des anciens liens 1↔1 vers groupes ;
- index et contraintes d’intégrité ;
- journalisation des transitions de statut ;
- stratégie de rollback documentée et testable.

---

## 9. Packaging et build exécutable

Constats :

- `build_exe.bat` utilise PyInstaller avec `--windowed --name Valoria Vision main.py`.
- Les dépendances verrouillées incluent PyInstaller.
- Le packaging final CDC v1.1 exige un ZIP autonome avec exécutable, ressources, LISEZMOI, notes de version, SHA-256 et rapports.

Écarts :

- Le script build est minimal.
- Il faut vérifier l’inclusion de `data/runtime/plotly.min.js`.
- Il faut produire une procédure de smoke test depuis dossier neuf.
- Il faut produire les rapports LIV-01 à LIV-12.

---

## 10. Tests existants

Test identifié :

- `tools/test_r7_2_import_sg.py`

Limites :

- Test import SG utile mais insuffisant.
- Pas encore de tests REC-01 à REC-28 automatisés.
- Pas de test migration/rollback.
- Pas de test rapprochements N↔N.

Tests à ajouter progressivement :

- tests import ligne par ligne ;
- test faux doublon #53 ;
- test atomicité rollback import ;
- test modification non financière ;
- test transaction manuelle rapprochable ;
- tests groupes 1↔1, 1↔N, N↔1, N↔N ;
- test annulation groupe ;
- test migration anciens liens.

---

## 11. Risques et dépendances

| Risque | Niveau | Mesure prévue |
|---|---:|---|
| Régression import SG | Élevé | Conserver fixture SG et test dédié |
| Faux doublon #53 non corrigé | Critique | Refaire la signature/import audit avec références discriminantes |
| Perte de données migration | Critique | Sauvegarde + migration atomique + rollback |
| Double comptage prévu/réalisé | Critique | Revoir cycle prévu/réalisé avec groupes |
| Rapprochement N↔N incomplet | Critique | Introduire tables de groupes avant UX finale |
| Exécutable incomplet | Élevé | Renforcer build et smoke test ZIP |

---

## 12. Décomposition technique des lots

| Lot | Action technique principale |
|---|---|
| Lot 1 | Reprendre signature/doublons import et corriger #53 |
| Lot 2 | Ajouter audit ligne par ligne, rapport import, contrôle soldes |
| Lot 3 | Ajouter progression import et retours utilisateur |
| Lot 4 | Durcir intégrité Transactions et transactions manuelles éligibles |
| Lot 5 | Stabiliser prévisionnel/récurrences/statuts/double comptage |
| Lot 6 | Introduire modèle `ReconciliationGroup` N↔N |
| Lot 7 | Scoring déterministe, paramétrable, explicable |
| Lot 8 | Cycle statuts, remise à traiter, annulation, historique |
| Lot 9 | Filtres et UX rapprochements |
| Lot 10 | Synchronisation transversale sans redémarrage |
| Lot 11 | Non-régression, migration, rollback, package final |

---

## 13. Décision de sortie Lot 0 technique

Le Lot 0 technique confirme :

- le dépôt est accessible ;
- la branche de développement est active ;
- les modules concernés sont localisés ;
- les écarts CDC sont identifiés ;
- le développement doit commencer par le Lot 1 Import/Doublons, sans refondre immédiatement l’UX rapprochements.

Statut : **Lot 0 technique terminé — prêt pour Lot 1**.
