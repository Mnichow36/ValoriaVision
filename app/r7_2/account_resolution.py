from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


MIN_STRONG_NUMERIC_LEN = 8
MIN_SUFFIX_LEN = 10
MIN_AMBIGUOUS_SUFFIX_LEN = 6


def normalize_alnum(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()


def normalize_digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def row_value(row: Any, key: str) -> str:
    try:
        if row is not None and key in row.keys():
            return str(row[key] or "")
    except Exception:
        pass
    try:
        return str(row[key] or "")
    except Exception:
        return ""


def unique(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in out:
            out.append(clean)
    return out


def iban_bban_digits(iban: str) -> str:
    clean = normalize_alnum(iban)
    if len(clean) > 4 and re.match(r"^[A-Z]{2}\d{2}", clean):
        return normalize_digits(clean[4:])
    return normalize_digits(clean)


def account_variants(account: Any) -> list[str]:
    """Build matching variants for a Valoria account.

    A bank file can expose only a short account number, a full RIB, a BBAN-like
    numeric payload, or a full IBAN. The application therefore compares the
    detected file identifiers against several normalized variants instead of a
    single historical `identifier` field.
    """
    raw_values = [
        row_value(account, "account_number"),
        row_value(account, "iban"),
        row_value(account, "identifier"),
    ]
    variants: list[str] = []
    for value in raw_values:
        alnum = normalize_alnum(value)
        digits = normalize_digits(value)
        bban_digits = iban_bban_digits(value)
        if alnum:
            variants.append(alnum)
        if digits:
            variants.append(digits)
        if bban_digits and bban_digits != digits:
            variants.append(bban_digits)
        # French BBAN/RIB: bank (5) + branch (5) + account (11) + key (2).
        # Some bank exports expose only the central 11-character account part.
        if len(bban_digits) == 23:
            variants.append(bban_digits[10:21])
        # Useful long suffixes for banks exposing only the account component.
        for size in (23, 18, 16, 14, 12, 11, 10, 8):
            if len(digits) >= size:
                variants.append(digits[-size:])
            if len(bban_digits) >= size:
                variants.append(bban_digits[-size:])
    return unique(variants)


def detected_variants(detected_identifiers: Iterable[str]) -> list[str]:
    variants: list[str] = []
    for detected in detected_identifiers or []:
        alnum = normalize_alnum(detected)
        digits = normalize_digits(detected)
        bban_digits = iban_bban_digits(detected)
        if alnum:
            variants.append(alnum)
        if digits:
            variants.append(digits)
        if bban_digits and bban_digits != digits:
            variants.append(bban_digits)
    return unique(variants)


@dataclass(frozen=True)
class AccountResolutionMatch:
    account: Any
    score: int
    confidence: str
    reason: str
    matched_value: str
    detected_value: str


@dataclass(frozen=True)
class AccountResolutionResult:
    detected_identifiers: list[str]
    matches: list[AccountResolutionMatch]

    @property
    def unique_strong_match(self) -> AccountResolutionMatch | None:
        strong = [m for m in self.matches if m.confidence == "strong"]
        return strong[0] if len(strong) == 1 else None

    @property
    def has_ambiguous_matches(self) -> bool:
        return len(self.matches) > 1

    @property
    def has_match(self) -> bool:
        return bool(self.matches)


def compare_identifier_sets(account_values: list[str], detected_values: list[str]) -> tuple[int, str, str, str, str]:
    """Compare account-side variants with file-side variants.

    Always returns five values, even when there is no match. This prevents the
    import analysis from failing before it can display a clear account message.
    """
    best: tuple[int, str, str, str, str] = (0, "", "", "", "")
    for account_value in account_values:
        account_alnum = normalize_alnum(account_value)
        account_digits = normalize_digits(account_value)
        for detected_value in detected_values:
            detected_alnum = normalize_alnum(detected_value)
            detected_digits = normalize_digits(detected_value)
            if not account_alnum or not detected_alnum:
                continue

            # Exact alphanumeric match, typically full IBAN/RIB/reference.
            if account_alnum == detected_alnum and len(account_alnum) >= MIN_STRONG_NUMERIC_LEN:
                candidate = (100, "strong", "Identifiant complet identique", account_value, detected_value)
            # Exact numeric match, typically account number or RIB digits.
            elif account_digits and detected_digits and account_digits == detected_digits and len(account_digits) >= MIN_STRONG_NUMERIC_LEN:
                candidate = (95, "strong", "Numéro bancaire identique", account_value, detected_value)
            # File exposes a component included in a stored IBAN/RIB.
            elif account_digits and detected_digits and detected_digits in account_digits and len(detected_digits) >= MIN_SUFFIX_LEN:
                candidate = (90, "strong", "Identifiant du fichier inclus dans le RIB/IBAN du compte", account_value, detected_value)
            # Stored account number is included in a full identifier from file.
            elif account_digits and detected_digits and account_digits in detected_digits and len(account_digits) >= MIN_SUFFIX_LEN:
                candidate = (88, "strong", "N° de compte inclus dans l’identifiant du fichier", account_value, detected_value)
            # Long suffix match, useful for banks exposing only account suffixes.
            elif account_digits and detected_digits and account_digits.endswith(detected_digits) and len(detected_digits) >= MIN_SUFFIX_LEN:
                candidate = (82, "strong", "Suffixe bancaire long cohérent", account_value, detected_value)
            elif account_digits and detected_digits and detected_digits.endswith(account_digits) and len(account_digits) >= MIN_SUFFIX_LEN:
                candidate = (80, "strong", "Suffixe bancaire long cohérent", account_value, detected_value)
            # Shorter suffixes are never auto-validating if several accounts match.
            elif account_digits and detected_digits and account_digits.endswith(detected_digits) and len(detected_digits) >= MIN_AMBIGUOUS_SUFFIX_LEN:
                candidate = (55, "candidate", "Suffixe bancaire court à confirmer", account_value, detected_value)
            elif account_digits and detected_digits and detected_digits.endswith(account_digits) and len(account_digits) >= MIN_AMBIGUOUS_SUFFIX_LEN:
                candidate = (52, "candidate", "Suffixe bancaire court à confirmer", account_value, detected_value)
            else:
                candidate = (0, "", "", "", "")

            if candidate[0] > best[0]:
                best = candidate
    return best


def resolve_import_account(accounts: Iterable[Any], detected_identifiers: Iterable[str]) -> AccountResolutionResult:
    detected = unique(str(v or "") for v in detected_identifiers or [] if str(v or "").strip())
    detected_values = detected_variants(detected)
    matches: list[AccountResolutionMatch] = []
    if not detected_values:
        return AccountResolutionResult(detected, [])

    for account in accounts or []:
        variants = account_variants(account)
        score, confidence, reason, matched_value, detected_value = compare_identifier_sets(variants, detected_values)
        if score > 0:
            matches.append(AccountResolutionMatch(account, score, confidence, reason, matched_value, detected_value))

    matches.sort(key=lambda m: m.score, reverse=True)

    # If several accounts match the same detected token strongly, downgrade to
    # candidate to avoid dangerous auto-selection.
    if len([m for m in matches if m.confidence == "strong"]) > 1:
        matches = [
            AccountResolutionMatch(m.account, min(m.score, 60), "candidate", "Correspondance multiple à confirmer", m.matched_value, m.detected_value)
            for m in matches
        ]
    return AccountResolutionResult(detected, matches)
