from __future__ import annotations

import json
from calendar import monthrange
from datetime import datetime
from uuid import uuid4


class ScenarioEventService:
    """Service for scenario financial events."""

    EVENT_TYPES = {
        "cash_in": "Entrée ponctuelle",
        "cash_out": "Sortie ponctuelle",
        "recurring_income": "Revenu récurrent",
        "recurring_expense": "Dépense récurrente",
        "loan_start": "Emprunt simple",
        "loan_payment": "Mensualité d’emprunt",
        "asset_purchase": "Achat d’actif",
        "asset_sale": "Vente d’actif",
        "liability_creation": "Création de passif",
        "liability_repayment": "Remboursement de passif",
        "investment": "Investissement",
        "custom": "Projet libre",
    }

    CASH_CREDIT_TYPES = {"cash_in", "recurring_income", "loan_start", "asset_sale"}
    CASH_DEBIT_TYPES = {"cash_out", "recurring_expense", "loan_payment", "liability_repayment", "investment"}

    ASSET_INCREASE_TYPES = {"asset_purchase", "investment"}
    ASSET_DECREASE_TYPES = {"asset_sale"}
    LIABILITY_INCREASE_TYPES = {"loan_start", "liability_creation"}
    LIABILITY_DECREASE_TYPES = {"loan_payment", "liability_repayment"}
    LOAN_CONTEXT_TYPES = {"loan_start", "loan_payment", "liability_creation", "liability_repayment"}

    FREQUENCIES = {
        "once": "Une fois",
        "monthly": "Mensuel",
        "yearly": "Annuel",
    }

    @classmethod
    def event_nature(cls, event_type: str) -> str:
        if event_type in cls.ASSET_INCREASE_TYPES or event_type in cls.ASSET_DECREASE_TYPES:
            return "Actif"
        if event_type in cls.LIABILITY_INCREASE_TYPES or event_type in cls.LIABILITY_DECREASE_TYPES:
            return "Passif"
        return "Flux"

    @classmethod
    def event_sense_label(cls, event_type: str) -> str:
        if event_type in cls.ASSET_INCREASE_TYPES:
            return "Augmente les actifs"
        if event_type in cls.ASSET_DECREASE_TYPES:
            return "Diminue les actifs"
        if event_type in cls.LIABILITY_INCREASE_TYPES:
            return "Augmente les dettes"
        if event_type in cls.LIABILITY_DECREASE_TYPES:
            return "Diminue les dettes"
        if event_type in cls.CASH_CREDIT_TYPES:
            return "Entrée de trésorerie"
        if event_type in cls.CASH_DEBIT_TYPES:
            return "Sortie de trésorerie"
        return "Libre"

    def __init__(self, db) -> None:
        self.db = db

    def validate_event(self, data: dict) -> dict:
        event_type = data.get("event_type") or "cash_out"
        if event_type not in self.EVENT_TYPES:
            event_type = "custom"
        label = (data.get("label") or "").strip()
        if not label:
            raise ValueError("Le libellé de l’événement est obligatoire.")
        frequency = data.get("frequency") or "once"
        if frequency not in self.FREQUENCIES:
            frequency = "once"
        amount = abs(float(data.get("amount") or 0))
        if event_type == "custom":
            amount = float(data.get("amount") or 0)
        metadata = data.get("metadata_json") or {}
        if isinstance(metadata, str):
            metadata_json = metadata
        else:
            metadata_json = json.dumps(metadata, ensure_ascii=False)
        return {
            "event_type": event_type,
            "label": label,
            "description": data.get("description") or "",
            "event_date": data.get("event_date"),
            "end_date": data.get("end_date"),
            "amount": amount,
            "currency_code": data.get("currency_code") or "EUR",
            "frequency": frequency,
            "duration_months": int(data.get("duration_months") or 0) or None,
            "account_id": data.get("account_id"),
            "asset_id": data.get("asset_id"),
            "liability_id": data.get("liability_id"),
            "metadata_json": metadata_json,
            "is_active": 1 if data.get("is_active", True) else 0,
        }

    def list_events(self, scenario_id: int, include_deleted: bool = False) -> list:
        where_deleted = "" if include_deleted else "AND e.deleted_at IS NULL"
        with self.db.connect() as conn:
            return list(conn.execute(
                f"""
                SELECT e.*, a.name AS account_name
                FROM scenario_events e
                LEFT JOIN accounts a ON a.id = e.account_id
                WHERE e.scenario_id = ? {where_deleted}
                ORDER BY e.event_date, e.id
                """,
                (scenario_id,),
            ))

    def get_event(self, event_id: int):
        with self.db.connect() as conn:
            return conn.execute("SELECT * FROM scenario_events WHERE id = ?", (event_id,)).fetchone()

    def loan_repayment_schedule(self, event_id: int) -> list[dict]:
        """Return the repayment schedule related to a loan/passive event.

        - If the selected event is itself a repayment event, expand this event.
        - If it is a loan/passive creation event, list repayment events from the
          same scenario starting after the loan date.
        """
        event = self.get_event(event_id)
        if not event:
            return []
        event_type = event["event_type"]
        if event_type not in self.LOAN_CONTEXT_TYPES:
            return []

        if event_type in self.LIABILITY_DECREASE_TYPES:
            source_events = [event]
        else:
            with self.db.connect() as conn:
                source_events = list(conn.execute(
                    """
                    SELECT *
                    FROM scenario_events
                    WHERE scenario_id = ?
                      AND deleted_at IS NULL
                      AND is_active = 1
                      AND event_type IN ('loan_payment', 'liability_repayment')
                      AND event_date >= ?
                    ORDER BY event_date, id
                    """,
                    (event["scenario_id"], event["event_date"]),
                ))

        rows: list[dict] = []
        for source in source_events:
            rows.extend(self._expand_repayment_event(source))
        return rows

    def _expand_repayment_event(self, event) -> list[dict]:
        frequency = event["frequency"] or "once"
        start = self._parse_date(event["event_date"])
        if not start:
            return []
        end = self._repayment_end_date(event, start)
        current = start
        rows: list[dict] = []
        index = 1
        while current <= end:
            rows.append({
                "index": index,
                "date": current.isoformat(),
                "label": event["label"],
                "event_type": event["event_type"],
                "frequency": self.FREQUENCIES.get(frequency, frequency),
                "amount": abs(float(event["amount"] or 0)),
                "duration_months": event["duration_months"],
                "scenario_event_id": int(event["id"]),
            })
            index += 1
            if frequency == "monthly":
                current = self._add_months(current, 1)
            elif frequency == "yearly":
                current = self._add_months(current, 12)
            else:
                break
        return rows

    def _repayment_end_date(self, event, start):
        if event["end_date"]:
            parsed = self._parse_date(event["end_date"])
            if parsed:
                return parsed
        duration = int(event["duration_months"] or 0)
        if duration:
            return self._add_months(start, max(0, duration - 1))
        return start

    @staticmethod
    def _parse_date(value):
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except Exception:
            return None

    @staticmethod
    def _add_months(day, months: int):
        month = day.month - 1 + months
        year = day.year + month // 12
        month = month % 12 + 1
        last = monthrange(year, month)[1]
        return day.replace(year=year, month=month, day=min(day.day, last))

    def add_event(self, scenario_id: int, data: dict) -> int:
        payload = self.validate_event(data)
        if not payload["event_date"]:
            raise ValueError("La date de début est obligatoire.")
        with self.db.connect() as conn:
            scenario = conn.execute("SELECT id FROM scenarios WHERE id = ? AND deleted_at IS NULL", (scenario_id,)).fetchone()
            if not scenario:
                raise ValueError("Scénario introuvable.")
            cur = conn.execute(
                """
                INSERT INTO scenario_events(uuid, scenario_id, event_type, label, description, event_date, end_date,
                                            amount, currency_code, frequency, duration_months, account_id, asset_id,
                                            liability_id, metadata_json, is_active)
                VALUES (:uuid, :scenario_id, :event_type, :label, :description, :event_date, :end_date,
                        :amount, :currency_code, :frequency, :duration_months, :account_id, :asset_id,
                        :liability_id, :metadata_json, :is_active)
                """,
                {"uuid": str(uuid4()), "scenario_id": scenario_id, **payload},
            )
            conn.execute("UPDATE scenarios SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (scenario_id,))
            event_id = int(cur.lastrowid)
        self.db.seal_database_to_encrypted_vault()
        return event_id

    def update_event(self, event_id: int, data: dict) -> None:
        row = self.get_event(event_id)
        if not row:
            raise ValueError("Événement introuvable.")
        merged = {key: row[key] for key in row.keys()}
        merged.update(data)
        payload = self.validate_event(merged)
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE scenario_events
                SET event_type = :event_type, label = :label, description = :description, event_date = :event_date,
                    end_date = :end_date, amount = :amount, currency_code = :currency_code, frequency = :frequency,
                    duration_months = :duration_months, account_id = :account_id, asset_id = :asset_id,
                    liability_id = :liability_id, metadata_json = :metadata_json, is_active = :is_active,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :event_id
                """,
                {"event_id": event_id, **payload},
            )
            conn.execute("UPDATE scenarios SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (row["scenario_id"],))
        self.db.seal_database_to_encrypted_vault()

    def delete_event(self, event_id: int) -> None:
        row = self.get_event(event_id)
        if not row:
            return
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE scenario_events SET deleted_at = CURRENT_TIMESTAMP, is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (event_id,),
            )
            conn.execute("UPDATE scenarios SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (row["scenario_id"],))
        self.db.seal_database_to_encrypted_vault()
