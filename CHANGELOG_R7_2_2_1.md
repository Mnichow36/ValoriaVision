# Valoria Vision V0.6.6-R7.2.2.1 — Crash Fix

## Objet

Correctif immédiat de démarrage après R7.2.2 Import Fix.

## Correction

- `app/ui/reconciliation_page.py` importe maintenant correctement `format_date_fr` depuis `app.theme`.
- Correction du crash au démarrage : `NameError: name 'format_date_fr' is not defined`.

## Impact métier

Aucune règle métier R7.2.2 n'est modifiée.
Le correctif ne touche pas au moteur d'import, aux données, ni aux règles de rapprochement.
