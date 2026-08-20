# Valoria Vision — R7.2.3 Imports Fix installable

## Objectif

Préparer une première version installable intermédiaire centrée sur :

- imports bancaires ;
- intégrité anti-faux doublons ;
- audit ligne par ligne ;
- transactions ;
- recette ciblée avant reprise complète des rapprochements.

---

## Nom de l’archive prévue

```text
ValoriaVision_INSTALLABLE_V0_6_6_R7_2_3_IMPORTS_FIX.zip
```

---

## Fichiers ajoutés pour la livraison

| Fichier | Rôle |
|---|---|
| `LISEZMOI_R7_2_3_IMPORTS_FIX.txt` | Instructions utilisateur de la version intermédiaire |
| `RELEASE_NOTES_R7_2_3_IMPORTS_FIX.md` | Notes de version |
| `tools/build_r7_2_3_installable.ps1` | Script Windows de fabrication du ZIP installable |
| `.github/workflows/build-r7-2-3-imports-fix.yml` | Workflow GitHub Actions de build automatique |
| `build_exe.bat` | Mis à jour pour appeler le script R7.2.3 |

---

## Contrôles effectués par le script de build

Le script `tools/build_r7_2_3_installable.ps1` doit :

1. installer les dépendances depuis `requirements-lock.txt` ;
2. compiler les fichiers Python avec `compileall` ;
3. exécuter `tools/test_r7_2_import_sg.py` ;
4. exécuter `tools/test_r7_2_false_duplicate_53.py` ;
5. compiler l’application avec PyInstaller ;
6. inclure la ressource locale Plotly ;
7. produire un dossier de release ;
8. générer le ZIP installable ;
9. générer l’empreinte SHA-256.

---

## Statut actuel

Chaîne de build installable : **préparée**.

Archive installable : **à produire par GitHub Actions ou par `build_exe.bat` en local**.

---

## Point de vigilance

La version R7.2.3 est une version intermédiaire.

Elle ne doit pas être fusionnée dans `main` avant recette fonctionnelle.

---

## Recette cible

Tester en priorité :

- démarrage application ;
- import Société Générale ;
- contrôle du compte bancaire source ;
- faux doublon #53 ;
- libellés enrichis ;
- aperçu import ;
- import réel ;
- annulation import ;
- règles automatiques ;
- affichage Transactions.
