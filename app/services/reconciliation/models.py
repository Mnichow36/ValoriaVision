from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal


Direction = Literal["debit", "credit"]
Qualification = Literal["automatic", "review", "without_forecast"]


@dataclass(frozen=True)
class TransactionInput:
    id: int
    account_id: int
    tx_date: date
    amount: float
    label: str
    direction: Direction
    category: str | None = None
    counterparty: str | None = None
    external_reference: str | None = None


@dataclass(frozen=True)
class ForecastInput:
    id: int
    account_id: int
    expected_date: date
    expected_amount: float
    expected_label: str
    direction: Direction
    category: str | None = None
    counterparty: str | None = None
    external_reference: str | None = None


@dataclass(frozen=True)
class CriterionScore:
    criterion: str
    points: float
    maximum: float
    explanation: str


@dataclass(frozen=True)
class CandidateScore:
    forecast: ForecastInput
    score: int
    date_delta_days: int
    amount_delta: float
    criteria: tuple[CriterionScore, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class QualificationResult:
    status: Qualification
    transaction_id: int
    best_candidate: CandidateScore | None
    candidates: tuple[CandidateScore, ...]
    ambiguity_delta: float | None
    reason: str

