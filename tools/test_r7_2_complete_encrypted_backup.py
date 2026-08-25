from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from app.database import Database
from app.r7_2.encrypted_backup_complete_patch import apply_r7_2_encrypted_backup_complete_patch


def main() -> None:
    apply_r7_2_encrypted_backup_complete_patch()

    with tempfile.TemporaryDirectory(prefix="vv_lot53_backup_") as tmp:
        root = Path(tmp)
        db_path = root / "source.db"
        restored_path = root / "restored.db"
        backup_path = root / "complete_backup.vvb"

        db = Database(db_path)
        db.initialize()
        db.set_setting("lot53.preference.test", "restored-ok")
        db.upsert_category({
            "name": "Lot53 Test Catégorie",
            "kind": "Dépense",
            "direction": "Dépense",
            "color": "#123456",
            "budget_enabled": True,
        })
        db.create_complete_encrypted_backup(backup_path)

        manifest = db.encrypted_backup_manifest(backup_path)
        assert manifest["configuration_tables"]["settings"] is not None
        assert manifest["configuration_tables"]["categories"] is not None
        assert manifest["sqlite_integrity"] == "ok"

        restored = Database(restored_path)
        # Reuse the same crypto service in this unit test so the local key can decrypt.
        restored.crypto = db.crypto
        restored.restore_complete_encrypted_backup(backup_path)

        assert restored.get_setting("lot53.preference.test") == "restored-ok"
        categories = [row["name"] for row in restored.list_categories(include_deleted=True)]
        assert "Lot53 Test Catégorie" in categories

    print("OK — Lot 5.3 sauvegarde chiffrée complète restaure paramètres et catégories")


if __name__ == "__main__":
    main()
