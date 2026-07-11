from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Mapping, Any


LIQUID_ACCOUNT_TYPES = {"Compte courant", "Compte épargne"}
INVESTMENT_ACCOUNT_TYPES = {"Compte investissement"}
DEBT_ACCOUNT_TYPES = {"Compte crédit"}
EXCLUDED_EXPENSE_CATEGORIES = {"Transferts", "Investissement"}
INCOME_CATEGORY_EXCLUSIONS = {"Transferts", "Investissement"}


@dataclass(frozen=True)
class AccountBalance:
    """Balance snapshot for a given account and date.

    Core rule:
    balance at date = initial balance + all transactions strictly after
    the initial date and up to the observed date.

    Before the initial date, the account is considered not active yet and
    therefore returns a calculated balance of 0.
    """

    initial_balance: float
    initial_date: str
    target_date: str
    movements: float
    calculated_balance: float
    calculated_date: str


def _date(value: str):
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _get(row: Any, key: str, default=None):
    """Read a value from dict-like mappings and sqlite3.Row objects."""

    if row is None:
        return default
    if hasattr(row, "get"):
        return row.get(key, default)
    try:
        if hasattr(row, "keys") and key not in row.keys():
            return default
        return row[key]
    except Exception:
        return default


def balance_at_date(
    initial_balance: float,
    initial_date: str,
    transactions: Iterable[Mapping],
    target_date: str,
) -> AccountBalance:
    """Calculate the account balance at any historical or current date.

    A transaction is included when:
    initial_date < transaction_date <= target_date

    This avoids double counting transactions that were already included in the
    initial balance.
    """

    initial_balance = float(initial_balance or 0)
    initial_date = str(initial_date)
    target_date = str(target_date)

    if _date(target_date) < _date(initial_date):
        return AccountBalance(
            initial_balance=initial_balance,
            initial_date=initial_date,
            target_date=target_date,
            movements=0.0,
            calculated_balance=0.0,
            calculated_date=target_date,
        )

    movements = 0.0
    calculated_date = initial_date
    for tx in transactions:
        tx_date = str(_get(tx, "tx_date", _get(tx, "date", "")) or "")
        if not tx_date:
            continue
        amount = float(_get(tx, "amount", 0) or 0)
        if initial_date < tx_date <= target_date:
            movements += amount
            if tx_date > calculated_date:
                calculated_date = tx_date

    return AccountBalance(
        initial_balance=initial_balance,
        initial_date=initial_date,
        target_date=target_date,
        movements=movements,
        calculated_balance=initial_balance + movements,
        calculated_date=calculated_date,
    )


def current_balance(
    initial_balance: float,
    initial_date: str,
    transactions: Iterable[Mapping],
    as_of_date: str,
) -> AccountBalance:
    """Current balance is the balance at the chosen observation date."""

    return balance_at_date(initial_balance, initial_date, transactions, as_of_date)


def balance_series(
    initial_balance: float,
    initial_date: str,
    transactions: Iterable[Mapping],
    start_date: str,
    end_date: str,
) -> list[AccountBalance]:
    """Return one balance snapshot per day between two dates included."""

    start = _date(start_date)
    end = _date(end_date)
    tx_rows = list(transactions)
    snapshots: list[AccountBalance] = []
    day = start
    while day <= end:
        snapshots.append(balance_at_date(initial_balance, initial_date, tx_rows, day.isoformat()))
        day += timedelta(days=1)
    return snapshots


def summarize_accounts_at_date(accounts: Iterable[Mapping], transactions_by_account: Mapping[int, Iterable[Mapping]], target_date: str) -> dict[str, float]:
    """Summarize account balances by business family at a date."""

    summary = {
        "solde_net": 0.0,
        "liquidites": 0.0,
        "epargne": 0.0,
        "investissements": 0.0,
        "dettes": 0.0,
        "comptes_courants": 0.0,
    }
    for account in accounts:
        if _get(account, "status") != "Actif":
            continue
        account_id = int(_get(account, "id"))
        typ = _get(account, "account_type")
        initial_balance = _get(account, "initial_balance", _get(account, "reference_balance", 0))
        initial_date = _get(account, "initial_date", _get(account, "reference_date"))
        snapshot = balance_at_date(initial_balance, initial_date, transactions_by_account.get(account_id, []), target_date)
        total = snapshot.calculated_balance
        summary["solde_net"] += total
        if typ == "Compte courant":
            summary["liquidites"] += total
            summary["comptes_courants"] += total
        elif typ == "Compte épargne":
            summary["liquidites"] += total
            summary["epargne"] += total
        elif typ == "Compte investissement":
            summary["investissements"] += total
        elif typ == "Compte crédit":
            summary["dettes"] += abs(total)
    return summary


def is_liquid_account(account_type: str) -> bool:
    return account_type in LIQUID_ACCOUNT_TYPES


def is_investment_account(account_type: str) -> bool:
    return account_type in INVESTMENT_ACCOUNT_TYPES


def is_debt_account(account_type: str) -> bool:
    return account_type in DEBT_ACCOUNT_TYPES


def is_true_income(category: str | None, amount: float) -> bool:
    """True income is intentionally strict.

    V0.4.13 business rule from recette:
    a positive amount is counted as income only when it is explicitly
    categorized as "Revenus". A credit categorized as a spending category must
    not inflate income KPIs.
    """

    return amount > 0 and (category or "") == "Revenus"


def is_current_expense(category: str | None, amount: float) -> bool:
    """Current expense excludes transfers and investments."""

    return amount < 0 and (category or "") not in EXCLUDED_EXPENSE_CATEGORIES


def is_uncategorized_transaction(category: str | None, status: str | None) -> bool:
    """Rule used by Transactions > À catégoriser.

    A transaction must appear in the tab if:
    - status is "À catégoriser";
    - category is empty;
    - category is explicitly "À catégoriser".
    """

    category_value = (category or "").strip()
    status_value = (status or "").strip()
    return status_value == "À catégoriser" or category_value == "" or category_value == "À catégoriser"
