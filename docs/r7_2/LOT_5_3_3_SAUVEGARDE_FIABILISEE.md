# Lot 5.3.3 — Sauvegarde fiabilisée

## Constat recette

La version Lot 5.3.2 centralise correctement la sauvegarde/restauration dans l’onglet **Sauvegarde**, mais la recette a révélé :

- une erreur Windows `[WinError 32]` lors de la création d’une sauvegarde ;
- un verrou temporaire sur `valoria_vision_snapshot.db` ;
- une liste des dernières sauvegardes visible mais partiellement incohérente si l’écriture échoue.

## Correction

Ajout du patch :

```text
app/r7_2/backup_reliability_patch.py
```

Le patch :

1. crée un snapshot SQLite fermé explicitement ;
2. vérifie l’intégrité du snapshot ;
3. lit le snapshot avec une courte boucle de retry pour contourner les verrous temporaires Windows / OneDrive / antivirus ;
4. chiffre le contenu en mémoire via `encrypt_bytes` ;
5. écrit ensuite le fichier `.vvb` final ;
6. met à jour `last_backup_path`, `last_backup_encrypted`, `last_backup_completed_at` et `backup_history` ;
7. rafraîchit immédiatement l’onglet Sauvegarde.

## Version attendue

```text
V0.6.6-R7.2.4 Lot 5.3.3 Sauvegarde fiabilisée
```

## Recette ciblée

- Créer une sauvegarde depuis Paramètres > Sauvegarde.
- Vérifier l’absence de `WinError 32`.
- Vérifier que la nouvelle sauvegarde apparaît immédiatement dans la liste.
- Vérifier que l’onglet Sécurité ne contient plus Créer/Restaurer.
- Vérifier que l’onglet Maintenance ne contient plus Créer/Restaurer.
- Restaurer une sauvegarde de la liste via le bouton Restaurer.
- Vérifier le rafraîchissement immédiat de l’état sauvegarde.
