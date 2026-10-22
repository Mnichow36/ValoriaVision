from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable


def _number(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


class DashboardReadService:
    """Build a UI-neutral Dashboard contract from the existing Python engine.

    This service is deliberately independent from PySide and FastAPI. It keeps
    Python as the single source of truth while allowing several presentation
    layers to consume the same values.
    """

    def __init__(
        self,
        database: Any,
        today_provider: Callable[[], date] = date.today,
        now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.database = database
        self.today_provider = today_provider
        self.now_provider = now_provider

    def snapshot(self) -> dict[str, Any]:
        today = self.today_provider()
        metrics = self.database.dashboard_metrics()
        month = str(metrics.get("month") or today.strftime("%Y-%m"))
        forecast = self.database.dashboard_forecast_chart(60)
        budget = self.database.budget_report(month)
        assets = self.database.asset_summary()

        return {
            "generatedAt": self.now_provider().isoformat(),
            "period": month,
            "currency": "EUR",
            "kpis": self._kpis(metrics),
            "forecast": self._forecast_points(forecast),
            "budget": self._budget(month, budget),
            "assets": self._assets(assets),
            "alerts": self._alerts(forecast),
        }

    @staticmethod
    def _kpis(metrics: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "id": "cash",
                "label": "Liquidités disponibles",
                "value": _number(metrics.get("cash")),
                "currency": "EUR",
                "detail": "Comptes courants et épargne",
                "tone": "blue",
            },
            {
                "id": "forecast-30",
                "label": "Liquidités prévisionnelles J+30",
                "value": _number(metrics.get("forecast_30")),
                "currency": "EUR",
                "detail": "Scénario réaliste",
                "tone": "green",
            },
            {
                "id": "net-worth",
                "label": "Patrimoine net",
                "value": _number(metrics.get("patrimoine_net")),
                "currency": "EUR",
                "detail": "Actifs moins passifs",
                "tone": "purple",
            },
            {
                "id": "income",
                "label": "Revenus du mois",
                "value": _number(metrics.get("revenus")),
                "currency": "EUR",
                "detail": "Hors transferts internes",
                "tone": "green",
            },
            {
                "id": "expenses",
                "label": "Dépenses du mois",
                "value": _number(metrics.get("depenses")),
                "currency": "EUR",
                "detail": "Y compris épargne programmée et remboursements ; hors transferts et investissements",
                "tone": "red",
            },
        ]

    @staticmethod
    def _forecast_points(forecast: dict[str, Any]) -> list[dict[str, Any]]:
        raw_points = forecast.get("points")
        if isinstance(raw_points, list):
            points = []
            for point in raw_points:
                if not isinstance(point, dict):
                    continue
                points.append(
                    {
                        "label": str(point.get("label") or point.get("date") or ""),
                        "balance": _number(
                            point["balance"] if "balance" in point else point.get("value")
                        ),
                    }
                )
            if points:
                return points

        labels = forecast.get("labels") or []
        series = forecast.get("series") or {}
        balances = (
            forecast.get("balances")
            or forecast.get("values")
            or series.get("Réaliste")
            or []
        )
        return [
            {"label": str(label), "balance": _number(balance)}
            for label, balance in zip(labels, balances)
        ]

    @staticmethod
    def _budget(month: str, budget: dict[str, Any]) -> dict[str, Any]:
        rows = []
        for row in budget.get("rows", []):
            rows.append(
                {
                    "category": str(row.get("category") or "Sans catégorie"),
                    "planned": _number(row.get("planned")),
                    "actual": _number(row.get("actual")),
                    "remaining": _number(row.get("remaining")),
                    "usage": _number(row.get("usage")),
                    "status": str(row.get("status") or "OK"),
                }
            )
        return {
            "month": str(budget.get("month") or month),
            "totalPlanned": _number(budget.get("total_planned")),
            "totalRealized": _number(budget.get("total_realized")),
            "rows": rows,
        }

    @staticmethod
    def _assets(assets: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {"label": str(label), "value": abs(_number(value))}
            for label, value in assets.items()
            if _number(value) > 0
        ]

    @staticmethod
    def _alerts(forecast: dict[str, Any]) -> list[dict[str, Any]]:
        level = str(forecast.get("alert_level") or "info")
        if level == "ok":
            level = "success"
        if level not in {"info", "success", "warning", "critical"}:
            level = "info"
        return [
            {
                "level": level,
                "title": str(forecast.get("alert") or "Prévision disponible"),
                "detail": str(
                    forecast.get("alert_detail")
                    or f"Point bas : {_number(forecast.get('min_balance')):,.0f} EUR"
                ),
            },
            {
                "level": "info",
                "title": "Projection à 60 jours",
                "detail": f"Solde projeté : {_number(forecast.get('end_balance')):,.0f} EUR",
            },
        ]
