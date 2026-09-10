from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Pattern introuvable pour {label}")
    return text.replace(old, new, 1)


repo = Path(__file__).resolve().parents[1]
ui_path = repo / "app" / "ui" / "transactions_page.py"
db_path = repo / "app" / "database.py"

ui = ui_path.read_text(encoding="utf-8")
db = db_path.read_text(encoding="utf-8")

old_ui = '''        if dialog.exec() == QDialog.Accepted:\n            data = dialog.data()\n            self.db.insert_transaction(\n                data["account_id"],\n                data["tx_date"],\n                data["label"],\n                data["category"],\n                data["amount"],\n                "Manuel",\n            )\n            self.refresh()\n'''

new_ui = '''        if dialog.exec() == QDialog.Accepted:\n            data = dialog.data()\n            try:\n                inserted = self.db.insert_transaction(\n                    data["account_id"],\n                    data["tx_date"],\n                    data["label"],\n                    data["category"],\n                    data["amount"],\n                    "Manuel",\n                )\n                if not inserted:\n                    QMessageBox.warning(\n                        self,\n                        "Nouvelle transaction",\n                        "Cette opération existe déjà pour ce compte, cette date, ce montant et ce libellé.\\n\\n"\n                        "Aucune nouvelle transaction n'a été créée.",\n                    )\n                    return\n                self.refresh()\n                QMessageBox.information(self, "Nouvelle transaction", "Transaction enregistrée.")\n            except Exception as exc:\n                QMessageBox.critical(\n                    self,\n                    "Nouvelle transaction",\n                    f"Impossible d'enregistrer la transaction.\\n\\n{exc}",\n                )\n'''
ui = replace_once(ui, old_ui, new_ui, "UI création transaction")

old_db = '''            conn.execute(\n                """\n                INSERT INTO transactions(account_id, tx_date, label, category, amount, tx_type, status, source, import_batch_id, signature,\n                                         categorization_status, categorized_by, categorization_rule_id, categorized_at,\n                                         currency, source_line, source_profile, raw_payload, source_identifier)\n                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)\n                """,\n                (account_id, tx_date, label, category, amount, tx_type, status, source, import_batch_id, signature,\n                 categorization_status, categorized_by, categorized_at,\n                 currency or 'EUR', source_line, source_profile, raw_payload, source_identifier),\n            )\n            return True\n'''

new_db = '''            conn.execute(\n                """\n                INSERT INTO transactions(account_id, tx_date, label, category, amount, tx_type, status, source, import_batch_id, signature,\n                                         categorization_status, categorized_by, categorization_rule_id, categorized_at,\n                                         currency, source_line, source_profile, raw_payload, source_identifier)\n                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)\n                """,\n                (account_id, tx_date, label, category, amount, tx_type, status, source, import_batch_id, signature,\n                 categorization_status, categorized_by, categorized_at,\n                 currency or 'EUR', source_line, source_profile, raw_payload, source_identifier),\n            )\n        self.seal_database_to_encrypted_vault()\n        return True\n'''
db = replace_once(db, old_db, new_db, "persistance vault création transaction")

ui_path.write_text(ui, encoding="utf-8")
db_path.write_text(db, encoding="utf-8")

print("Patch R7.2.5c appliqué : création transaction + retour utilisateur + persistance vault")
