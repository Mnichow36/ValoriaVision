# Rapport des modifications — Valoria Vision V0.6.6-R7.2.2 Import Fix

## Objectif

Stabiliser les données d'entrée issues de l'import bancaire avant de poursuivre la recette du module Rapprochements.

## Fichiers modifiés

- `app/imports/import_models.py`
- `app/imports/csv_parser.py`
- `app/theme.py`
- `app/services/money.py`
- `app/ui/transactions_page.py`
- `app/ui/accounts_page.py`
- `app/ui/assets_page.py`
- `app/ui/dashboard_page.py`
- `app/ui/forecast_page.py`
- `app/ui/reconciliation_page.py`
- `app/ui/scenarios_page.py`
- `app/ui/settings_page.py`
- `app/main_window.py`
- `README.md`
- `CHANGELOG_R7_2_2.md`

## Détail technique

### Détection du compte source

Le diagnostic d'import porte maintenant une liste `source_account_identifiers` issue des lignes techniques situées avant l'en-tête CSV et du nom du fichier. Le module Transactions compare ces identifiants aux comptes Valoria existants et bloque l'import si le compte sélectionné est incohérent.

### Libellé enrichi

Le parseur CSV enrichit le libellé normalisé avec le détail bancaire lorsque celui-ci contient une information métier exploitable. Pour les opérations carte Société Générale, les références techniques longues et suffixes `IOPD` sont supprimés du libellé affiché.

### Formats d'affichage

Le formatage monétaire `euro()` affiche désormais toujours deux décimales. Un helper `format_date_fr()` centralise l'affichage des dates en `JJ/MM/AAAA`.

### Filtre période

Dans Transactions, l'ancien menu déroulant de période est remplacé par des sélecteurs calendaires `Du / Au` et un bouton `Toutes dates`.
