from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable


def _field(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key] if key in row.keys() else default
    except (AttributeError, KeyError, TypeError):
        return default


def _number(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


class AssetsReadService:
    """Expose patrimonial valuations without adding presentation-only estimates."""

    def __init__(
        self,
        database: Any,
        now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.database = database
        self.now_provider = now_provider

    def snapshot(self) -> dict[str, Any]:
        rows = [self._asset(row) for row in self.database.list_assets()]
        active_rows = [row for row in rows if row["status"] == "Actif" and self._is_patrimonial(row)]
        assets = [row for row in active_rows if row["value"] >= 0]
        liabilities = [row for row in active_rows if row["value"] < 0]
        total_assets = round(sum(row["value"] for row in assets), 2)
        total_liabilities = round(abs(sum(row["value"] for row in liabilities)), 2)
        net = round(total_assets - total_liabilities, 2)
        evolution = self._evolution()
        starting_net = evolution[0]["net"] if evolution else 0
        change_percent = round((net - starting_net) / abs(starting_net) * 100, 1) if starting_net else 0.0
        families = self._families(assets, total_assets)

        return {
            "generatedAt": self.now_provider().isoformat(),
            "currency": "EUR",
            "summary": {
                "totalAssets": total_assets,
                "totalLiabilities": total_liabilities,
                "netWorth": net,
                "liquidities": 0.0,
                "changePercent": change_percent,
                "assetCount": len(assets),
                "liabilityCount": len(liabilities),
            },
            "families": families,
            "evolution": evolution,
            "assets": assets,
            "liabilities": liabilities,
            "leadingAssetId": assets[0]["id"] if assets else None,
        }

    @staticmethod
    def _asset(row: Any) -> dict[str, Any]:
        raw_details = _field(row, "details_json", "{}")
        try:
            details = raw_details if isinstance(raw_details, dict) else json.loads(str(raw_details or "{}"))
        except (TypeError, ValueError):
            details = {}
        return {
            "id": int(_field(row, "id", 0) or 0),
            "name": str(_field(row, "name", "Élément patrimonial") or "Élément patrimonial"),
            "category": str(_field(row, "category", "Autres actifs") or "Autres actifs"),
            "type": str(_field(row, "asset_type", "Actif") or "Actif"),
            "value": _number(_field(row, "value", 0)),
            "valuationDate": str(_field(row, "valuation_date", "") or ""),
            "valuationMode": str(_field(row, "valuation_mode", "Manuelle") or "Manuelle"),
            "status": str(_field(row, "status", "Actif") or "Actif"),
            "comment": str(_field(row, "comment", "") or ""),
            "details": {str(key): str(value) for key, value in details.items()} if isinstance(details, dict) else {},
        }

    @staticmethod
    def _is_patrimonial(row: dict[str, Any]) -> bool:
        excluded_terms = (
            "compte courant", "compte bancaire", "liquidités", "liquidites", "livret",
            "épargne", "epargne", "dépôt", "depot", "découvert", "decouvert",
        )
        text = " ".join(str(row.get(key, "")).casefold() for key in ("name", "category", "type"))
        return not any(term in text for term in excluded_terms)

    def _evolution(self) -> list[dict[str, Any]]:
        raw = {
            "net": list(self.database.patrimonio_evolution("net")),
            "assets": list(self.database.patrimonio_evolution("assets")),
            "liabilities": list(self.database.patrimonio_evolution("liabilities")),
        }
        dates = sorted({str(point.get("date") or "") for values in raw.values() for point in values if point.get("date")})[-8:]
        if not dates:
            return []
        indexed = {
            name: {str(point.get("date") or ""): _number(point.get("value")) for point in values}
            for name, values in raw.items()
        }
        return [
            {
                "date": value_date,
                "net": indexed["net"].get(value_date, 0.0),
                "assets": indexed["assets"].get(value_date, 0.0),
                "liabilities": -abs(indexed["liabilities"].get(value_date, 0.0)),
            }
            for value_date in dates
        ]

    @staticmethod
    def _families(assets: list[dict[str, Any]], total_assets: float) -> list[dict[str, Any]]:
        values: dict[str, float] = {}
        for asset in assets:
            values[asset["category"]] = round(values.get(asset["category"], 0) + asset["value"], 2)
        return [
            {
                "name": name,
                "value": value,
                "weight": round(value / total_assets * 100, 1) if total_assets else 0.0,
                "status": "Disponible" if "liquid" in name.lower() or "compte" in name.lower() else "Actif",
            }
            for name, value in sorted(values.items(), key=lambda item: item[1], reverse=True)
        ]
