# Valoria Vision — Lot 5.3
## Sauvegarde chiffrée complète des paramètres

Issue liée : #62 — `[P0][Sauvegarde] Les paramètres ne sont pas restaurés depuis la sauvegarde cryptée`

---

## Constat recette

Après restauration d'une sauvegarde chiffrée dans une installation locale récente, les données métier peuvent être restaurées mais les paramètres applicatifs ne reviennent pas forcément dans l'état attendu.

Ce comportement est bloquant car une sauvegarde chiffrée doit permettre de restaurer un environnement Valoria Vision cohérent, et pas seulement une partie des données visibles.

---

## Décision métier

La sauvegarde chiffrée `.vvb` doit contenir une image SQLite complète et cohérente de la base applicative.

Elle doit inclure notamment :

- paramètres généraux ;
- préférences utilisateur stockées en base ;
- catégories ;
- règles automatiques ;
- scénarios ;
- événements de scénarios ;
- feature flags ;
- devises et traductions ;
- budgets ;
- récurrences ;
- comptes, transactions, imports, patrimoine et occurrences prévisionnelles.

Les secrets locaux et clés de chiffrement restent gérés par le poste local et ne sont pas exportés comme fichiers séparés.

---

## Implémentation

Ajout du patch :

```text
app/r7_2/encrypted_backup_complete_patch.py
```

Le patch ajoute :

- création d'un snapshot SQLite propre via l'API `sqlite3.backup` ;
- checkpoint WAL avant snapshot ;
- contrôle `PRAGMA integrity_check` ;
- manifeste interne des tables de configuration ;
- chiffrement du snapshot complet en `.vvb` ;
- restauration complète avec copie de sécurité préalable ;
- reseal du coffre local chiffré après restauration ;
- raccord de l'écran Paramètres > Sauvegarde aux nouvelles routines.

---

## Tests techniques

Ajout du test :

```text
tools/test_r7_2_complete_encrypted_backup.py
```

Le test vérifie :

- création d'une préférence dans `settings` ;
- création d'une catégorie de test ;
- sauvegarde chiffrée complète ;
- inspection du manifeste ;
- restauration dans une base propre ;
- présence de la préférence restaurée ;
- présence de la catégorie restaurée.

Le test est ajouté au build local Lot 5.3.

---

## Recette utilisateur attendue

1. Modifier un paramètre visible ou une préférence.
2. Modifier/ajouter une catégorie reconnaissable.
3. Créer une sauvegarde chiffrée complète.
4. Restaurer la sauvegarde dans une installation locale propre.
5. Redémarrer l'application.
6. Vérifier que les paramètres et catégories sont restaurés.
7. Vérifier que les données métier sont toujours présentes.

---

## Statut

Développé côté branche `dev/r7.2-cdc-v1.1-imports-rapprochements`.

À vérifier sur build local :

```text
V0.6.6-R7.2.4 Lot 5.3 Sauvegarde complète
```
