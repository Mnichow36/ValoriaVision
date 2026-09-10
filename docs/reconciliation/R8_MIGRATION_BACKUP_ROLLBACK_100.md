# R8 — Validation migration, sauvegarde et retour arrière (#100)

## Résultat

Validation réalisée le 10 septembre 2026 sur un fixture SQLite R7.2 entièrement synthétique.

- suite R8 : **33 tests réussis sur 33** ;
- intégrité avant migration : **OK** ;
- sauvegarde créée et vérifiée avant migration : **OK** ;
- migration R7.2 vers R8 : **OK** ;
- seconde migration sans duplication : **OK** ;
- conservation des tables et données legacy : **OK** ;
- absence de membres orphelins : **OK** ;
- réconciliation des volumes avant/après : **OK** ;
- restauration depuis la sauvegarde : **OK**.

Le rapport machine anonymisé est conservé dans
`docs/reconciliation/reports/R8_100_SYNTHETIC_VALIDATION.json`.

## Périmètre du fixture

Le fixture contient uniquement des données inventées :

- 3 transactions liées ;
- 7 occurrences ;
- 1 lien automatique R7.2 ;
- 1 lien confirmé R7.2 ;
- 1 proposition « À vérifier » ;
- 1 occurrence prévue ;
- 1 occurrence en retard ;
- 1 occurrence ignorée ;
- 1 occurrence annulée.

Une base vide est également validée.

Les formes 1↔1, 1↔N, N↔1 et N↔N sont couvertes par les tests structurels du
modèle de membres, notamment `test_model_supports_many_to_many_membership`.

## Procédure de validation

Exécuter uniquement sur une copie anonymisée ou synthétique :

```bash
python tools/validate_r8_migration.py /chemin/vers/copie_r7_2.db \
  --report /chemin/local/rapport_r8.json
```

Le validateur :

1. refuse les coffres chiffrés et les fichiers non SQLite ;
2. calcule l’empreinte SHA-256 de la source ;
3. crée une sauvegarde temporaire avant toute migration ;
4. vérifie l’intégrité et l’empreinte de cette sauvegarde ;
5. migre une seconde copie temporaire ;
6. exécute deux fois la migration pour contrôler l’idempotence ;
7. compare les volumes et les empreintes des tables legacy ;
8. recherche les membres orphelins ;
9. restaure une troisième copie depuis la sauvegarde ;
10. vérifie l’intégrité et l’identité binaire de la restauration ;
11. supprime automatiquement toutes les copies temporaires.

La base source n’est jamais ouverte en écriture.

## Procédure de retour arrière en exploitation

Avant une migration réelle :

1. fermer Valoria Vision ;
2. réaliser une sauvegarde chiffrée avec la fonction de sauvegarde de
   l’application ;
3. conserver cette sauvegarde hors du répertoire de travail ;
4. vérifier qu’elle est lisible et que son empreinte correspond ;
5. exécuter la migration sur une copie locale anonymisée avant la base cible.

En cas d’échec :

1. ne pas relancer l’application sur la base partiellement migrée ;
2. isoler cette base pour diagnostic ;
3. restaurer la sauvegarde vérifiée à son emplacement d’origine ;
4. exécuter `PRAGMA integrity_check` sur la base restaurée ;
5. relancer l’application seulement si le résultat est `ok`.

## Protection des données

Aucune base SQLite n’est versionnée. Le `.gitignore` exclut désormais
`*.db`, `*.sqlite` et `*.sqlite3`, en complément des coffres et sauvegardes
déjà ignorés.

Le rapport versionné ne contient ni nom de fichier source, ni compte, ni
transaction, ni libellé utilisateur. Son identifiant tronqué provient
uniquement du fixture synthétique.
