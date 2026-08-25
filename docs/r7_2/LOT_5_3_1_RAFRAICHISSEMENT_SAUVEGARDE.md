# Lot 5.3.1 — Rafraîchissement sauvegarde/restauration

## Constat recette

Dans `V0.6.6-R7.2.4 Lot 5.3 Sauvegarde complète`, l'utilisateur a constaté que :

- la sauvegarde créée n'était pas affichée immédiatement dans `Paramètres > Sauvegarde` ;
- le panneau `Audit sécurité` restait sur un état ancien ;
- après restauration, il fallait fermer et relancer Valoria Vision pour voir l'état restauré.

## Correction

Le patch `app/r7_2/encrypted_backup_complete_patch.py` a été renforcé :

- mise à jour explicite de `last_backup_path`, `last_backup_encrypted` et dates de traitement ;
- rafraîchissement complet des onglets Paramètres après sauvegarde ;
- rafraîchissement complet après restauration ;
- recalcul immédiat du rapport qualité, de l'audit sécurité et des préférences ;
- remise à jour du panneau latéral ouvert quand il s'agit de l'audit sécurité ou du diagnostic.

## Version visible

`V0.6.6-R7.2.4 Lot 5.3.1 Sauvegarde rafraîchie`

## Recette ciblée

1. Ouvrir `Paramètres > Sauvegarde`.
2. Créer une sauvegarde chiffrée complète.
3. Vérifier immédiatement que `Dernière sauvegarde` n'affiche plus `Aucune`.
4. Cliquer sur `Voir détail sécurité`.
5. Vérifier que `Sauvegardes chiffrées` et `Dernière sauvegarde` sont cohérents.
6. Modifier un paramètre ou une catégorie.
7. Restaurer la sauvegarde.
8. Vérifier que l'écran se rafraîchit sans redémarrage.

## Décision

Correctif requis avant clôture finale du Lot 5.3 et avant passage au Lot 6.
