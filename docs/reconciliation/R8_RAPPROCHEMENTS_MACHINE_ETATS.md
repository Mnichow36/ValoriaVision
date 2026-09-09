# R8 Rapprochements — Machine à états

**Statut :** validé — fondation R8  
**Validation :** 9 septembre 2026 — issue #120  
**Implémentation partielle :** PR #93 et #97

Ce document sépare explicitement les cycles de vie des **transactions**, **occurrences**, **propositions** et **rapprochements**.

## 1. Principe

Le système R7.2 utilisait le statut de `forecast_occurrences` pour représenter à la fois l'état prévisionnel et l'état du rapprochement. La refonte R8 interdit cette confusion.

## 2. Transaction réelle

La transaction conserve son statut transactionnel propre.

La qualification de rapprochement est portée séparément.

Qualification possible :
- `unclassified` : analyse non exécutée ou à recalculer ;
- `without_forecast` : aucun candidat plausible connu ;
- `has_proposal` : au moins une proposition active ;
- `reconciled` : membre d'un rapprochement actif.

Transitions principales :

```text
unclassified
  ├─> without_forecast
  ├─> has_proposal
  └─> reconciled

without_forecast
  ├─> has_proposal       (nouvelle prévision / réévaluation)
  └─> reconciled         (match automatique certain)

has_proposal
  ├─> without_forecast   (proposition rejetée/expirée sans autre candidat)
  └─> reconciled         (validation)

reconciled
  └─> unclassified       (annulation puis réévaluation)
```

## 3. Occurrence prévisionnelle

États :
- `planned` ;
- `overdue` ;
- `ignored` ;
- `cancelled`.

Transitions :

```text
planned
  ├─> overdue       (date dépassée)
  ├─> ignored       (action utilisateur)
  └─> cancelled     (action utilisateur)

overdue
  ├─> ignored
  └─> cancelled

ignored
  └─> planned|overdue    (remettre à traiter selon la date)

cancelled
  └─> planned|overdue    (réactivation si fonction autorisée)
```

Le rapprochement d'une occurrence n'altère pas nécessairement ce statut ; l'appartenance à un rapprochement est portée par l'objet Rapprochement.

## 4. Proposition de rapprochement

États :
- `proposed` : proposition active ;
- `rejected` : refus utilisateur ;
- `expired` : devenue invalide après changement de données/règles ;
- `converted` : transformée en rapprochement.

Transitions :

```text
proposed
  ├─> rejected
  ├─> expired
  └─> converted
```

Une proposition doit être immuable quant au snapshot de scoring utilisé pour la décision. Un recalcul crée une nouvelle version/proposition ou historise explicitement le recalcul.

## 5. Rapprochement

États :
- `automatic` : rapprochement créé automatiquement ;
- `confirmed` : rapprochement confirmé par l'utilisateur ;
- `cancelled` : rapprochement annulé.

Transitions :

```text
automatic
  └─> cancelled

confirmed
  └─> cancelled
```

Une proposition `proposed` validée devient `converted` et crée un rapprochement `confirmed`.

## 6. Événements d'audit

Les transitions importantes génèrent un événement :
- `qualification_calculated` ;
- `proposal_created` ;
- `proposal_rejected` ;
- `proposal_expired` ;
- `reconciliation_created_auto` ;
- `reconciliation_confirmed` ;
- `reconciliation_cancelled` ;
- `occurrence_ignored` ;
- `occurrence_reactivated` ;
- `occurrence_cancelled` ;
- `occurrence_reactivated_from_cancelled` ;
- `source_changed` ;
- `rules_changed` ;
- `reevaluation_started` ;
- `reevaluation_completed`.

Chaque événement contient au minimum :
- identifiant ;
- type ;
- date/heure ;
- objet concerné ;
- identifiant utilisateur si disponible ;
- raison/motif ;
- données utiles à l'audit.

## 7. Actions UI autorisées selon l'état

| Objet / état | Actions principales |
|---|---|
| Occurrence planned | rapprocher, ignorer, annuler occurrence, détails |
| Occurrence overdue | rapprocher, ignorer, annuler occurrence, détails |
| Occurrence ignored | remettre à traiter, détails |
| Occurrence cancelled | réactiver si autorisé, détails |
| Proposition proposed | valider, rejeter/ignorer, mode manuel, détails |
| Rapprochement automatic | annuler rapprochement, détails |
| Rapprochement confirmed | annuler rapprochement, détails |
| Rapprochement cancelled | détails |

Une action incompatible avec l'état courant ne doit pas être proposée.

## 8. Invariants de transition

1. Une transaction ne peut pas être membre simultanément de rapprochements actifs incompatibles.
2. Un membre ne peut pas être supprimé silencieusement d'un rapprochement.
3. Toute annulation crée une trace d'audit.
4. Toute modification d'une donnée source susceptible d'invalider une décision déclenche une réévaluation.
5. Les filtres d'interface ne déclenchent aucune transition.
