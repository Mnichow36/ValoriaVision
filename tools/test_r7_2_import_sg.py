from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.imports.import_service import BankImportService


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data' / 'test_fixtures' / 'societe_generale_anonymise_r7_2.csv'
    service = BankImportService()
    analysis = service.analyze(path)
    print('Fichier:', path)
    print('Profil:', analysis.diagnostic.profile_name)
    print('Encodage:', analysis.diagnostic.encoding)
    print('Séparateur:', repr(analysis.diagnostic.delimiter))
    print('En-tête ligne:', analysis.diagnostic.header_line)
    print('Opérations reconnues:', analysis.valid_count)
    print('Lignes rejetées:', len(analysis.rejected_lines))
    if analysis.valid_transactions:
        first = analysis.valid_transactions[0]
        print('Première opération:', first.tx_date, first.label, first.amount, first.currency)
    return 0 if analysis.valid_count > 0 and analysis.diagnostic.header_line else 1


if __name__ == '__main__':
    raise SystemExit(main())
