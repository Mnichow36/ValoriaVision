from __future__ import annotations

import re
import unicodedata


def normalize_bank_label(value: str | None) -> str:
    text = value or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_counterparty(label: str | None) -> str:
    """Extract the likely counterparty while preserving the raw bank label elsewhere."""

    raw_label = (label or "").strip()
    if not raw_label:
        return ""

    # Bank exports commonly isolate the merchant after a long dash:
    # "CARTE X7693 05/06 — LIDL 3011".
    segments = re.split(r"\s+(?:—|–|-)\s+", raw_label)
    merchant_segment = segments[-1] if len(segments) > 1 else raw_label
    merchant_segment = re.sub(
        r"\b(?:[A-Za-z]\.){2,}[A-Za-z]?\.?",
        lambda match: match.group(0).replace(".", ""),
        merchant_segment,
    )
    tokens = normalize_bank_label(merchant_segment).split()

    leading_noise = {
        "achat", "cb", "carte", "credit", "de", "debit", "du", "emis",
        "facture", "paiement", "par", "prelevement", "prlv", "recu",
        "retrait", "sepa", "virement", "vir",
    }
    terminal_noise = {
        "cb", "carte", "facture", "fr", "paiement", "ref", "reference",
        "sepa",
    }

    def is_technical(token: str) -> bool:
        if token.isdigit():
            return True
        if re.fullmatch(r"[a-z]{0,3}\d{3,}[a-z0-9]*", token):
            return True
        if re.fullmatch(r"\d+[a-z]+\d*", token):
            return True
        return (
            len(token) >= 8
            and any(ch.isdigit() for ch in token)
            and any(ch.isalpha() for ch in token)
        )

    candidate: list[str] = []
    for token in tokens:
        if not candidate:
            if token in leading_noise or is_technical(token):
                continue
            candidate.append(token)
            continue
        if token in terminal_noise or is_technical(token):
            break
        candidate.append(token)
        if len(candidate) >= 4:
            break

    if candidate:
        return " ".join(candidate).upper()
    return raw_label[:40].upper()
