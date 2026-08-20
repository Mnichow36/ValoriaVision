from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


def clean_header(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", " ").replace("'", " ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


@dataclass(frozen=True)
class ColumnAliases:
    date_operation: tuple[str, ...] = ("date", "date operation", "date de l operation", "date comptable")
    date_valeur: tuple[str, ...] = ("date valeur", "valeur")
    label: tuple[str, ...] = ("libelle", "libelle operation", "description", "operation", "memo", "name")
    detail: tuple[str, ...] = ("detail", "detail de l ecriture", "information", "complement")
    amount: tuple[str, ...] = ("montant", "montant de l operation", "amount", "montant eur", "valeur")
    debit: tuple[str, ...] = ("debit", "sortie", "montant debit")
    credit: tuple[str, ...] = ("credit", "entree", "montant credit")
    currency: tuple[str, ...] = ("devise", "currency", "monnaie")
    source_identifier: tuple[str, ...] = ("reference", "id operation", "identifiant", "numero", "piece")


@dataclass
class BankProfile:
    name: str
    required_any: tuple[str, ...]
    aliases: ColumnAliases = field(default_factory=ColumnAliases)
    delimiter: str | None = None

    def score_headers(self, headers: list[str]) -> int:
        cleaned = [clean_header(h) for h in headers]
        joined = " | ".join(cleaned)
        score = 0
        for needle in self.required_any:
            if clean_header(needle) in joined:
                score += 3
        mapping = self.map_headers(headers)
        if mapping.get("date_operation"):
            score += 5
        if mapping.get("label"):
            score += 4
        if mapping.get("amount") or (mapping.get("debit") and mapping.get("credit")):
            score += 5
        return score

    def map_headers(self, headers: list[str]) -> dict[str, str]:
        cleaned_to_original = {clean_header(h): h for h in headers if str(h or "").strip()}

        def find(candidates: tuple[str, ...]) -> str:
            normalized = [clean_header(c) for c in candidates]
            for candidate in normalized:
                for cleaned, original in cleaned_to_original.items():
                    if candidate == cleaned or candidate in cleaned or cleaned in candidate:
                        return original
            return ""

        return {
            "date_operation": find(self.aliases.date_operation),
            "date_valeur": find(self.aliases.date_valeur),
            "label": find(self.aliases.label),
            "detail": find(self.aliases.detail),
            "amount": find(self.aliases.amount),
            "debit": find(self.aliases.debit),
            "credit": find(self.aliases.credit),
            "currency": find(self.aliases.currency),
            "source_identifier": find(self.aliases.source_identifier),
        }


SOCIETE_GENERALE = BankProfile(
    name="Société Générale CSV",
    required_any=(
        "Date de l'opération",
        "Libellé",
        "Détail de l'écriture",
        "Montant de l'opération",
        "Devise",
    ),
    aliases=ColumnAliases(
        date_operation=("date de l operation", "date de l'opération"),
        label=("libelle", "libellé"),
        detail=("detail de l ecriture", "détail de l'écriture"),
        amount=("montant de l operation", "montant de l'opération"),
        currency=("devise",),
    ),
    delimiter=";",
)

GENERIC_CSV = BankProfile(
    name="CSV générique",
    required_any=("date", "montant"),
)

PROFILES: tuple[BankProfile, ...] = (SOCIETE_GENERALE, GENERIC_CSV)


def choose_profile(headers: list[str]) -> BankProfile:
    scored = sorted(((profile.score_headers(headers), profile) for profile in PROFILES), key=lambda x: x[0], reverse=True)
    if scored and scored[0][0] >= 8:
        return scored[0][1]
    return GENERIC_CSV
