from __future__ import annotations

from pathlib import Path
from typing import Iterable

_PATCHED = False


def apply_r7_2_import_progress_patch() -> None:
    """Add visible progress feedback during bank import validation.

    Lot 3 objective:
    - avoid leaving the user without feedback while an import is processed;
    - show explicit processing steps;
    - show line counters and live import counters;
    - protect against repeated clicks while the import is running.

    The import business rules remain those of the existing TransactionsPage.
    """
    global _PATCHED
    if _PATCHED:
        return

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog
        from app.ui.transactions_page import TransactionsPage
        from app.imports.csv_parser import payload_to_json
        from app.services.categorization_rule_service import CategorizationRuleService
        from app.services.forecast_reconciliation_service import ForecastReconciliationService
    except Exception:
        return

    def _set_progress(dialog: QProgressDialog, value: int, title: str, detail: str = "") -> None:
        dialog.setValue(max(0, min(100, int(value))))
        label = title if not detail else f"{title}\n\n{detail}"
        dialog.setLabelText(label)
        QApplication.processEvents()

    def validate_import_with_progress(self, rows_to_import: Iterable | None = None) -> None:
        selected_rows = list(rows_to_import) if rows_to_import is not None else list(getattr(self, "preview_rows", []) or [])
        if not selected_rows:
            QMessageBox.information(self, "Import", "Aucune opération sélectionnée pour l'import.")
            return

        account_id = self.import_account_combo.currentData()
        if not account_id:
            QMessageBox.warning(self, "Compte manquant", "Sélectionnez un compte bancaire.")
            return
        if not self.ensure_import_account_consistency():
            return

        file_name = getattr(getattr(self, "current_import_path", None), "name", "import")
        account_label = self.import_account_combo.currentText()
        total = len(selected_rows)

        progress = QProgressDialog(self)
        progress.setWindowTitle("Import bancaire en cours")
        progress.setCancelButton(None)
        progress.setMinimum(0)
        progress.setMaximum(100)
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.resize(520, 180)
        progress.show()

        previous_import_enabled = self.import_btn.isEnabled() if hasattr(self, "import_btn") else True
        previous_validate_enabled = self.validate_import_btn.isEnabled() if hasattr(self, "validate_import_btn") else True
        try:
            if hasattr(self, "import_btn"):
                self.import_btn.setEnabled(False)
            if hasattr(self, "validate_import_btn"):
                self.validate_import_btn.setEnabled(False)
            if hasattr(self, "preview_detail_btn"):
                self.preview_detail_btn.setEnabled(False)

            _set_progress(
                progress,
                5,
                "1/8 — Préparation de l'import",
                f"Fichier : {file_name}\nCompte : {account_label}"
            )

            analysis = getattr(self.import_service, "last_analysis", None)
            diagnostic = getattr(analysis, "diagnostic", None)
            errors = len(getattr(analysis, "rejected_lines", []) or []) if analysis else 0

            _set_progress(
                progress,
                15,
                "2/8 — Création du lot d'import",
                f"{total} opération(s) à écrire. Rejets déjà identifiés : {errors}."
            )
            batch_id = self.db.create_import_batch(
                getattr(self, "current_import_path", Path("import")).name,
                account_id,
                parser_profile=getattr(diagnostic, "profile_name", None),
                diagnostic_summary=diagnostic.short_message() if diagnostic else None,
                header_line=getattr(diagnostic, "header_line", None),
            )

            imported = 0
            duplicates = 0

            _set_progress(
                progress,
                25,
                "3/8 — Écriture des opérations",
                f"0 / {total} ligne traitée."
            )
            for index, tx in enumerate(selected_rows, start=1):
                ok = self.db.insert_transaction(
                    account_id,
                    tx.tx_date,
                    tx.label,
                    tx.category,
                    tx.amount,
                    "Import bancaire",
                    batch_id,
                    currency=tx.currency or "EUR",
                    source_line=tx.source_line,
                    source_profile=tx.source_profile,
                    raw_payload=payload_to_json(tx.raw_payload),
                    source_identifier=tx.source_identifier,
                )
                if ok:
                    imported += 1
                else:
                    duplicates += 1

                if total <= 20 or index == total or index % 10 == 0:
                    ratio = index / max(total, 1)
                    value = 25 + int(ratio * 35)
                    _set_progress(
                        progress,
                        value,
                        "3/8 — Écriture des opérations",
                        f"{index} / {total} ligne(s) traitée(s)\n"
                        f"Importées : {imported}  •  Doublons : {duplicates}  •  Rejets : {errors}"
                    )

            _set_progress(
                progress,
                65,
                "4/8 — Contrôle de cohérence du lot",
                f"Importées : {imported}\nDoublons : {duplicates}\nErreurs / rejets : {errors}"
            )
            self.db.update_import_batch(batch_id, imported, duplicates, errors)

            _set_progress(progress, 75, "5/8 — Application des règles automatiques", "Catégorisation du lot importé...")
            categorization_summary = CategorizationRuleService(self.db).apply_rules_to_import_batch(batch_id)

            _set_progress(progress, 85, "6/8 — Rapprochement prévisionnel", "Recherche de correspondances automatiques...")
            reconciliation_summary = ForecastReconciliationService(self.db).reconcile_import_batch(batch_id)

            _set_progress(progress, 92, "7/8 — Rafraîchissement de l'interface", "Mise à jour des listes, compteurs et historique...")
            self.preview_rows = []
            self.current_import_path = None
            self.import_status.setText("Import validé avec catégorisation automatique.")
            self.import_summary.setText(
                f"Nouvelles : {imported}\n"
                f"Doublons : {duplicates}\n"
                f"Auto : {categorization_summary['auto']}\n"
                f"À vérifier : {categorization_summary['to_review']}\n"
                f"À catégoriser : {categorization_summary['to_categorize']}\n"
                f"Rapprochés : {reconciliation_summary['auto']}\n"
                f"Rapp. à vérifier : {reconciliation_summary['to_review']}\n"
                f"Erreurs : {errors}"
            )
            self.refresh()

            _set_progress(progress, 100, "8/8 — Import terminé", "Le traitement est terminé.")
            progress.close()

            QMessageBox.information(
                self,
                "Import terminé",
                f"{imported} opérations importées. {duplicates} doublons ignorés.\n\n"
                f"Catégorisées automatiquement : {categorization_summary['auto']}\n"
                f"À vérifier : {categorization_summary['to_review']}\n"
                f"À catégoriser : {categorization_summary['to_categorize']}\n\n"
                f"Rapprochements automatiques : {reconciliation_summary['auto']}\n"
                f"Rapprochements à vérifier : {reconciliation_summary['to_review']}\n"
                f"Occurrences générées : {reconciliation_summary['generated']}"
            )
        except Exception as exc:
            try:
                _set_progress(progress, 100, "Import interrompu", str(exc))
                progress.close()
            except Exception:
                pass
            QMessageBox.critical(self, "Import impossible", str(exc))
        finally:
            if hasattr(self, "import_btn"):
                self.import_btn.setEnabled(previous_import_enabled)
            if hasattr(self, "validate_import_btn"):
                self.validate_import_btn.setEnabled(False if getattr(self, "current_import_path", None) is None else previous_validate_enabled)
            if hasattr(self, "preview_detail_btn"):
                self.preview_detail_btn.setEnabled(bool(getattr(self, "preview_rows", []) or []))

    TransactionsPage.validate_import = validate_import_with_progress
    _PATCHED = True
