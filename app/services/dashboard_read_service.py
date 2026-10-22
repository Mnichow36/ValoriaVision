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

    def snapshot(self, account_id: int | None = None, month: str | None = None) -> dict[str, Any]:
        today = self.today_provider()
        if month is not None and not (len(month) == 7 and month[4] == "-" and month[:4].isdigit() and month[5:].isdigit() and 1 <= int(month[5:]) <= 12):
            raise ValueError("Le mois doit avoir la forme AAAA-MM.")
        interactive = hasattr(self.database, "dashboard_quality")
        if interactive:
            metrics = self.database.dashboard_metrics(month, account_id)
        else:
            metrics = self.database.dashboard_metrics()
        month = str(metrics.get("month") or today.strftime("%Y-%m"))
        forecast = self.database.dashboard_forecast_chart(60)
        budget = self.database.budget_report(month)
        assets = self.database.asset_summary()

        result = {
            "generatedAt": self.now_provider().isoformat(),
            "period": month,
            "currency": "EUR",
            "kpis": self._kpis(metrics),
            "forecast": self._forecast_points(forecast),
            "budget": self._budget(month, budget),
            "assets": self._assets(assets),
            "alerts": self._alerts(forecast),
        }
        if interactive:
            result.update(self._interactive(account_id, month, budget, today))
        return result

    # -- Tableau de bord interactif : filtres, alertes réelles, qualité, échéances --
    def _interactive(self, account_id: int | None, month: str, budget: dict[str, Any], today: date) -> dict[str, Any]:
        db = self.database
        quality = db.dashboard_quality(account_id)
        flows = db.dashboard_month_flows(month, account_id)
        start = db.default_forecast_start_date()
        forecast = db.cash_forecast(start, 60, "Réaliste", account_id=account_id)
        reconciliation = self._reconciliation(account_id)
        accounts = [
            {
                "id": int(row["id"]),
                "name": (f"{row['bank']} - " if row["bank"] else "") + str(row["name"]) + (" (archivé)" if row["status"] != "Actif" else ""),
                "status": str(row["status"]),
            }
            for row in db.list_accounts()
            if row["status"] != "Clos"
        ]
        alerts = self._real_alerts(account_id, month, budget, forecast, quality, reconciliation)
        upcoming = [
            {"date": str(event["date"]), "label": str(event.get("name") or event.get("label") or "Mouvement"), "amount": _number(event.get("amount"))}
            for event in forecast.get("upcoming", [])
            if str(event["date"]) >= today.isoformat()
        ][:5]
        last_import = quality["lastImport"]
        days_since = None
        if last_import:
            try:
                days_since = (today - date.fromisoformat(last_import)).days
            except ValueError:
                days_since = None
        return {
            "filters": {"accountId": account_id, "month": month},
            "accounts": accounts,
            "months": [str(item) for item in db.budget_months()],
            "alerts": alerts,
            "toProcess": len([alert for alert in alerts if alert["level"] != "success"]),
            "expensesByCategory": [
                {"label": name, "value": round(value, 2)}
                for name, value in sorted(flows["by_category"].items(), key=lambda item: -item[1])
            ],
            "budgetComparable": account_id is None,
            "quality": {**quality, "daysSinceImport": days_since, "reconciliationPending": reconciliation["pending"]},
            "upcoming": upcoming,
        }

    def _reconciliation(self, account_id: int | None) -> dict[str, int]:
        try:
            from app.services.reconciliation_read_service import ReconciliationReadService
            summary = ReconciliationReadService(self.database).snapshot(account_id).get("summary", {})
            return {"pending": int(summary.get("unmatchedTransactions") or 0), "gap": int(summary.get("partial") or 0)}
        except Exception:  # le tableau de bord ne doit jamais tomber à cause des rapprochements
            return {"pending": 0, "gap": 0}

    @staticmethod
    def _eur(value: float) -> str:
        return f"{value:,.0f}".replace(",", "\u202f") + "\u00a0€"

    def _real_alerts(self, account_id, month, budget, forecast, quality, reconciliation) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        if account_id is None:
            over = [row for row in budget.get("rows", []) if row.get("status") == "Dépassement"]
            over.sort(key=lambda row: float(row.get("actual") or 0) - float(row.get("planned") or 0), reverse=True)
            for row in over[:2]:
                alerts.append({
                    "level": "warning", "target": "budgets",
                    "title": f"{row['category']} dépasse son budget",
                    "detail": f"{self._eur(float(row['actual']))} / {self._eur(float(row['planned']))} ce mois-ci",
                })
        balances = forecast.get("balances") or []
        points = forecast.get("daily_points") or []
        if balances:
            low = min(balances)
            index = balances.index(low)
            when = str(points[index]["date"])[5:].split("-") if index < len(points) else []
            when_label = f"{when[1]}/{when[0]}" if len(when) == 2 else ""
            threshold = self._safety_threshold()
            if low < 0:
                alerts.append({"level": "critical", "target": "forecast", "title": "Trésorerie négative prévue",
                               "detail": f"Point bas {self._eur(low)} le {when_label}"})
            elif threshold > 0 and low < threshold:
                alerts.append({"level": "warning", "target": "forecast", "title": "Solde sous le seuil de sécurité",
                               "detail": f"Point bas {self._eur(low)} le {when_label} · seuil {self._eur(threshold)}"})
        if quality["uncategorized"] > 0:
            n = quality["uncategorized"]
            large = quality["uncategorizedLarge"]
            alerts.append({
                "level": "info", "target": "transactions",
                "title": f"{n} transaction{'s' if n > 1 else ''} à catégoriser",
                "detail": f"Dont {large} supérieure{'s' if large > 1 else ''} à 100 €" if large else "Aucune supérieure à 100 €",
            })
        if reconciliation["pending"] > 0:
            n = reconciliation["pending"]
            gap = reconciliation["gap"]
            alerts.append({
                "level": "info", "target": "reconciliation",
                "title": f"{n} rapprochement{'s' if n > 1 else ''} à traiter",
                "detail": f"{gap} écart{'s' if gap > 1 else ''} de montant à régler" if gap else "Opérations bancaires sans prévision associée",
            })
        order = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda alert: order.get(alert["level"], 3))
        if not alerts:
            alerts.append({"level": "success", "target": None, "title": "Aucune alerte", "detail": "Budget, trésorerie et données sont à jour."})
        return alerts

    def _safety_threshold(self) -> float:
        try:
            return max(0.0, float(str(self.database.get_setting("forecast.safety_threshold", "0") or "0").replace(",", ".")))
        except (AttributeError, ValueError):
            return 0.0

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
