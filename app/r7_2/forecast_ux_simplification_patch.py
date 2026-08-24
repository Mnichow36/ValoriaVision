from __future__ import annotations

_PATCHED = False


def apply_r7_2_forecast_ux_simplification_patch() -> None:
    """Lot 5.2 — simplify forecast UX around recurring events.

    Rules:
    - creation/edition/deletion of forecast recurrences is centralized in
      "Gérer les récurrences";
    - the duplicate blue "+ Ajouter événement / récurrence" button is hidden;
    - chart context menus only expose recurrence-management actions;
    - the redundant "Voir les opérations" context action is removed because
      hover/click already expose period operations.
    """
    global _PATCHED
    if _PATCHED:
        return

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QMenu, QPushButton
        from app.ui import forecast_page
    except Exception:
        return

    ForecastPage = forecast_page.ForecastPage
    ForecastDailyChart = getattr(forecast_page, "ForecastDailyChart", None)

    original_build = ForecastPage.build

    def build_without_duplicate_add_button(self):
        original_build(self)
        # The button is still created by the historical ForecastPage.build.
        # Hide it after build so this patch stays non-invasive and compatible
        # with older layouts.
        for button in self.findChildren(QPushButton):
            if button.text().strip() == "+ Ajouter événement / récurrence":
                button.hide()
                button.setEnabled(False)
                button.setToolTip("Ajout centralisé dans Gérer les récurrences")
        # Keep the help text aligned with the new interaction model.
        try:
            for label in self.findChildren(forecast_page.QLabel):
                text = label.text() or ""
                if "Clic droit : menu de gestion des récurrences" in text:
                    label.setText("Survol : détail des opérations. Clic : détail de la période. Clic droit : gestion des récurrences uniquement si une récurrence existe.")
                elif "clic droit : récurrences" in text:
                    label.setText("Crédits et débits en colonnes, solde cumulé en courbe. Survol : détail, clic : opérations, clic droit : récurrences existantes.")
        except Exception:
            pass

    def open_period_context_menu_recurrences_only(self, point: dict) -> None:
        recurring_events = [event for event in point.get("events", []) if event.get("recurring_id")]
        if not recurring_events:
            return
        menu = QMenu(self)
        recurring_actions = {}
        manage_menu = menu.addMenu("Gérer les récurrences de la période")
        for event in recurring_events:
            label = f"{event.get('name', '')} — {event.get('account', '')}"
            sub = manage_menu.addMenu(label)
            recurring_actions[sub.addAction("Modifier la récurrence")] = ("edit", event["recurring_id"])
            recurring_actions[sub.addAction("Supprimer la récurrence")] = ("delete", event["recurring_id"])
        selected = menu.exec(QCursor.pos())
        if selected in recurring_actions:
            action_type, recurring_id = recurring_actions[selected]
            if action_type == "edit":
                self.edit_recurring_item(recurring_id)
            elif action_type == "delete":
                self.delete_recurring_item(recurring_id)

    def daily_chart_context_menu_recurrences_only(self, pos):
        index = self.nearest_day_index(pos)
        if index is None or not self.data:
            return
        day = self.data["daily_points"][index]
        recurring_events = [event for event in day.get("events", []) if event.get("recurring_id")]
        if not recurring_events:
            return
        menu = QMenu(self)
        recurring_actions = {}
        manage_menu = menu.addMenu("Gérer les récurrences du jour")
        for event in recurring_events:
            label = f"{event.get('name', '')} — {event.get('account', '')}"
            sub = manage_menu.addMenu(label)
            recurring_actions[sub.addAction("Modifier la récurrence")] = ("edit", event["recurring_id"])
            recurring_actions[sub.addAction("Supprimer la récurrence")] = ("delete", event["recurring_id"])
        selected = menu.exec(self.mapToGlobal(pos))
        if selected in recurring_actions:
            action_type, recurring_id = recurring_actions[selected]
            if action_type == "edit":
                self.parent_page.edit_recurring_item(recurring_id)
            elif action_type == "delete":
                self.parent_page.delete_recurring_item(recurring_id)

    ForecastPage.build = build_without_duplicate_add_button
    ForecastPage.open_period_context_menu = open_period_context_menu_recurrences_only
    if ForecastDailyChart is not None:
        ForecastDailyChart.open_context_menu = daily_chart_context_menu_recurrences_only

    _PATCHED = True
