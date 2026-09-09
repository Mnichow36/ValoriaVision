# ADR — R8 Modèle de données des rapprochements

**Statut :** accepté — fondation R8
**Décision :** séparer occurrences, propositions et rapprochements
**Validation :** 9 septembre 2026 — issue #120
**Implémentation de référence :** PR #93, #94 et #97

## Contexte

Le modèle actuel lie directement une occurrence à une transaction via `forecast_occurrences.actual_transaction_id` et utilise le statut de l'occurrence pour représenter plusieurs notions :
- état prévisionnel ;
- proposition ;
- rapprochement automatique ;
- rapprochement manuel.

Cette structure facilite le cas 1↔1 mais rend difficiles :
- l'ambiguïté avec plusieurs candidats ;
- le N↔N ;
- l'historique ;
- la réversibilité ;
- la séparation « Sans prévision » / « À vérifier » / « Rapprochée » ;
- la cohérence des vues.

## Décision

Introduire des entités dédiées aux propositions, rapprochements, membres et événements.

### 1. `reconciliation_proposals`

Champs indicatifs :
- `id`
- `uuid`
- `status`
- `score`
- `confidence_level`
- `score_details_json`
- `rules_snapshot_json`
- `ambiguity_delta`
- `created_at`
- `updated_at`
- `expires_at`

### 2. `reconciliation_proposal_members`

Permet le N↔N.

Champs indicatifs :
- `id`
- `proposal_id`
- `member_type` = transaction|occurrence
- `transaction_id` nullable
- `occurrence_id` nullable
- `role`
- `amount_snapshot`
- `date_snapshot`

Contrainte : exactement un des identifiants transaction/occurrence est renseigné.

### 3. `reconciliations`

Champs indicatifs :
- `id`
- `uuid`
- `status` = automatic|confirmed|cancelled
- `match_type` = automatic|manual
- `score`
- `score_details_json`
- `rules_snapshot_json`
- `source_proposal_id` nullable
- `created_at`
- `confirmed_at`
- `cancelled_at`
- `cancel_reason`

### 4. `reconciliation_members`

Champs indicatifs :
- `id`
- `reconciliation_id`
- `member_type`
- `transaction_id` nullable
- `occurrence_id` nullable
- `amount_snapshot`
- `date_snapshot`

Cette table rend les groupes 1↔1, 1↔N, N↔1 et N↔N représentables sans modifier le schéma.

### 5. `reconciliation_events`

Journal append-only indicatif :
- `id`
- `uuid`
- `entity_type`
- `entity_id`
- `event_type`
- `reason`
- `payload_json`
- `actor_id` nullable
- `created_at`

### 6. Qualification des transactions

Ajouter une représentation persistante de la qualification de rapprochement, soit :
- colonne dédiée sur `transactions`, soit
- table dédiée `transaction_reconciliation_state`.

Préférence : table dédiée si l'historisation et le recalcul deviennent riches.

Valeurs fonctionnelles :
- `unclassified`
- `without_forecast`
- `has_proposal`
- `reconciled`

## Conséquences

### Positives
- séparation claire des responsabilités ;
- N↔N natif ;
- propositions multiples possibles ;
- audit complet ;
- annulation propre ;
- scoring versionné ;
- vues cohérentes ;
- possibilité de recalculer sans perdre la décision précédente.

### Négatives
- migration plus importante ;
- requêtes plus riches ;
- nécessité d'adapter le prévisionnel et les suppressions.

## Compatibilité R7.2

Les champs actuels `actual_transaction_id`, `match_confidence`, `match_reason` et `match_type` de `forecast_occurrences` deviennent des données héritées.

Migration recommandée :
1. créer les nouvelles tables ;
2. convertir les occurrences `auto_matched` et `confirmed` en rapprochements ;
3. convertir `to_review` en propositions lorsque le lien est cohérent ;
4. conserver les statuts propres `planned`, `overdue`, `ignored`, `cancelled` ;
5. vérifier l'intégrité ;
6. seulement ensuite déprécier les colonnes historiques.

Aucune migration ne doit supprimer une transaction réelle.

## Alternatives rejetées

### Continuer à enrichir `forecast_occurrences.actual_transaction_id`
Rejeté : incompatible naturellement avec N↔N et les propositions multiples.

### Ajouter uniquement une table de liens
Insuffisant : ne traite pas correctement le cycle de vie des propositions, le snapshot de scoring et l'audit.

## Critères d'acceptation de l'ADR

Le modèle final doit permettre sans modification de schéma :
- deux candidats concurrents pour une transaction ;
- un groupe N↔N ;
- l'annulation complète d'un rapprochement ;
- la conservation de l'historique ;
- la réévaluation d'une transaction « Sans prévision » ;
- la consultation du score ayant motivé une décision passée.
