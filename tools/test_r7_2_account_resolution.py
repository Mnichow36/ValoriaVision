from __future__ import annotations

from app.r7_2.account_resolution import resolve_import_account, account_variants, compare_identifier_sets


class FakeRow(dict):
    def keys(self):
        return super().keys()


def make_account(account_id: int, name: str, account_number: str = "", iban: str = "", identifier: str = ""):
    return FakeRow({
        "id": account_id,
        "name": name,
        "bank": "Banque Test",
        "account_number": account_number,
        "iban": iban,
        "identifier": identifier,
    })


def test_iban_full_matches_short_sg_account_number():
    account = make_account(
        1,
        "Compte SG",
        iban="FR76 3000 3038 9000 0503 8425 529",
    )
    result = resolve_import_account([account], ["00050384255"])
    assert result.unique_strong_match is not None
    assert result.unique_strong_match.account["id"] == 1
    assert result.unique_strong_match.confidence == "strong"


def test_full_rib_matches_short_account_component():
    account = make_account(
        2,
        "Compte RIB",
        account_number="30003038900005038425529",
    )
    result = resolve_import_account([account], ["00050384255"])
    assert result.unique_strong_match is not None
    assert result.unique_strong_match.account["id"] == 2


def test_full_iban_exact_match_is_strong():
    account = make_account(
        3,
        "Compte IBAN",
        iban="DE89 3704 0044 0532 0130 00",
    )
    result = resolve_import_account([account], ["DE89370400440532013000"])
    assert result.unique_strong_match is not None
    assert result.unique_strong_match.account["id"] == 3


def test_short_ambiguous_suffix_is_not_auto_validated():
    a = make_account(4, "Compte A", account_number="123456789012")
    b = make_account(5, "Compte B", account_number="999956789012")
    result = resolve_import_account([a, b], ["789012"])
    assert result.unique_strong_match is None
    assert result.has_match
    assert all(match.confidence == "candidate" for match in result.matches)


def test_no_identifier_does_not_match():
    account = make_account(6, "Compte vide")
    result = resolve_import_account([account], ["00050384255"])
    assert not result.has_match


def test_no_match_returns_complete_tuple():
    score, confidence, reason, matched_value, detected_value = compare_identifier_sets(["12345678901"], ["99999999999"])
    assert score == 0
    assert confidence == ""
    assert reason == ""
    assert matched_value == ""
    assert detected_value == ""


def test_resolver_never_crashes_on_no_match():
    account = make_account(8, "Compte sans rapport", account_number="12345678901")
    result = resolve_import_account([account], ["99999999999"])
    assert result.unique_strong_match is None
    assert not result.has_match


def test_variants_include_iban_bban_and_suffixes():
    account = make_account(
        7,
        "Compte variantes",
        iban="FR76 3000 3038 9000 0503 8425 529",
    )
    variants = account_variants(account)
    assert "FR7630003038900005038425529" in variants
    assert "30003038900005038425529" in variants
    assert "00050384255" in variants


if __name__ == "__main__":
    test_iban_full_matches_short_sg_account_number()
    test_full_rib_matches_short_account_component()
    test_full_iban_exact_match_is_strong()
    test_short_ambiguous_suffix_is_not_auto_validated()
    test_no_identifier_does_not_match()
    test_no_match_returns_complete_tuple()
    test_resolver_never_crashes_on_no_match()
    test_variants_include_iban_bban_and_suffixes()
    print("OK — résolution comptes multi-banques Lot 3")
