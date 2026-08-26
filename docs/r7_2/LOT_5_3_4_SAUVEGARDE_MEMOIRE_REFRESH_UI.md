# Lot 5.3.4 — Sauvegarde mémoire et rafraîchissement UI

## Constat recette

La version Lot 5.3.3 conservait deux anomalies :

1. la création de sauvegarde pouvait encore échouer avec `WinError 32` sur `valoria_vision_snapshot.db` ;
2. certains onglets ne reflétaient les données restaurées qu'après changement d'écran ou nouvelle interaction, notamment :
   - Règles auto ;
   - Dernières sauvegardes effectuées.

## Correction

Le Lot 5.3.4 remplace la sauvegarde par une stratégie sans fichier SQLite temporaire :

- copie SQLite vers une base en mémoire ;
- contrôle d'intégrité en mémoire ;
- sérialisation SQLite en octets ;
- chiffrement direct en mémoire ;
- écriture du fichier `.vvb` final.

Cette approche supprime la dépendance au fichier temporaire `valoria_vision_snapshot.db`, source du verrou Windows.

## Rafraîchissement UI

Après sauvegarde ou restauration, l'écran Paramètres force le rafraîchissement de :

- Sauvegarde ;
- Sécurité ;
- Diagnostic ;
- Cohérence métier ;
- Maintenance ;
- Catégories ;
- Règles auto, via refresh/reload/load_rules si disponible.

## Version

Version visible attendue :

`V0.6.6-R7.2.4 Lot 5.3.4 Sauvegarde mémoire`

## Recette ciblée

1. Créer une sauvegarde chiffrée complète.
2. Vérifier l'absence de WinError 32.
3. Vérifier l'apparition immédiate dans Dernières sauvegardes effectuées.
4. Restaurer une sauvegarde contenant des règles automatiques.
5. Vérifier que Règles auto est visible sans devoir cliquer sur Ajouter une règle.
6. Vérifier que Sécurité et Maintenance ne contiennent toujours pas les actions Créer/Restaurer.
