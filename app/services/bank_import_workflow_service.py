from __future__ import annotations

import base64
import binascii
import re
import secrets
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from app.imports.csv_parser import payload_to_json
from app.imports.import_models import ImportAnalysis, ImportedTransaction
from app.imports.import_service import BankImportService
from app.services.categorization_rule_service import CategorizationRuleService


SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".qif", ".ofx"}
MAX_FILE_BYTES = 10 * 1024 * 1024
PREVIEW_TTL = timedelta(minutes=20)
PREVIEW_ROW_LIMIT = 200


@dataclass
class _PendingPreview:
    owner: str
    file_name: str
    analysis: ImportAnalysis
    account_id: int | None
    created_at: datetime


def _field(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key] if key in row.keys() else default
    except (AttributeError, KeyError, TypeError):
        return default


def _identifier_digits(value: str | None) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _mask_identifier(identifier: str | None) -> str:
    compact = _identifier_digits(identifier)
    return f"•••• {compact[-4:]}" if compact else "Identifiant non renseigné"


def _account_matches_identifier(account: Any, identifiers: list[str]) -> bool:
    account_digits = _identifier_digits(_field(account, "identifier", ""))
    if len(account_digits) < 6:
        return False
    for detected in identifiers:
        detected_digits = _identifier_digits(detected)
        if len(detected_digits) < 8:
            continue
        if account_digits == detected_digits:
            return True
        if detected_digits.endswith(account_digits) and len(account_digits) >= 6:
            return True
        if account_digits.endswith(detected_digits) and len(detected_digits) >= 6:
            return True
        rib = account_digits[-23:] if len(account_digits) in (23, 25) else ""
        if rib and rib[10:21].lstrip("0") == detected_digits.lstrip("0"):
            return True
    return False


class BankImportWorkflowService:
    """Session-scoped adapter between React and the existing bank importer.

    The uploaded file only lives in a temporary local file while the historical
    parser runs. The pending preview contains normalized transactions, never the
    original binary payload, and expires automatically.
    """

    def __init__(
        self,
        database: Any,
        *,
        importer_factory: Callable[[], BankImportService] = BankImportService,
        categorizer_factory: Callable[[Any], CategorizationRuleService] = CategorizationRuleService,
        now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.database = database
        self.importer_factory = importer_factory
        self.categorizer_factory = categorizer_factory
        self.now_provider = now_provider
        self._previews: dict[str, _PendingPreview] = {}

    def preview(self, owner: str, file_name: str, content_base64: str, account_id: int | None) -> dict[str, Any]:
        self._cleanup()
        safe_name = Path(str(file_name or "")).name
        suffix = Path(safe_name).suffix.lower()
        if not safe_name or suffix not in SUPPORTED_SUFFIXES:
            raise ValueError("Format non supporté. Utilisez un fichier CSV, XLSX, QIF ou OFX.")
        try:
            content = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Le fichier sélectionné ne peut pas être lu.") from exc
        if not content:
            raise ValueError("Le fichier sélectionné est vide.")
        if len(content) > MAX_FILE_BYTES:
            raise ValueError("Le fichier dépasse la taille maximale de 10 Mo.")

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="valoria-import-", suffix=suffix, delete=False) as handle:
                handle.write(content)
                temporary_path = Path(handle.name)
            analysis = self.importer_factory().analyze(temporary_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        if not analysis.valid_transactions:
            message = analysis.diagnostic.short_message() or "Aucune opération bancaire reconnue."
            raise ValueError(message)

        resolved_account_id, account_ok, account_message = self._resolve_account(analysis, account_id)
        preview_id = secrets.token_urlsafe(24)
        pending = _PendingPreview(
            owner=owner,
            file_name=safe_name,
            analysis=analysis,
            account_id=resolved_account_id,
            created_at=self.now_provider(),
        )
        self._previews[preview_id] = pending
        self._limit_pending_previews()
        return self._render_preview(preview_id, pending, account_ok, account_message)

    def commit(self, owner: str, preview_id: str, account_id: int | None) -> dict[str, Any]:
        pending = self._get_preview(owner, preview_id)
        resolved_account_id, account_ok, account_message = self._resolve_account(pending.analysis, account_id)
        if not account_ok or resolved_account_id is None:
            raise ValueError(account_message or "Sélectionnez un compte bancaire valide.")

        rows = pending.analysis.valid_transactions
        duplicate_flags = [
            self.database.transaction_exists(resolved_account_id, tx.tx_date, tx.label, tx.amount)
            for tx in rows
        ]
        rows_to_import = [tx for tx, duplicate in zip(rows, duplicate_flags) if not duplicate]
        if not rows_to_import:
            raise ValueError("Toutes les opérations reconnues existent déjà sur ce compte.")

        diagnostic = pending.analysis.diagnostic
        batch_id = self.database.create_import_batch(
            pending.file_name,
            resolved_account_id,
            parser_profile=diagnostic.profile_name,
            diagnostic_summary=diagnostic.short_message(),
            header_line=diagnostic.header_line,
        )
        imported = 0
        late_duplicates = 0
        for tx in rows_to_import:
            inserted = self.database.insert_transaction(
                resolved_account_id,
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
            if inserted:
                imported += 1
            else:
                late_duplicates += 1

        duplicate_count = sum(duplicate_flags) + late_duplicates
        error_count = pending.analysis.error_count
        self.database.update_import_batch(batch_id, imported, duplicate_count, error_count)
        categorization = self.categorizer_factory(self.database).apply_rules_to_import_batch(batch_id)
        reconciliation = self.database.reconciliation_summary_for_import_batch(batch_id)
        self._previews.pop(preview_id, None)
        return {
            "success": True,
            "message": f"{imported} opération(s) importée(s).",
            "batchId": batch_id,
            "importedCount": imported,
            "duplicateCount": duplicate_count,
            "errorCount": error_count,
            "categorization": {
                "automatic": int(categorization.get("auto", 0)),
                "toReview": int(categorization.get("to_review", 0)),
                "toCategorize": int(categorization.get("to_categorize", 0)),
            },
            "reconciliation": {
                "automatic": int(reconciliation.get("auto", 0)),
                "toReview": int(reconciliation.get("to_review", 0)),
                "withoutForecast": int(reconciliation.get("without_forecast", 0)),
            },
        }

    def history(self, limit: int = 20) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit or 20), 50))
        rows = list(self.database.list_recent_import_batches(safe_limit))
        return {
            "items": [self._render_batch(row) for row in rows],
            "count": len(rows),
        }

    def cancel(self, batch_id: int) -> dict[str, Any]:
        batch = self.database.get_import_batch(batch_id)
        if batch is None:
            raise KeyError("Lot d’import introuvable.")
        if str(_field(batch, "status", "")) == "Annulé":
            raise ValueError("Ce lot d’import est déjà annulé.")
        deleted = int(self.database.cancel_import_batch(batch_id) or 0)
        return {
            "success": True,
            "message": f"Import annulé : {deleted} opération(s) supprimée(s).",
            "batchId": batch_id,
            "deletedCount": deleted,
        }

    def _render_preview(
        self,
        preview_id: str,
        pending: _PendingPreview,
        account_ok: bool,
        account_message: str,
    ) -> dict[str, Any]:
        account_id = pending.account_id
        rows = pending.analysis.valid_transactions
        duplicate_flags = [
            self.database.transaction_exists(account_id, tx.tx_date, tx.label, tx.amount)
            if account_id is not None else False
            for tx in rows
        ]
        diagnostic = pending.analysis.diagnostic
        return {
            "previewId": preview_id,
            "fileName": pending.file_name,
            "accountId": account_id,
            "accountConsistent": account_ok,
            "accountMessage": account_message,
            "detectedAccounts": [_mask_identifier(value) for value in diagnostic.source_account_identifiers],
            "format": diagnostic.format_name or Path(pending.file_name).suffix.lstrip(".").upper(),
            "profile": diagnostic.profile_name or "Générique",
            "recognizedCount": len(rows),
            "newCount": sum(1 for duplicate in duplicate_flags if not duplicate),
            "duplicateCount": sum(1 for duplicate in duplicate_flags if duplicate),
            "errorCount": pending.analysis.error_count,
            "rowsTruncated": len(rows) > PREVIEW_ROW_LIMIT,
            "rows": [self._render_row(tx, duplicate) for tx, duplicate in zip(rows[:PREVIEW_ROW_LIMIT], duplicate_flags[:PREVIEW_ROW_LIMIT])],
        }

    @staticmethod
    def _render_row(tx: ImportedTransaction, duplicate: bool) -> dict[str, Any]:
        return {
            "date": tx.tx_date,
            "label": tx.label,
            "category": tx.category or "À catégoriser",
            "amount": round(float(tx.amount or 0), 2),
            "currency": tx.currency or "EUR",
            "status": "Doublon" if duplicate else "Nouveau",
            "duplicate": duplicate,
        }

    @staticmethod
    def _render_batch(row: Any) -> dict[str, Any]:
        imported = int(_field(row, "imported_count", 0) or 0)
        duplicates = int(_field(row, "duplicate_count", 0) or 0)
        errors = int(_field(row, "error_count", 0) or 0)
        return {
            "id": int(_field(row, "id", 0) or 0),
            "fileName": str(_field(row, "file_name", "Import bancaire") or "Import bancaire"),
            "accountName": str(_field(row, "account_name", "Compte") or "Compte"),
            "bank": str(_field(row, "bank", "") or ""),
            "accountIdentifier": _mask_identifier(_field(row, "account_identifier", "")),
            "importedCount": imported,
            "duplicateCount": duplicates,
            "errorCount": errors,
            "recognizedCount": imported + duplicates + errors,
            "linkedTransactions": int(_field(row, "linked_transactions", 0) or 0),
            "status": str(_field(row, "status", "") or ""),
            "createdAt": str(_field(row, "created_at", "") or ""),
            "canceledAt": str(_field(row, "canceled_at", "") or ""),
            "parserProfile": str(_field(row, "parser_profile", "") or ""),
        }

    def _resolve_account(self, analysis: ImportAnalysis, requested_id: int | None) -> tuple[int | None, bool, str]:
        accounts = list(self.database.list_accounts())
        selected = next((row for row in accounts if int(_field(row, "id", 0)) == int(requested_id or 0)), None)
        identifiers = list(analysis.diagnostic.source_account_identifiers or [])
        if not identifiers:
            if selected is None:
                return None, False, "Sélectionnez le compte qui recevra les opérations."
            return int(_field(selected, "id", 0)), True, "Compte cible sélectionné manuellement."

        matches = [row for row in accounts if _account_matches_identifier(row, identifiers)]
        shown = ", ".join(_mask_identifier(value) for value in identifiers[:3])
        if len(matches) > 1:
            return None, False, "Plusieurs comptes correspondent à l’identifiant détecté. Vérifiez les comptes avant l’import."
        if not matches:
            return None, False, f"Le relevé indique le compte {shown}, absent des comptes Valoria."
        matched = matches[0]
        matched_id = int(_field(matched, "id", 0))
        return matched_id, True, f"Compte source détecté : {shown}. Compte cible cohérent."

    def _get_preview(self, owner: str, preview_id: str) -> _PendingPreview:
        self._cleanup()
        pending = self._previews.get(preview_id)
        if pending is None or not secrets.compare_digest(pending.owner, owner):
            raise KeyError("Aperçu d’import introuvable ou expiré.")
        return pending

    def _cleanup(self) -> None:
        cutoff = self.now_provider() - PREVIEW_TTL
        expired = [key for key, pending in self._previews.items() if pending.created_at < cutoff]
        for key in expired:
            self._previews.pop(key, None)

    def _limit_pending_previews(self) -> None:
        if len(self._previews) <= 12:
            return
        oldest = sorted(self._previews, key=lambda key: self._previews[key].created_at)
        for key in oldest[:-12]:
            self._previews.pop(key, None)
