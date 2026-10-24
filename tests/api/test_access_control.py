from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.database import Database
from app.security.auth_service import AuthService
from app.security.users import UserStore

ADMIN_PASSWORD = "MotDePasse123!"
MARIE_PASSWORD = "MarieSecret456!"
LEA_PASSWORD = "LeaSecret789!!"


def _family_database(root: str, with_password: bool = True) -> Database:
    database = Database(Path(root) / "valoria.db")
    with database.connect() as conn:
        database.create_schema(conn)
        database.apply_migrations(conn)
        database.seed_if_empty(conn)
        database.seed_recurring_items(conn)
    if with_password:
        AuthService(database).set_master_password(ADMIN_PASSWORD)
    return database


class Session:
    def __init__(self, client: TestClient, token: str, profile_id: str):
        self.client = client
        self.headers = {"X-Valoria-Session": token}
        self.profile_id = profile_id

    def get(self, path, **kw):
        return self.client.get(path, headers=self.headers, **kw)

    def post(self, path, json=None):
        return self.client.post(path, headers=self.headers, json=json)

    def put(self, path, json=None):
        return self.client.put(path, headers=self.headers, json=json)


class AccessControlBase(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.database = _family_database(self.tmp.name)
        self.client = TestClient(create_app(self.database))
        self.admin = self.login("u1", ADMIN_PASSWORD)
        accounts = {a["name"]: a["id"] for a in self.admin.get("/api/v1/accounts").json()["accounts"]}
        self.accounts = accounts
        self.visible_names = ["Compte courant", "Livret A"]
        assets = self.admin.get("/api/v1/assets").json()["assets"]
        self.asset_ids = [a["id"] for a in assets]
        self.marie = self.create_user(
            "Marie", "contributor", MARIE_PASSWORD,
            accounts=[accounts[n] for n in self.visible_names], assets=self.asset_ids[:2],
        )
        self.lea = self.create_user(
            "Léa", "reader", LEA_PASSWORD, accounts=[accounts["Compte courant"]], assets=[]
        )

    def tearDown(self):
        self.tmp.cleanup()

    def login(self, profile_id: str, password: str) -> Session:
        response = self.client.post("/api/v1/auth/unlock", json={"profile_id": profile_id, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return Session(self.client, response.json()["token"], profile_id)

    def create_user(self, name, role, password, accounts, assets) -> str:
        response = self.admin.post(
            "/api/v1/profiles",
            {"name": name, "role": role, "password": password, "accounts": accounts, "assets": assets},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["profile"]["id"]

    def as_user(self, profile_id: str, password: str) -> Session:
        return self.login(profile_id, password)

    def as_admin(self) -> Session:
        """Un seul profil est ouvert à la fois : on rouvre l'administrateur au besoin."""
        self.admin = self.login("u1", ADMIN_PASSWORD)
        return self.admin


class MigrationAndSetupTest(unittest.TestCase):
    def test_existing_password_becomes_first_administrator(self):
        with TemporaryDirectory() as root:
            database = _family_database(root)
            client = TestClient(create_app(database))
            status = client.get("/api/v1/auth/status").json()
            self.assertEqual([p["role"] for p in status["profiles"]], ["admin"])
            self.assertTrue(status["configured"])
            ok = client.post("/api/v1/auth/unlock", json={"password": ADMIN_PASSWORD})
            self.assertEqual(ok.status_code, 200)
            bad = client.post("/api/v1/auth/unlock", json={"password": "faux"})
            self.assertEqual(bad.status_code, 401)

    def test_first_installation_creates_the_family_base_and_first_administrator(self):
        with TemporaryDirectory() as root:
            database = Database(Path(root) / "new.db")
            client = TestClient(create_app(database))
            status = client.get("/api/v1/auth/status").json()
            self.assertFalse(status["configured"])
            self.assertFalse(database.path.exists())
            weak = client.post("/api/v1/auth/setup", json={"password": "court"})
            self.assertEqual(weak.status_code, 422)
            done = client.post("/api/v1/auth/setup", json={"password": ADMIN_PASSWORD, "name": "François"})
            self.assertEqual(done.status_code, 200, done.text)
            self.assertTrue(database.path.exists())
            again = client.post("/api/v1/auth/setup", json={"password": ADMIN_PASSWORD})
            self.assertEqual(again.status_code, 409)
            me = client.get("/api/v1/me", headers={"X-Valoria-Session": done.json()["token"]}).json()["me"]
            self.assertEqual((me["name"], me["role"], me["restricted"]), ("François", "admin", False))


class VisibilityTest(AccessControlBase):
    def test_restricted_profile_sees_only_its_accounts_and_scoped_totals(self):
        admin_seen = self.admin.get("/api/v1/accounts").json()
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        seen = marie.get("/api/v1/accounts").json()
        self.assertEqual(sorted(a["name"] for a in seen["accounts"]), sorted(self.visible_names))
        self.assertGreater(len(admin_seen["accounts"]), len(seen["accounts"]))
        dash = marie.get("/api/v1/dashboard").json()
        self.assertEqual(len(dash["accounts"]), len(self.visible_names))
        ids = {a["id"] for a in seen["accounts"]}
        transactions = marie.get("/api/v1/transactions").json()["transactions"]
        self.assertTrue(transactions)
        self.assertTrue(all(t["accountId"] in ids for t in transactions) if "accountId" in transactions[0]
                        else all(t["account"] in self.visible_names for t in transactions))

    def test_restricted_profile_can_open_with_imports_on_hidden_accounts(self):
        """Régression : des transactions liées à un lot d'import d'un compte masqué
        faisaient échouer l'élagage (clé étrangère) et donc la connexion (HTTP 500)."""
        hidden = next(i for n, i in self.accounts.items() if n not in self.visible_names)
        with self.database.connect() as conn:
            batch_id = conn.execute(
                "INSERT INTO import_batches(file_name, account_id, imported_count) VALUES ('rel.csv', ?, 1)",
                (hidden,),
            ).lastrowid
            tx_id = conn.execute(
                "INSERT INTO transactions(account_id, tx_date, label, category, amount, tx_type, status, source, "
                "signature, import_batch_id) VALUES (?, '2026-01-05', 'CAFE', 'Loisirs', -3, 'Débit', 'Validée', "
                "'test', 'sig-hidden-1', ?)",
                (hidden, batch_id),
            ).lastrowid
            # Table enfant sans colonne account_id : elle référence la transaction supprimée.
            rule_id = conn.execute(
                "INSERT INTO categorization_rules(uuid, name, match_field, match_operator, match_value, target_category_id) "
                "VALUES ('r-hidden', 'R', 'label', 'contains', 'CAFE', (SELECT MIN(id) FROM categories))"
            ).lastrowid
            conn.execute(
                "INSERT INTO categorization_rule_logs(uuid, rule_id, transaction_id, result_status) "
                "VALUES ('l-hidden', ?, ?, 'applied')",
                (rule_id, tx_id),
            )
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        seen = marie.get("/api/v1/transactions").json()["transactions"]
        self.assertFalse(any(t.get("label") == "CAFE" for t in seen))

    def test_hidden_accounts_do_not_weigh_in_the_net_worth(self):
        admin_kpis = self.admin.get("/api/v1/dashboard").json()["kpis"]
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        marie_kpis = marie.get("/api/v1/dashboard").json()["kpis"]
        self.assertNotEqual(admin_kpis, marie_kpis)

    def test_restricted_assets_are_filtered(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.assertEqual(len(marie.get("/api/v1/assets").json()["assets"]), 2)
        lea = self.as_user(self.lea, LEA_PASSWORD)
        self.assertEqual(len(lea.get("/api/v1/assets").json()["assets"]), 0)

    def test_scoped_copy_contains_no_secret_or_user_table(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        marie.get("/api/v1/accounts")
        import app.api.main as main_module  # noqa: F401  (le fichier temporaire est dans le dossier système)
        import glob
        import tempfile

        copies = glob.glob(str(Path(tempfile.gettempdir()) / "valoria-scope-*" / "scope-*.db"))
        self.assertTrue(copies)
        for path in copies:
            conn = sqlite3.connect(path)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertFalse({"app_users", "user_settings", "access_grants"} & tables)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM settings WHERE key LIKE 'security.%'").fetchone()[0], 0)
            conn.close()

    def test_changes_made_by_the_administrator_appear_without_restart(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        before = len(marie.get("/api/v1/transactions").json()["transactions"])
        admin = self.as_admin()
        created = admin.post(
            "/api/v1/transactions",
            {"account_id": self.accounts["Compte courant"], "tx_date": "2026-10-01", "label": "Test visible",
             "direction": "Débit", "amount": 10.0},
        )
        self.assertEqual(created.status_code, 200, created.text)
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        after = len(marie.get("/api/v1/transactions").json()["transactions"])
        self.assertEqual(after, before + 1)

    def test_giving_access_updates_the_scope(self):
        everything = list(self.accounts.values())
        response = self.admin.put(f"/api/v1/profiles/{self.marie}/access", {"accounts": everything, "assets": self.asset_ids})
        self.assertEqual(response.status_code, 200)
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.assertEqual(len(marie.get("/api/v1/accounts").json()["accounts"]), len(everything))


class RolesTest(AccessControlBase):
    def test_reader_cannot_write_but_can_simulate(self):
        lea = self.as_user(self.lea, LEA_PASSWORD)
        refused = lea.post(
            "/api/v1/transactions",
            {"account_id": self.accounts["Compte courant"], "tx_date": "2026-10-01", "label": "X",
             "direction": "Débit", "amount": 1.0},
        )
        self.assertEqual(refused.status_code, 403)
        self.assertIn("consultation", refused.json()["detail"])
        self.assertEqual(lea.post("/api/v1/accounts", {"name": "x", "bank": "b", "account_type": "Courant",
                                                         "initial_date": "2026-01-01"}).status_code, 403)
        simulation = lea.post("/api/v1/forecast/simulate", {"kind": "Dépense", "date": "2026-12-01", "amount": 50})
        self.assertNotEqual(simulation.status_code, 403)
        me = lea.get("/api/v1/me").json()["me"]
        self.assertFalse(me["canWrite"])
        self.assertTrue(me["restricted"])
        self.assertEqual((me["visibleAccounts"], me["totalAccounts"]), (1, len(self.accounts)))

    def test_contributor_cannot_touch_hidden_accounts(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        hidden = self.accounts["Boursorama"]
        r = marie.post(
            "/api/v1/transactions",
            {"account_id": hidden, "tx_date": "2026-10-01", "label": "X", "direction": "Débit", "amount": 1.0},
        )
        self.assertEqual(r.status_code, 404)
        with self.database.connect() as conn:
            tx_id = conn.execute("SELECT id FROM transactions WHERE account_id = ?", (hidden,)).fetchone()["id"]
        r = marie.post(
            f"/api/v1/transactions/{tx_id}",
            {"account_id": hidden, "tx_date": "2026-10-01", "label": "X", "direction": "Débit", "amount": 1.0, "status": "Validée"},
        )
        self.assertEqual(r.status_code, 404)
        self.assertEqual(marie.post(f"/api/v1/accounts/{hidden}/delete").status_code, 404)
        self.assertEqual(marie.post("/api/v1/transactions/actions/bulk", {"transaction_ids": [tx_id], "action": "validate"}).status_code, 404)

    def test_contributor_can_write_in_scope_and_sees_what_it_creates(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        ok = marie.post(
            "/api/v1/transactions",
            {"account_id": self.accounts["Livret A"], "tx_date": "2026-10-01", "label": "Dans le périmètre",
             "direction": "Débit", "amount": 5.0},
        )
        self.assertEqual(ok.status_code, 200, ok.text)
        created = marie.post(
            "/api/v1/accounts",
            {"name": "Compte de Marie", "bank": "Banque", "account_type": "Compte courant", "identifier": "FR-MARIE-1",
             "initial_balance": 100, "initial_date": "2026-01-01"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        names = [a["name"] for a in marie.get("/api/v1/accounts").json()["accounts"]]
        self.assertIn("Compte de Marie", names)
        # l'administrateur voit aussi ce compte, les autres profils non
        lea = self.as_user(self.lea, LEA_PASSWORD)
        self.assertNotIn("Compte de Marie", [a["name"] for a in lea.get("/api/v1/accounts").json()["accounts"]])
        admin = self.as_admin()
        self.assertIn("Compte de Marie", [a["name"] for a in admin.get("/api/v1/accounts").json()["accounts"]])

    def test_administration_is_reserved_to_administrators(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.assertEqual(marie.get("/api/v1/access").status_code, 403)
        self.assertEqual(marie.get("/api/v1/security/journal").status_code, 403)
        self.assertEqual(marie.post("/api/v1/profiles", {"name": "Pirate", "password": "Pirate12345!x"}).status_code, 403)
        self.assertEqual(marie.put(f"/api/v1/profiles/{self.lea}/access", {"accounts": [1], "assets": []}).status_code, 403)
        self.assertEqual(marie.post("/api/v1/settings/general", {"currency": "EUR", "current_month": "", "session_timeout_minutes": 5}).status_code, 403)
        # elle peut en revanche modifier son propre profil, mais pas son rôle
        self.assertEqual(marie.put(f"/api/v1/profiles/{self.marie}", {"name": "Marie D."}).status_code, 200)
        self.assertEqual(marie.put(f"/api/v1/profiles/{self.marie}", {"role": "admin"}).status_code, 403)
        self.assertEqual(marie.put(f"/api/v1/profiles/{self.lea}", {"name": "Autre"}).status_code, 403)

    def test_reader_can_change_its_own_password(self):
        lea = self.as_user(self.lea, LEA_PASSWORD)
        r = lea.post("/api/v1/security/change-password", {"current_password": LEA_PASSWORD, "new_password": "NouveauLea123!"})
        self.assertEqual(r.status_code, 200, r.text)
        self.login(self.lea, "NouveauLea123!")

    def test_access_matrix_tells_who_sees_what(self):
        matrix = self.admin.get("/api/v1/access").json()
        by_name = {r["name"]: r["visibleTo"] for r in matrix["resources"] if r["type"] == "account"}
        self.assertIn("u1", by_name["Boursorama"])
        self.assertNotIn(self.marie, by_name["Boursorama"])
        self.assertIn(self.marie, by_name["Livret A"])
        self.assertNotIn(self.lea, by_name["Livret A"])


class ProfileLifecycleTest(AccessControlBase):
    def test_passwords_are_independent_and_lockout_is_per_profile(self):
        for _ in range(3):
            r = self.client.post("/api/v1/auth/unlock", json={"profile_id": self.marie, "password": "faux"})
        self.assertEqual(r.status_code, 429)
        self.assertEqual(
            self.client.post("/api/v1/auth/unlock", json={"profile_id": self.marie, "password": MARIE_PASSWORD}).status_code, 429
        )
        self.assertEqual(
            self.client.post("/api/v1/auth/unlock", json={"profile_id": self.lea, "password": LEA_PASSWORD}).status_code, 200
        )

    def test_only_one_profile_is_open_at_a_time(self):
        first = self.as_user(self.marie, MARIE_PASSWORD)
        self.as_user(self.lea, LEA_PASSWORD)
        self.assertEqual(first.get("/api/v1/accounts").status_code, 401)

    def test_last_administrator_is_protected(self):
        self.assertEqual(self.admin.put("/api/v1/profiles/u1", {"role": "reader"}).status_code, 422)
        r = self.admin.post("/api/v1/profiles/u1/delete", {"password": ADMIN_PASSWORD})
        self.assertEqual(r.status_code, 409)  # on ne supprime pas le profil ouvert

    def test_delete_needs_the_administrator_password(self):
        r = self.admin.post(f"/api/v1/profiles/{self.lea}/delete", {"password": "faux"})
        self.assertEqual(r.status_code, 403)
        r = self.admin.post(f"/api/v1/profiles/{self.lea}/delete", {"password": ADMIN_PASSWORD})
        self.assertEqual(r.status_code, 200)
        ids = [p["id"] for p in self.client.get("/api/v1/profiles").json()["profiles"]]
        self.assertNotIn(self.lea, ids)
        with self.database.connect() as conn:
            left = conn.execute("SELECT COUNT(*) FROM access_grants WHERE user_id = 3").fetchone()[0]
        self.assertEqual(left, 0)

    def test_demo_profile_is_separate_and_needs_no_password(self):
        r = self.admin.post("/api/v1/profiles", {"name": "Démo", "kind": "demo"})
        self.assertEqual(r.status_code, 200, r.text)
        demo_id = r.json()["profile"]["id"]
        demo = self.login(demo_id, "")
        accounts = demo.get("/api/v1/accounts").json()["accounts"]
        self.assertTrue(accounts)
        self.assertEqual(demo.get("/api/v1/me").json()["me"]["roleLabel"], "Démonstration")
        self.assertEqual(demo.get("/api/v1/security/status").status_code, 409)

    def test_status_never_exposes_secrets(self):
        text = self.client.get("/api/v1/auth/status").text
        for secret in (ADMIN_PASSWORD, MARIE_PASSWORD, "hash", "salt"):
            self.assertNotIn(secret, text)

    def test_user_store_validations(self):
        store = UserStore(self.database)
        with self.assertRaises(Exception):
            store.create("marie", "contributor")  # nom déjà pris, sans tenir compte de la casse
        with self.assertRaises(Exception):
            store.create("Zoé", "super")
        self.assertEqual(store.scope_for(1).accounts, None)


if __name__ == "__main__":
    unittest.main()
