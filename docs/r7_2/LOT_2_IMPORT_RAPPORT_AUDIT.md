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
- suivi des doublons ;
- base de contrôle avant reprise complète des rapprochements.

---

## Fichiers ajoutés

| Fichier | Rôle |
|---|---|
| `app/r7_2/import_report_patch.py` | Génération automatique d’un rapport texte après mise à jour d’un lot d’import |
| `tools/test_r7_2_import_report.py` | Test technique minimal de génération du rapport |
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
- décision ligne par ligne : `imported` ou `duplicate` ;
- motif de décision ;
- signature technique utilisée.

---

## Limite connue

À ce stade du Lot 2, le rapport consolide les lignes arrivées jusqu’à l’étape d’écriture réelle ou de doublon.

Les lignes rejetées très tôt par l’analyse du fichier sont comptabilisées via `error_count`, mais leur détail ligne par ligne doit encore être enrichi dans une étape suivante.

Cette limite est volontairement documentée pour éviter toute surinterprétation.

---

## Tests associés

| Test | Objet |
|---|---|
| `tools/test_r7_2_import_sg.py` | Vérifie la reconnaissance du fichier SG |
| `tools/test_r7_2_false_duplicate_53.py` | Vérifie la correction du faux doublon #53 |
| `tools/test_r7_2_import_report.py` | Vérifie la génération d’un rapport d’import lisible |

---

## Statut

Statut actuel : **développé côté branche — à vérifier sur prochaine archive installable**.

Recette exhaustive : **reportée après consolidation des correctifs Imports / Transactions**.
