# Lot 5.3.2 — UX Sauvegarde centralisée

## Contexte

La recette utilisateur de l'écran Paramètres a montré une duplication excessive des actions de sauvegarde/restauration : elles étaient visibles dans les onglets Sauvegarde, Sécurité et Maintenance.

Cette duplication rendait l'organisation fonctionnelle confuse.

## Décision UX

L'onglet **Sauvegarde** devient le seul point d'entrée pour :

- créer une sauvegarde chiffrée complète ;
- restaurer une sauvegarde ;
- consulter l'état de sauvegarde ;
- consulter les dernières sauvegardes connues.

L'onglet **Sécurité** reste dédié à :

- coffre local / vault ;
- clé locale / keyring ;
- mot de passe maître ;
- verrouillage session ;
- audit sécurité.

L'onglet **Maintenance** reste dédié à :

- intégrité SQLite ;
- version de schéma ;
- anomalies techniques ;
- rapport maintenance ;
- socle Premium / évolutivité.

## Corrections réalisées

- Ajout du patch `app/r7_2/settings_backup_ux_patch.py`.
- Retrait des actions sauvegarde/restauration des onglets Sécurité et Maintenance.
- Centralisation des actions dans l'onglet Sauvegarde.
- Ajout d'une section **Dernières sauvegardes effectuées**.
- La liste affiche les 10 dernières sauvegardes `.vvb` connues : date, nom, taille, chemin.
- L'historique est alimenté par `backup_history` et `last_backup_path`.

## Version visible attendue

`V0.6.6-R7.2.4 Lot 5.3.2 UX Sauvegarde centralisée`

## Recette ciblée

1. Ouvrir Paramètres > Sauvegarde.
2. Vérifier que Créer/Restaurer sont présents uniquement dans cet onglet.
3. Créer une sauvegarde chiffrée.
4. Vérifier que l'état de sauvegarde se met à jour immédiatement.
5. Vérifier que la nouvelle sauvegarde apparaît dans **Dernières sauvegardes effectuées**.
6. Ouvrir Paramètres > Sécurité.
7. Vérifier qu'il n'y a plus de bouton Créer/Restaurer.
8. Ouvrir Paramètres > Maintenance.
9. Vérifier qu'il n'y a plus de bouton Créer/Restaurer.
