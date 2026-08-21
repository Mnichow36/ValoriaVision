# Valoria Vision — R7.2 Lot 3
## Contrôle technique global avant archive groupée

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`

---

## Objectif

Consolider les correctifs du Lot 3 avant de décider d'une nouvelle archive installable de recette.

Principe retenu :

- pas de reconstruction à chaque correction mineure ;
- build GitHub Actions déclenché manuellement uniquement ;
- regroupement des correctifs cohérents dans une archive unique ;
- contrôle technique avant livraison utilisateur.

---

## Périmètre Lot 3

### 1. Build manuel uniquement

Le workflow GitHub Actions ne se déclenche plus automatiquement à chaque `push`.

Il doit être lancé manuellement lorsque le lot est prêt.

### 2. Gestion des comptes bancaires

Ajouts prévus côté branche :

- `N° de compte / RIB` ;
- `IBAN` international ;
- normalisation IBAN ;
- devise indépendante de l'IBAN ;
- modification contrôlée des comptes ;
- suppression d'un compte vide ;
- archivage / blocage si données liées ;
- compatibilité avec l'ancien champ `identifier` pour les imports existants.

### 3. Progression visuelle de l'import

Ajouts prévus côté branche :

- fenêtre de progression ;
- étape en cours ;
- fichier traité ;
- compte cible ;
- lignes traitées / total ;
- compteurs importées / doublons / erreurs ;
- protection contre double clic pendant traitement ;
- conservation du rapport et du message final existants.

### 4. Rapports centralisés

Ajouts prévus côté branche :

- remplacement du placeholder `Rapports` par une vraie page ;
- lecture des rapports d'import dans `data/reports/imports/` ;
- affichage date, fichier, compte, importées, doublons, erreurs, lignes auditées ;
- boutons `Ouvrir le rapport` et `Ouvrir le dossier` ;
- état vide lisible si aucun rapport n'existe.

---

## Tests techniques intégrés au build manuel

Le script `tools/build_r7_2_3_installable.ps1` exécute maintenant :

### Tests imports R7.2

- `tools/test_r7_2_import_sg.py`
- `tools/test_r7_2_false_duplicate_53.py`
- `tools/test_r7_2_import_report.py`
- `tools/test_r7_2_all_duplicate_import_message.py`

### Tests Lot 3

- `tools/test_r7_2_account_management.py`
- `tools/test_r7_2_reports_page.py`

---

## Points à vérifier lors de la prochaine archive

### Comptes

- créer un compte avec N° de compte / RIB + IBAN ;
- vérifier le masquage en liste, cartes, détail et import ;
- modifier uniquement les champs autorisés ;
- vérifier que solde initial et date initiale ne changent pas ;
- vérifier les IBAN FR / DE / CH / GB / PL ;
- supprimer un compte vide ;
- tenter de supprimer un compte avec transactions : suppression refusée ou archivage.

### Import

- importer un fichier SG valide ;
- observer la fenêtre de progression ;
- vérifier les étapes et compteurs ;
- vérifier que le double clic import n'est pas possible ;
- vérifier le message final ;
- vérifier que le rapport d'import est généré.

### Rapports

- aller dans `Rapports` après import ;
- vérifier que le rapport d'import apparaît ;
- ouvrir le rapport ;
- ouvrir le dossier ;
- redémarrer l'application et vérifier que le rapport reste visible.

---

## État actuel

Statut : **Lot 3 développé côté branche — build manuel non lancé**.

Décision : ne pas générer d'archive tant que le contrôle du périmètre et les derniers ajustements de documentation ne sont pas validés.
