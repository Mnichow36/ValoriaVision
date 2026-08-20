# V0.6.6 — Prévisionnel : graphique combiné crédits / débits / solde

## Objectif

Modifier le graphique principal du Prévisionnel afin d’afficher :

- crédits en colonnes ;
- débits en colonnes ;
- solde cumulé en courbe superposée.

## Service central

Ajout de `app/services/forecast_chart_service.py`.

Méthode principale :

```python
build_cashflow_chart_series(start_date, end_date, account_id=None, scenario_id=None, granularity="month", scenario="Réaliste")
```

Le widget graphique ne recalcule pas les transactions. Il consomme uniquement la série préparée par le service, qui s’appuie sur le moteur existant `cash_forecast()`.

## Compatibilité

- vue quotidienne ;
- vue mensuelle ;
- filtre compte ;
- filtre période ;
- filtre scénario.

## Interactions

- survol : crédits, débits, solde début, solde fin, opérations ;
- clic : ouverture du détail des opérations de la période ;
- clic droit : menu contextuel des récurrences de la période.

## Notes

La version mensuelle agrège les points quotidiens générés par le moteur de prévisionnel afin de conserver la source de vérité métier.
