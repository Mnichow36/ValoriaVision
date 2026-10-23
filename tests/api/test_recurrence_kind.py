from __future__ import annotations

from tests.api.test_access_control import AccessControlBase


class RecurrenceKindTests(AccessControlBase):
    def payload(self, **overrides):
        base = {
            "account_id": self.accounts["Compte courant"],
            "name": "BOUYGUES TELECOM",
            "category": "Logement",
            "direction": "Débit",
            "amount": 12.99,
            "frequency": "Mensuel",
            "next_date": "2026-12-15",
            "scenario": "Réaliste",
        }
        base.update(overrides)
        return base

    def listed(self):
        data = self.admin.get("/api/v1/forecast").json()
        return {item["id"]: item for item in data["recurrences"]}

    def test_kind_is_saved_listed_and_kept_when_omitted(self):
        created = self.admin.post("/api/v1/recurrences", self.payload(kind="Abonnement"))
        self.assertEqual(created.status_code, 200, created.text)
        item_id = created.json()["recurringItemId"]
        self.assertEqual(self.listed()[item_id]["kind"], "Abonnement")
        # une mise à jour sans type (ancien client) ne l'écrase pas
        updated = self.admin.put(f"/api/v1/recurrences/{item_id}", self.payload(amount=14.5))
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(self.listed()[item_id]["kind"], "Abonnement")
        changed = self.admin.put(f"/api/v1/recurrences/{item_id}", self.payload(kind="Charge fixe"))
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(self.listed()[item_id]["kind"], "Charge fixe")

    def test_default_kind_is_autre(self):
        item_id = self.admin.post("/api/v1/recurrences", self.payload()).json()["recurringItemId"]
        self.assertEqual(self.listed()[item_id]["kind"], "Autre")

    def test_inconsistent_kinds_are_refused(self):
        self.assertEqual(self.admin.post("/api/v1/recurrences", self.payload(kind="Inconnu")).status_code, 409)
        self.assertEqual(self.admin.post("/api/v1/recurrences", self.payload(kind="Revenu")).status_code, 409)
        credit = self.payload(category="Revenus", direction="Crédit", kind="Abonnement")
        self.assertEqual(self.admin.post("/api/v1/recurrences", credit).status_code, 409)

    def test_desktop_insert_without_kind_still_works(self):
        item_id = self.database.add_recurring_item({
            "account_id": self.accounts["Compte courant"], "name": "Ancien", "category": "Logement", "amount": -5,
            "frequency": "Mensuel", "next_date": "2026-12-01", "end_date": None, "scenario": "Réaliste", "status": "Actif",
        })
        self.assertEqual(self.database.get_recurring_item(item_id)["recurrence_kind"], "Autre")
