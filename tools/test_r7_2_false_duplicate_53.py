from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Database
from app.r7_2.import_integrity import apply_r7_2_import_integrity_patch


def main() -> int:
    apply_r7_2_import_integrity_patch()
    with tempfile.TemporaryDirectory(prefix="valoria_r7_2_53_") as tmp:
        db = Database(Path(tmp) / "valoria_test.db")
        db.initialize()
        account_id = int(db.list_accounts()[0]["id"])
        batch_id = db.create_import_batch("sg_53.csv", account_id, parser_profile="Société Générale CSV")

        common = {
            "account_id": account_id,
            "tx_date": "2026-06-19",
            "label": "PRELEVEMENT 7,76",
            "category": None,
            "amount": -7.76,
            "source": "Import bancaire",
            "import_batch_id": batch_id,
            "currency": "EUR",
            "source_profile": "Société Générale CSV",
        }
        first = db.insert_transaction(
            **common,
            source_line=12,
            raw_payload=json.dumps({"Référence": "SG-OP-000001", "Libellé": "PRELEVEMENT 7,76"}, ensure_ascii=False),
            source_identifier="SG-OP-000001",
        )
        second = db.insert_transaction(
            **common,
            source_line=13,
            raw_payload=json.dumps({"Référence": "SG-OP-000002", "Libellé": "PRELEVEMENT 7,76"}, ensure_ascii=False),
            source_identifier="SG-OP-000002",
        )
        duplicate = db.insert_transaction(
            **common,
            source_line=12,
            raw_payload=json.dumps({"Référence": "SG-OP-000001", "Libellé": "PRELEVEMENT 7,76"}, ensure_ascii=False),
            source_identifier="SG-OP-000001",
        )

        with db.connect() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM transactions WHERE import_batch_id = ? AND amount = -7.76",
                (batch_id,),
            ).fetchone()["c"]
            audit = conn.execute(
                "SELECT decision, COUNT(*) AS c FROM import_line_audit WHERE import_batch_id = ? GROUP BY decision ORDER BY decision",
                (batch_id,),
            ).fetchall()

        print("first_inserted:", first)
        print("second_inserted:", second)
        print("third_duplicate_inserted:", duplicate)
        print("stored_transactions_7_76:", count)
        print("audit:", [(row["decision"], row["c"]) for row in audit])

        if not first or not second:
            print("KO: deux opérations légitimes de 7,76 € doivent être conservées.")
            return 1
        if duplicate:
            print("KO: la réimportation de la même référence doit être détectée comme doublon.")
            return 1
        if count != 2:
            print("KO: le nombre de transactions 7,76 € doit être 2.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
