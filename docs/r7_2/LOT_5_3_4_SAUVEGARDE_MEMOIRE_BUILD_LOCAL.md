# Lot 5.3.4 — Sauvegarde mémoire et build local isolé

## Contexte

Lors de la recette du Lot 5.3.3, deux blocages Windows ont été observés :

1. la création de sauvegarde pouvait échouer avec un verrou temporaire sur le snapshot SQLite ;
2. le build local pouvait échouer lors de la suppression de l'ancien dossier `dist`, notamment sur le fichier `_rust.pyd` de `cryptography`.

Ces blocages sont liés à Windows, OneDrive, l'antivirus ou à une instance encore ouverte de Valoria Vision. Ils ne doivent pas empêcher la recette locale.

## Décision

Le Lot 5.3.4 fiabilise la sauvegarde et le build local :

- sauvegarde SQLite préparée en mémoire afin d'éviter le verrou du fichier snapshot temporaire ;
- chiffrement du contenu en mémoire avant écriture du `.vvb` final ;
- conservation du rafraîchissement immédiat de l'écran Sauvegarde ;
- build local dans des dossiers horodatés isolés ;
- arrêt de la suppression systématique des anciens dossiers `build` et `dist`.

## Version visible attendue

`V0.6.6-R7.2.4 Lot 5.3.4 Sauvegarde mémoire`

## Archive locale attendue

`ValoriaVision_INSTALLABLE_V0_6_6_R7_2_4_LOT5_3_4_SAUVEGARDE_MEMOIRE_<timestamp>.zip`

## Recette ciblée

1. Lancer le build local via `build_local_lot5_2.bat`.
2. Vérifier que le build ne bloque plus sur la suppression de `dist`.
3. Lancer la version générée dans `release`.
4. Vérifier le titre Lot 5.3.4.
5. Dans Paramètres > Sauvegarde, créer une sauvegarde chiffrée.
6. Vérifier l'absence de `WinError 32`.
7. Vérifier l'apparition immédiate de la nouvelle sauvegarde dans la liste.
8. Vérifier que les onglets Sécurité et Maintenance ne contiennent plus d'actions Créer/Restaurer.

## Statut

**VALIDÉ — 26/08/2026**

- le script de build local corrigé est validé ;
- le build local ne doit plus être considéré comme un point ouvert ;
- la sauvegarde/restauration chiffrée du Lot 5.3 a déjà été validée dans `RECETTE_LOT_5_3_3_SAUVEGARDE_FIABILISEE_VALIDEE.md` pour les paramètres, catégories, règles, scénarios et données métier restaurées.

Le Lot 5.3.4 est clôturé. Le développement passe au **Lot 6 — Scénarios paramétrables et impact réel sur le prévisionnel**, rattaché à l'issue #63.
