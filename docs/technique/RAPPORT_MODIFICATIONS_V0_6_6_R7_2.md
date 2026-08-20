# Rapport des modifications — Valoria Vision V0.6.6-R7.2

## Référentiel utilisé

CDC : `ValoriaVision_CDC_Technique_V0.6.6-R7.2.docx`.

## Arbitrages validés et appliqués

| Point | Décision appliquée |
|---|---|
| Statut Confirmée | Supprimé comme statut de finalisation sans transaction réelle. |
| Statut manuel | `confirmed` = Rapprochée manuellement, uniquement avec transaction liée. |
| Statut automatique | `auto_matched` = Rapprochée automatiquement. |
| Écart / proposition | `to_review` = À vérifier, non considéré comme final pur. |
| Annulation | Libellé et action : `Annuler rapprochement`. |
| Multi-liens | Une occurrence ou transaction déjà liée n'est pas réutilisée pour un rapprochement incompatible. |
| Filtres | Le service construit l'exhaustif puis applique les filtres compte/date/statut. |
| Formats R7.2 | CSV robuste + Société Générale validé ; autres formats conservés en non-régression. |

## Lot A — Import

Fichiers créés :

- `app/imports/import_models.py`
- `app/imports/format_detector.py`
- `app/imports/bank_profiles.py`
- `app/imports/csv_parser.py`
- `tools/test_r7_2_import_sg.py`
- `data/test_fixtures/societe_generale_anonymise_r7_2.csv`

Fichiers modifiés :

- `app/imports/import_service.py`
- `app/imports/__init__.py`
- `app/ui/transactions_page.py`
- `app/database.py`

## Lot B — Rapprochements

Fichiers modifiés :

- `app/services/forecast_reconciliation_service.py`
- `app/ui/reconciliation_page.py`
- `app/database.py`

## Migration

La migration `apply_r7_2_foundation` ajoute :

- `transactions.source_line`
- `transactions.source_profile`
- `transactions.raw_payload`
- `transactions.source_identifier`
- `import_batches.parser_profile`
- `import_batches.source_fingerprint`
- `import_batches.diagnostic_summary`
- `import_batches.header_line`
- `forecast_occurrences.match_type`

Elle transforme aussi les occurrences `planned_confirmed` :

- avec transaction liée : `confirmed` ;
- sans transaction liée : `planned` ou `overdue` selon la date.

Aucune suppression de transaction ou de solde n'est effectuée par cette migration.
