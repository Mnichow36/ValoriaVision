from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.imports.bank_profiles import choose_profile
from app.imports.format_detector import FormatDetector
from app.imports.import_models import ImportedTransaction, ImportAnalysis, ImportRejectedLine


class RobustCsvParser:
    def __init__(self) -> None:
        self.detector = FormatDetector()

    def parse(self, path: Path) -> ImportAnalysis:
        structure, diagnostic = self.detector.detect_csv_structure(path)
        analysis = ImportAnalysis(file_name=path.name, diagnostic=diagnostic)
        if structure is None:
            return analysis

        diagnostic.source_account_identifiers = detect_source_account_identifiers(
            structure.lines[:structure.header_index], path.name
        )

        profile = choose_profile(structure.headers)
        mapping = profile.map_headers(structure.headers)
        missing = []
        if not mapping.get("date_operation"):
            missing.append("date")
        if not mapping.get("label"):
            missing.append("libellé")
        if not mapping.get("amount") and not (mapping.get("debit") and mapping.get("credit")):
            missing.append("montant ou débit/crédit")
        if missing:
            diagnostic.stage = "colonnes"
            diagnostic.message = "Colonnes obligatoires manquantes : " + ", ".join(missing)
            return analysis

        data_text = "\n".join(structure.lines[structure.header_index:])
        reader = csv.DictReader(data_text.splitlines(), delimiter=structure.delimiter)
        for offset, row in enumerate(reader, start=structure.header_index + 2):
            if not row or not any(str(v or "").strip() for v in row.values()):
                continue
            try:
                tx = self.row_to_transaction(row, mapping, offset, profile.name)
                analysis.valid_transactions.append(tx)
            except ValueError as exc:
                analysis.rejected_lines.append(ImportRejectedLine(offset, str(exc), dict(row)))
        diagnostic.errors.extend(analysis.rejected_lines)
        diagnostic.message = f"{len(analysis.valid_transactions)} opération(s) reconnue(s)."
        return analysis

    def row_to_transaction(self, row: dict[str, Any], mapping: dict[str, str], line_number: int, profile_name: str) -> ImportedTransaction:
        raw_date = row.get(mapping.get("date_operation", ""), "")
        tx_date = normalize_date(raw_date)
        if not tx_date:
            raise ValueError(f"Date non interprétable : {raw_date!r}")

        raw_label = str(row.get(mapping.get("label", ""), "") or "").strip()
        detail = str(row.get(mapping.get("detail", ""), "") or "").strip()
        label = enrich_label(raw_label, detail, profile_name)
        if not label:
            raise ValueError("Libellé vide")

        amount = extract_amount(row, mapping)
        if amount is None:
            raise ValueError("Montant non interprétable")

        currency = str(row.get(mapping.get("currency", ""), "") or "EUR").strip() or "EUR"
        date_value = normalize_date(row.get(mapping.get("date_valeur", ""), "")) or None
        source_identifier = str(row.get(mapping.get("source_identifier", ""), "") or "").strip() or None
        raw_payload = {str(k): ("" if v is None else str(v)) for k, v in row.items() if k is not None}
        return ImportedTransaction(
            tx_date=tx_date,
            label=label,
            amount=amount,
            category=None,
            detail=detail or None,
            currency=currency,
            source_line=line_number,
            source_profile=profile_name,
            raw_payload=raw_payload,
            date_value=date_value,
            source_identifier=source_identifier,
        )


def extract_amount(row: dict[str, Any], mapping: dict[str, str]) -> float | None:
    if mapping.get("amount"):
        return parse_amount(row.get(mapping["amount"]))
    debit = parse_amount(row.get(mapping.get("debit", ""))) if mapping.get("debit") else 0.0
    credit = parse_amount(row.get(mapping.get("credit", ""))) if mapping.get("credit") else 0.0
    if debit and credit:
        return abs(credit) - abs(debit)
    if credit:
        return abs(credit)
    if debit:
        return -abs(debit)
    return None


def parse_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    text = text.replace("€", "").replace("EUR", "").replace("eur", "")
    text = text.replace("\u202f", "").replace("\xa0", "").replace(" ", "")
    # Formats français: 1.234,56 ou 1234,56
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    cleaned = re.sub(r"[^0-9+\-.]", "", text)
    if cleaned in {"", "+", "-", "."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_date(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value).strip()
    if not text:
        return ""
    if re.match(r"^\d{8}$", text):
        # OFX style YYYYMMDD first; bank CSVs generally contain separators.
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"]
    for fmt in formats:
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def detect_source_account_identifiers(metadata_lines: list[str], file_name: str = "") -> list[str]:
    """Extract reliable account identifiers from pre-header bank metadata.

    Société Générale exports include a technical first line such as
    ="0389000050384255";... while the exported file name may also contain
    00050384255. Both values are useful for account matching. We keep all
    plausible candidates and their long suffixes so Valoria can compare them
    with account identifiers entered by the user.
    """
    candidates: list[str] = []
    sources = list(metadata_lines or []) + [file_name or ""]
    for source in sources:
        for match in re.findall(r"\d{8,}", str(source or "")):
            add_identifier_candidate(candidates, match)
    return candidates


def add_identifier_candidate(candidates: list[str], value: str) -> None:
    digits = re.sub(r"\D+", "", str(value or ""))
    if len(digits) < 8:
        return
    variants = [digits]
    stripped = digits.lstrip("0")
    if stripped and stripped != digits:
        variants.append(stripped)
    # Common French account exports may include bank/branch prefixes. The user
    # usually enters the actual account number, often found at the end.
    for length in (14, 13, 12, 11, 10, 9, 8):
        if len(digits) > length:
            variants.append(digits[-length:])
    for variant in variants:
        if len(variant) >= 8 and variant not in candidates:
            candidates.append(variant)


def enrich_label(raw_label: str, detail: str | None, profile_name: str = "") -> str:
    """Build the business label used for display and automatic rules.

    SG card rows often have a poor label like `CARTE X6425 18/06` while the
    `Détail de l’écriture` column contains the merchant. R7.2.2 keeps the
    original detail in `raw_payload` and exposes an enriched label so users can
    identify and categorize imported operations.
    """
    label = clean_bank_text(raw_label)
    detail_text = clean_bank_text(detail or "")
    if not detail_text:
        return label

    if "société générale" in (profile_name or "").lower() or "societe generale" in (profile_name or "").lower():
        merchant = extract_sg_card_merchant(label, detail_text)
        if merchant:
            return f"{label} — {merchant}" if label else merchant

    if not label:
        return detail_text
    if detail_text.lower() == label.lower():
        return label
    # If the detail contains the label plus useful complementary information,
    # expose the detail directly; otherwise preserve both parts.
    if detail_text.lower().startswith(label.lower()):
        return compact_bank_reference(detail_text)
    return compact_bank_reference(f"{label} — {detail_text}")


def clean_bank_text(value: str | None) -> str:
    text = str(value or "").replace("\xa0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def extract_sg_card_merchant(label: str, detail: str) -> str:
    if not detail or not label.upper().startswith("CARTE"):
        return ""
    suffix = detail
    if label and detail.lower().startswith(label.lower()):
        suffix = detail[len(label):].strip(" -–—")
    suffix = re.sub(r"\b\d{8,}[A-Z]*\b", "", suffix, flags=re.I)
    suffix = re.sub(r"\bIOPD\b", "", suffix, flags=re.I)
    suffix = re.sub(r"\s+", " ", suffix).strip(" -–—")
    return suffix


def compact_bank_reference(text: str) -> str:
    cleaned = re.sub(r"\b\d{10,}[A-Z]*\b", "", text, flags=re.I)
    cleaned = re.sub(r"\bIOPD\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–—")
    return cleaned


def payload_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
