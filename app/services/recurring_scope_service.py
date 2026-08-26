from __future__ import annotations


class RecurringScopeService:
    """Règle métier de portée des récurrences standards."""

    COMMON_SCOPE = "Tous"

    @classmethod
    def normalize_payload(cls, data: dict) -> dict:
        payload = dict(data)
        payload["scenario"] = cls.COMMON_SCOPE
        return payload

    @classmethod
    def is_common(cls, scenario_value: str | None) -> bool:
        return str(scenario_value or "").strip() == cls.COMMON_SCOPE
