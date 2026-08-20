# V0.6.0 — Socle Premium & évolutivité long terme

## Objectif

Préparer l’application à évoluer sans casser le socle validé V0.4.

Cette version n’active pas encore les fonctions Premium visibles. Elle prépare les fondations techniques.

## Inclus

### Feature flags
Table `feature_flags` :
- `premium.enabled`
- `premium.multi_currency`
- `premium.multi_language`
- `premium.open_banking`
- `premium.cloud_sync`
- `premium.multi_profile`
- modules roadmap : budgets, investissements, rapports

### Multi-devises préparatoire
Table `currencies` :
- EUR activé par défaut
- USD, GBP, CHF, PLN préparés mais non activés

Aucune conversion de change n’est effectuée en V0.6.0.

### Multi-langues préparatoire
Table `translations` :
- premières clés FR
- premières clés EN

L’interface reste française par défaut.

### Métadonnées techniques
Ajout sur les principales tables :
- `uuid`
- `deleted_at`
- `sync_status`
- `external_id`
- `external_source`

Ces champs préparent :
- synchronisation future ;
- Open Banking ;
- exports/imports plus robustes ;
- multi-profils.

### Préférences centralisées
Table `user_preferences` :
- langue par défaut ;
- devise par défaut ;
- mode Premium/Free ;
- device id ;
- préparation Open Banking.

### Audit trail
Table `audit_log` :
- premiers événements techniques ;
- base pour l’audit futur.

## Non inclus en V0.6.0

- pas d’abonnement réel ;
- pas de paiement ;
- pas de multi-devise active ;
- pas de changement de langue UI ;
- pas de connexion bancaire Open Banking ;
- pas de synchronisation cloud.
