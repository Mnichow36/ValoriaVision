from __future__ import annotations

SUPPORTED_CURRENCIES = {
    "EUR": {"symbol": "€", "label": "Euro", "decimal_places": 2, "position": "after"},
    "USD": {"symbol": "$", "label": "Dollar américain", "decimal_places": 2, "position": "before"},
    "GBP": {"symbol": "£", "label": "Livre sterling", "decimal_places": 2, "position": "before"},
    "CHF": {"symbol": "CHF", "label": "Franc suisse", "decimal_places": 2, "position": "after"},
    "PLN": {"symbol": "zł", "label": "Zloty", "decimal_places": 2, "position": "after"},
}


def normalize_currency(code: str | None) -> str:
    value = (code or "EUR").upper().strip()
    return value if value in SUPPORTED_CURRENCIES else "EUR"


def format_money(value: float, currency: str = "EUR", show_cents: bool = True) -> str:
    """Format money without enabling FX conversion yet.

    V0.6.0 prepares multi-currency display. Amounts remain stored as entered.
    No exchange-rate conversion is performed in this version.
    """

    code = normalize_currency(currency)
    meta = SUPPORTED_CURRENCIES[code]
    decimals = meta["decimal_places"] if show_cents else 0
    number = f"{float(value or 0):,.{decimals}f}".replace(",", " ").replace(".", ",")
    if meta["position"] == "before":
        return f"{meta['symbol']}{number}"
    return f"{number} {meta['symbol']}"
