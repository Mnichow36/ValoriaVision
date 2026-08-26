from __future__ import annotations

from app.services.recurring_scope_service import RecurringScopeService


def main() -> None:
    source = {
        "name": "Loyer",
        "scenario": "Optimiste",
        "amount": 1200,
    }
    normalized = RecurringScopeService.normalize_payload(source)

    assert source["scenario"] == "Optimiste"
    assert normalized["scenario"] == "Tous"
    assert normalized["name"] == "Loyer"
    assert normalized["amount"] == 1200
    assert RecurringScopeService.is_common("Tous") is True
    assert RecurringScopeService.is_common("Réaliste") is False

    print("OK - Lot 6.1 : les récurrences standards sont communes aux scénarios")


if __name__ == "__main__":
    main()
