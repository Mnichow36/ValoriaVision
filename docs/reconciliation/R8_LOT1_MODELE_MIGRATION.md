# R8 Rapprochements — Lot 1 technique
## Modèle de données, migration et garde-fous

**Statut :** intégré dans `main`  
**PR :** #93 — fusionnée  
**Commit d’intégration :** `639be23bdb415337431b3741a82ffdded9edeee1`  
**Base fonctionnelle :** PR #92 — fusionnée

## 1. Objectif du lot

Créer le socle de données R8 sans basculer encore le moteur R7.2 ni l'interface.

Le lot doit être installable sur une base existante sans supprimer ni réécrire les transactions réelles.

## 2. Version de schéma

Le schéma passe de **14 à 15**.

La migration R8 est appelée après les migrations R7.2 existantes.

## 3. Nouvelles tables

### transaction_reconciliation_state
État de qualification R8 d'une transaction :
- `unclassified`
- `without_forecast`
- `has_proposal`
- `reconciled`

Au Lot 1, toute transaction sans information legacy exploitable est initialisée à `unclassified`. La qualification réelle `without_forecast` sera produite par le nouveau moteur dans un lot suivant.

### reconciliation_proposals
Porte les propositions non finalisées et leur snapshot de score/règles.

### reconciliation_proposal_members
Porte les transactions et occurrences candidates d'une proposition.

### reconciliations
Porte les rapprochements finalisés :
- `automatic`
- `confirmed`
- `cancelled`

### reconciliation_members
Porte les membres d'un rapprochement et permet nativement :
- 1↔1
- 1↔N
- N↔1
- N↔N

### reconciliation_events
Journal d'audit R8.

## 4. Migration R7.2 → R8

### auto_matched
Création d'un rapprochement R8 `automatic`.

### confirmed
Création d'un rapprochement R8 `confirmed`.

### to_review
Création d'une proposition R8 `proposed`.

### Statuts et colonnes legacy
Ils sont **conservés volontairement**.

Le Lot 1 ne supprime ni ne réinterprète les statuts R7.2 utilisés par le moteur et le prévisionnel actuels.

Cette coexistence est temporaire et protège la compatibilité pendant la refonte.

## 5. Idempotence

Chaque occurrence legacy migrée est référencée par `legacy_occurrence_id`.

Les événements de migration utilisent une clé de déduplication.

Exécuter la migration plusieurs fois ne doit pas multiplier :
- les rapprochements ;
- les propositions ;
- les membres ;
- les événements.

## 6. Garde-fous SQLite

### Unicité des membres actifs
Une transaction ou une occurrence ne peut pas appartenir simultanément à deux rapprochements actifs différents.

Un membre peut être réutilisé après annulation du rapprochement précédent.

### Annulation
Le passage d'un rapprochement à `cancelled` replace ses transactions en `unclassified` afin d'imposer une future réévaluation.

### Suppression d'une transaction source
Avant suppression :
- les rapprochements actifs concernés passent à `cancelled` ;
- les propositions actives passent à `expired` ;
- un événement d'audit est créé avec un snapshot utile de la transaction.

### Suppression d'une occurrence source
Même principe :
- rapprochement annulé ;
- proposition expirée ;
- événement d'audit.

Les relations de membre sont ensuite nettoyées par les contraintes de clé étrangère.

## 7. Tests ajoutés

Le fichier `tests/reconciliation/test_r8_schema.py` couvre actuellement :

1. version de schéma 15 ;
2. création des tables R8 ;
3. état transaction `unclassified` par défaut ;
4. migration d'un rapprochement manuel legacy ;
5. conservation des données transaction/occurrence ;
6. migration d'un rapprochement automatique ;
7. migration d'un `to_review` en proposition ;
8. idempotence de la migration ;
9. représentation N↔N ;
10. contrainte membre transaction/occurrence ;
11. branchement dans `Database.apply_migrations()` ;
12. interdiction de double appartenance active ;
13. libération après annulation ;
14. suppression transaction → annulation + audit ;
15. suppression occurrence → expiration proposition + audit.

## 8. CI

Le workflow :

`.github/workflows/r8-reconciliation-tests.yml`

compile :
- `app/database.py`
- `app/migrations/r8_reconciliation.py`

puis exécute les tests `unittest` R8.

**État au moment de la création du Lot 1 :** aucun run GitHub Actions n'a encore été remonté sur la branche/PR. Les tests sont donc versionnés mais ne doivent pas être déclarés verts avant exécution effective.

## 9. Hors périmètre du Lot 1

- nouveau scoring ;
- règles paramétrables ;
- recherche des candidats ;
- détection d'ambiguïté ;
- qualification automatique `without_forecast` ;
- transaction manuelle → moteur ;
- services Valider / Ignorer / Réactiver / Annuler ;
- UI R8 ;
- bascule du prévisionnel ;
- suppression des colonnes legacy.

## 10. Condition de passage au Lot 2

Avant de démarrer le nouveau moteur :
- valider le schéma ;
- exécuter les tests sur CI ou poste de développement ;
- vérifier une migration sur copie anonymisée d'une base R7.2 ;
- confirmer qu'aucune donnée source n'est altérée ;
- confirmer que les garde-fous de suppression et d'unicité sont acceptés.
