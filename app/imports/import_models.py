from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImportedTransaction:
    """Transaction bancaire normalisée avant écriture définitive.

    Les quatre premiers champs sont volontairement conservés pour rester
    compatibles avec les écrans R7.1. Les champs suivants portent la
    traçabilité R7.2 : profil, ligne source, devise, détail et payload brut.
    """

    tx_date: str
    label: str
    amount: float
    category: str | None = None
    detail: str | None = None
    currency: str | None = "EUR"
    source_line: int | None = None
    source_profile: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    date_value: str | None = None
    source_identifier: str | None = None

    @property
    def direction(self) -> str:
        return "Crédit" if float(self.amount or 0) >= 0 else "Débit"


@dataclass
class ImportRejectedLine:
    line_number: int | None
    reason: str
    raw_payload: dict[str, Any] | str | None = None


@dataclass
class ImportDiagnostic:
    stage: str = "initialisation"
    message: str = ""
    format_name: str = ""
    encoding: str = ""
    delimiter: str = ""
    header_line: int | None = None
    profile_name: str = "Générique"
    source_account_identifiers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[ImportRejectedLine] = field(default_factory=list)

    def short_message(self) -> str:
        details = []
        if self.profile_name:
            details.append(f"Profil : {self.profile_name}")
        if self.encoding:
            details.append(f"Encodage : {self.encoding}")
        if self.delimiter:
            rendered = "tabulation" if self.delimiter == "\t" else self.delimiter
            details.append(f"Séparateur : {rendered}")
        if self.header_line:
            details.append(f"En-tête ligne : {self.header_line}")
        if self.source_account_identifiers:
            shown = ", ".join(self.source_account_identifiers[:3])
            details.append(f"Compte détecté : {shown}")
        if self.message:
            details.append(self.message)
        if self.errors:
            details.append(f"Lignes rejetées : {len(self.errors)}")
        return "\n".join(details) if details else "Analyse terminée."


@dataclass
class ImportAnalysis:
    file_name: str
    valid_transactions: list[ImportedTransaction] = field(default_factory=list)
    rejected_lines: list[ImportRejectedLine] = field(default_factory=list)
    diagnostic: ImportDiagnostic = field(default_factory=ImportDiagnostic)
    duplicate_flags: list[bool] = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        return len(self.valid_transactions)

    @property
    def error_count(self) -> int:
        return len(self.rejected_lines) + len(self.diagnostic.errors)
