from __future__ import annotations

from datetime import date
from uuid import uuid4


class ScenarioService:
    """CRUD service for personalized Valoria Vision scenarios.

    A scenario is a simulation layer. It never writes real transactions,
    accounts or assets.
    """

    TYPES = [
        "Achat immobilier",
        "Emprunt",
        "Travaux",
        "Investissement",
        "Vente d’actif",
        "Baisse de revenus",
        "Hausse de revenus",
        "Dépense exceptionnelle",
        "Revenu exceptionnel",
        "Projet libre",
    ]

    def __init__(self, db) -> None:
        self.db = db
        self.ensure_reference_scenario()

    def ensure_reference_scenario(self) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id FROM scenarios WHERE is_reference = 1 AND deleted_at IS NULL ORDER BY id LIMIT 1"
            ).fetchone()
            if row:
                return int(row["id"])
            cur = conn.execute(
                """
                INSERT INTO scenarios(uuid, name, description, scenario_type, start_date, horizon_months, currency_code, is_reference, is_active)
                VALUES (?, 'Référence', 'Situation réelle actuelle sans hypothèse supplémentaire.', 'Référence', ?, 12, 'EUR', 1, 1)
                """,
                (str(uuid4()), date.today().isoformat()),
            )
            return int(cur.lastrowid)

    def list_scenarios(self, include_deleted: bool = False) -> list:
        self.ensure_reference_scenario()
        where = "" if include_deleted else "WHERE deleted_at IS NULL"
        with self.db.connect() as conn:
            return list(conn.execute(
                f"""
                SELECT s.*,
                       (SELECT COUNT(*) FROM scenario_events e WHERE e.scenario_id = s.id AND e.deleted_at IS NULL) AS event_count
                FROM scenarios s
                {where}
                ORDER BY s.is_reference DESC, s.updated_at DESC, s.name
                """
            ))

    def get_scenario(self, scenario_id: int):
        with self.db.connect() as conn:
            return conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()

    def get_reference_scenario(self):
        self.ensure_reference_scenario()
        with self.db.connect() as conn:
            return conn.execute("SELECT * FROM scenarios WHERE is_reference = 1 AND deleted_at IS NULL ORDER BY id LIMIT 1").fetchone()

    def create_scenario(self, data: dict) -> int:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("Le nom du scénario est obligatoire.")
        scenario_type = data.get("scenario_type") or "Projet libre"
        start_date = data.get("start_date") or date.today().isoformat()
        horizon = int(data.get("horizon_months") or 12)
        currency = data.get("currency_code") or "EUR"
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO scenarios(uuid, name, description, scenario_type, start_date, end_date, horizon_months, currency_code, is_reference, is_active, is_premium)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?)
                """,
                (
                    str(uuid4()),
                    name,
                    data.get("description") or "",
                    scenario_type,
                    start_date,
                    data.get("end_date"),
                    horizon,
                    currency,
                    1 if data.get("is_premium") else 0,
                ),
            )
            scenario_id = int(cur.lastrowid)
        self.db.seal_database_to_encrypted_vault()
        return scenario_id

    def update_scenario(self, scenario_id: int, data: dict) -> None:
        row = self.get_scenario(scenario_id)
        if not row:
            raise ValueError("Scénario introuvable.")
        if row["is_reference"]:
            # The reference scenario can be displayed but its structural status
            # must remain stable and non-deletable.
            data = {**data, "name": "Référence", "scenario_type": "Référence"}
        name = (data.get("name") or row["name"] or "").strip()
        if not name:
            raise ValueError("Le nom du scénario est obligatoire.")
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE scenarios
                SET name = ?, description = ?, scenario_type = ?, start_date = ?, end_date = ?,
                    horizon_months = ?, currency_code = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    name,
                    data.get("description") if data.get("description") is not None else row["description"],
                    data.get("scenario_type") or row["scenario_type"],
                    data.get("start_date") or row["start_date"],
                    data.get("end_date") if data.get("end_date") is not None else row["end_date"],
                    int(data.get("horizon_months") or row["horizon_months"] or 12),
                    data.get("currency_code") or row["currency_code"] or "EUR",
                    1 if data.get("is_active", row["is_active"]) else 0,
                    scenario_id,
                ),
            )
        self.db.seal_database_to_encrypted_vault()

    def delete_scenario(self, scenario_id: int) -> None:
        row = self.get_scenario(scenario_id)
        if not row:
            return
        if row["is_reference"]:
            raise ValueError("Le scénario de référence ne peut pas être supprimé.")
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE scenarios SET deleted_at = CURRENT_TIMESTAMP, is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (scenario_id,),
            )
            conn.execute(
                "UPDATE scenario_events SET deleted_at = CURRENT_TIMESTAMP, is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE scenario_id = ?",
                (scenario_id,),
            )
        self.db.seal_database_to_encrypted_vault()

    def duplicate_scenario(self, scenario_id: int) -> int:
        row = self.get_scenario(scenario_id)
        if not row:
            raise ValueError("Scénario introuvable.")
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO scenarios(uuid, name, description, scenario_type, start_date, end_date, horizon_months, currency_code, is_reference, is_active, is_premium)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?)
                """,
                (
                    str(uuid4()),
                    f"{row['name']} — copie",
                    row["description"],
                    row["scenario_type"],
                    row["start_date"],
                    row["end_date"],
                    row["horizon_months"],
                    row["currency_code"],
                    row["is_premium"],
                ),
            )
            new_id = int(cur.lastrowid)
            events = list(conn.execute("SELECT * FROM scenario_events WHERE scenario_id = ? AND deleted_at IS NULL", (scenario_id,)))
            for event in events:
                conn.execute(
                    """
                    INSERT INTO scenario_events(uuid, scenario_id, event_type, label, description, event_date, end_date,
                                                amount, currency_code, frequency, duration_months, account_id, asset_id,
                                                liability_id, metadata_json, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        new_id,
                        event["event_type"],
                        event["label"],
                        event["description"],
                        event["event_date"],
                        event["end_date"],
                        event["amount"],
                        event["currency_code"],
                        event["frequency"],
                        event["duration_months"],
                        event["account_id"],
                        event["asset_id"],
                        event["liability_id"],
                        event["metadata_json"],
                        event["is_active"],
                    ),
                )
        self.db.seal_database_to_encrypted_vault()
        return new_id
