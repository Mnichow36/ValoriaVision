# Valoria Vision — R7.2.3 Imports Fix
## Lot 2 — Rapport d’import et audit exploitable

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`

---

## Objectif

Renforcer la traçabilité des imports bancaires après validation, en produisant automatiquement un rapport lisible par l’utilisateur et exploitable pour la recette.

Ce lot s’inscrit dans les exigences CDC v1.1 :

- preuve des décisions d’import ;
- cohérence aperçu / écriture réelle ;
- audit des lignes importées ;
- audit des lignes rejetées avant écriture ;
- suivi des doublons ;
- base de contrôle avant reprise complète des rapprochements.

---

## Fichiers ajoutés

| Fichier | Rôle |
|---|---|
| `app/r7_2/import_report_patch.py` | Génération automatique d’un rapport texte après mise à jour d’un lot d’import |
| `tools/test_r7_2_import_report.py` | Test technique de génération du rapport avec ligne importée et ligne rejetée |
| `docs/r7_2/LOT_2_IMPORT_RAPPORT_AUDIT.md` | Documentation du présent lot |

---

## Fichiers modifiés

| Fichier | Modification |
|---|---|
| `main.py` | Activation du patch `apply_r7_2_import_report_patch()` au démarrage |
| `tools/build_r7_2_3_installable.ps1` | Ajout du test `tools/test_r7_2_import_report.py` au build |

---

## Comportement ajouté

Après un import validé, Valoria Vision génère automatiquement un rapport dans :

```text
data/reports/imports/
```

Nom de fichier prévu :

```text
import_batch_00001_nom_du_fichier.txt
```

Le rapport contient :

- identifiant du lot d’import ;
- nom du fichier importé ;
- compte Valoria cible ;
- profil de parsing ;
- compteur importées / doublons / erreurs ;
- total crédits ;
- total débits ;
- solde net importé ;
- lignes auditées ;
- décision ligne par ligne : `imported`, `duplicate` ou `rejected` ;
- motif de décision ;
- signature technique utilisée quand elle existe ;
- payload brut de rejet conservé en base d’audit.

---

## Correction complémentaire ajoutée

Les lignes rejetées par le parseur avant écriture sont maintenant rattachées au lot d’import réel avant génération du rapport.

Avant :

```text
les lignes rejetées étaient comptabilisées mais pas détaillées dans le rapport final
```

Après :

```text
les lignes rejetées apparaissent dans import_line_audit avec decision = rejected
```

Cela permet de distinguer clairement :

- une transaction réellement importée ;
- une transaction ignorée comme doublon ;
- une ligne rejetée pour motif technique ou métier.

---

## Tests associés

| Test | Objet |
|---|---|
| `tools/test_r7_2_import_sg.py` | Vérifie la reconnaissance du fichier SG |
| `tools/test_r7_2_false_duplicate_53.py` | Vérifie la correction du faux doublon #53 |
| `tools/test_r7_2_import_report.py` | Vérifie la génération d’un rapport d’import avec ligne importée et ligne rejetée |

---

## Statut

Statut actuel : **développé côté branche — à vérifier sur prochaine archive installable**.

Recette exhaustive : **reportée après consolidation des correctifs Imports / Transactions**.