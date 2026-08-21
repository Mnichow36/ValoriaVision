from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.r7_2.account_management_patch import (
    apply_r7_2_account_management_patch,
    iban_checksum_valid,
    normalize_iban,
)
from app.database import Database


def main() -> int:
    apply_r7_2_account_management_patch()

    assert normalize_iban("fr76 3000 3038 9000 0503 8425 5") == "FR76300030389000050384255"
    assert iban_checksum_valid("FR76300030389000050384255") is True
    assert iban_checksum_valid("DE89370400440532013000") is True
    assert iban_checksum_valid("CH9300762011623852957") is True
    assert iban_checksum_valid("FR76300030389000050384256") is False

    with tempfile.TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "valoria_accounts_test.db")
        db.initialize()

        db.add_account({
            "name": "Compte test international",
            "bank": "Banque test",
            "account_type": "Compte courant",
            "account_number": "00050384255",
            "iban": "FR76 3000 3038 9000 0503 8425 5",
            "initial_balance": 123.45,
            "initial_date": "2026-08-21",
            "currency": "EUR",
            "status": "Actif",
        })
        accounts = [row for row in db.list_accounts() if row["name"] == "Compte test international"]
        if len(accounts) != 1:
            print("Compte ajouté introuvable")
            return 1
        account = accounts[0]
        if account["account_number"] != "00050384255" or account["iban"] != "FR76300030389000050384255":
            print("RIB/IBAN mal stockés")
            return 1
        if account["identifier"] != "00050384255":
            print("Identifiant de compatibilité import incorrect")
            return 1

        db.update_account_identity(account["id"], {
            "name": "Compte test modifié",
            "bank": "Banque modifiée",
            "account_type": "Compte épargne",
            "account_number": "555666777",
            "iban": "DE89 3704 0044 0532 0130 00",
            "currency": "CHF",
            "status": "Archivé",
        })
        updated = [row for row in db.list_accounts() if row["id"] == account["id"]][0]
        if updated["name"] != "Compte test modifié" or updated["iban"] != "DE89370400440532013000":
            print("Modification identité compte incorrecte")
            return 1
        if float(updated["effective_initial_balance"]) != 123.45 or updated["effective_initial_date"] != "2026-08-21":
            print("Le solde initial a été modifié alors qu'il devait rester inchangé")
            return 1

        result, counts = db.delete_account_if_empty(account["id"])
        if result != "deleted":
            print("Suppression d'un compte vide non effectuée", result, counts)
            return 1

    print("Gestion comptes R7.2 Lot 3 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
