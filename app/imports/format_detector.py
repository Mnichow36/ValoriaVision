from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from app.imports.bank_profiles import choose_profile
from app.imports.import_models import ImportDiagnostic


@dataclass
class CsvStructure:
    text: str
    lines: list[str]
    encoding: str
    delimiter: str
    header_index: int
    headers: list[str]
    profile_name: str


class FormatDetector:
    ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "iso-8859-15", "latin-1")
    DELIMITERS = (";", ",", "\t")

    def decode_text(self, path: Path) -> tuple[str, str]:
        raw = path.read_bytes()
        last_error: Exception | None = None
        for encoding in self.ENCODINGS:
            try:
                return raw.decode(encoding), encoding
            except UnicodeDecodeError as exc:
                last_error = exc
        if last_error:
            return raw.decode("latin-1", errors="replace"), "latin-1/remplacement"
        return raw.decode("utf-8", errors="replace"), "utf-8/remplacement"

    def detect_csv_structure(self, path: Path) -> tuple[CsvStructure | None, ImportDiagnostic]:
        diagnostic = ImportDiagnostic(stage="lecture", format_name="CSV")
        text, encoding = self.decode_text(path)
        lines = text.splitlines()
        diagnostic.encoding = encoding
        if not lines:
            diagnostic.stage = "structure"
            diagnostic.message = "Fichier CSV vide."
            return None, diagnostic

        delimiter = self.detect_delimiter(lines)
        diagnostic.delimiter = delimiter
        header_index, headers = self.find_header_line(lines, delimiter)
        if header_index is None:
            diagnostic.stage = "en-tête"
            diagnostic.message = "En-tête bancaire introuvable. Les colonnes date/libellé/montant n'ont pas été reconnues."
            return None, diagnostic

        profile = choose_profile(headers)
        diagnostic.profile_name = profile.name
        diagnostic.header_line = header_index + 1
        diagnostic.stage = "normalisation"
        diagnostic.message = "Structure CSV reconnue."
        return CsvStructure(text, lines, encoding, delimiter, header_index, headers, profile.name), diagnostic

    def detect_delimiter(self, lines: list[str]) -> str:
        sample_lines = [line for line in lines[:30] if line.strip()]
        scores: dict[str, int] = {}
        for delimiter in self.DELIMITERS:
            counts = [line.count(delimiter) for line in sample_lines]
            scores[delimiter] = max(counts or [0]) + sum(1 for count in counts if count > 0)
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best
        try:
            dialect = csv.Sniffer().sniff("\n".join(sample_lines), delimiters=";,\t")
            return dialect.delimiter
        except csv.Error:
            return ";"

    def find_header_line(self, lines: list[str], delimiter: str) -> tuple[int | None, list[str]]:
        best_index: int | None = None
        best_headers: list[str] = []
        best_score = -1
        for index, line in enumerate(lines[:80]):
            if not line.strip():
                continue
            try:
                row = next(csv.reader([line], delimiter=delimiter))
            except csv.Error:
                continue
            headers = [cell.strip().strip('"') for cell in row]
            if len(headers) < 2:
                continue
            profile = choose_profile(headers)
            score = profile.score_headers(headers)
            # Generic safeguard: a real transaction header must at least expose date + label + amount/debit/credit.
            clean_join = " ".join(h.lower() for h in headers)
            if "date" in clean_join:
                score += 1
            if "montant" in clean_join or "amount" in clean_join or "débit" in clean_join or "credit" in clean_join or "crédit" in clean_join:
                score += 1
            if score > best_score:
                best_score = score
                best_index = index
                best_headers = headers
        if best_index is not None and best_score >= 7:
            return best_index, best_headers
        return None, []
