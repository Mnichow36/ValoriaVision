from __future__ import annotations

_PATCHED = False


def apply_r7_2_import_account_resolution_patch() -> None:
    """Lot 3 — robust multi-bank account recognition for imports.

    The import screen no longer compares the bank-file identifier against only
    one account field. It resolves the selected account through normalized
    variants built from account number, RIB/BBAN fragments, IBAN and legacy
    identifier.
    """
    global _PATCHED
    if _PATCHED:
        return

    from app.ui.transactions_page import TransactionsPage
    from app.r7_2.account_resolution import resolve_import_account

    def detected_source_identifiers(self) -> list[str]:
        analysis = getattr(self.import_service, "last_analysis", None)
        diagnostic = getattr(analysis, "diagnostic", None)
        return list(getattr(diagnostic, "source_account_identifiers", []) or [])

    def account_resolution_result(self):
        return resolve_import_account(getattr(self, "accounts", []) or [], self.detected_source_identifiers())

    def account_matches_detected_identifier(self, account, detected_identifiers: list[str]) -> bool:
        result = resolve_import_account([account], detected_identifiers)
        return result.unique_strong_match is not None

    def matching_accounts_for_import(self) -> list:
        result = self.account_resolution_result()
        return [match.account for match in result.matches]

    def auto_select_detected_account(self) -> None:
        result = self.account_resolution_result()
        match = result.unique_strong_match
        if match is None:
            return
        index = self.import_account_combo.findData(match.account["id"])
        if index >= 0:
            self.import_account_combo.setCurrentIndex(index)

    def import_account_consistency(self) -> tuple[bool, str]:
        result = self.account_resolution_result()
        detected = result.detected_identifiers
        if not detected:
            return True, "Le fichier ne contient pas d’identifiant de compte exploitable. Sélection manuelle du compte requise."

        account_id = self.import_account_combo.currentData()
        selected_match = None
        for match in result.matches:
            try:
                if match.account["id"] == account_id:
                    selected_match = match
                    break
            except Exception:
                pass

        shown = ", ".join(detected[:3])
        if selected_match and selected_match.confidence == "strong":
            return True, (
                f"Compte source détecté : {shown}. Compte cible cohérent.\n"
                f"Méthode : {selected_match.reason}."
            )

        strong_matches = [match for match in result.matches if match.confidence == "strong"]
        if len(strong_matches) == 1:
            match = strong_matches[0]
            label = f"{match.account['name']} — {match.account['bank']}"
            return False, (
                f"Import bloqué : le fichier semble appartenir au compte {shown}.\n"
                f"Compte Valoria correspondant détecté : {label}.\n"
                f"Méthode : {match.reason}.\n"
                "Sélectionnez ce compte avant l'import."
            )

        if result.matches:
            labels = ", ".join(f"{m.account['name']} — {m.account['bank']}" for m in result.matches[:4])
            return False, (
                f"Import bloqué : le fichier contient l'identifiant de compte {shown},\n"
                "mais plusieurs comptes Valoria peuvent correspondre ou la correspondance est trop faible.\n"
                f"Comptes candidats : {labels}.\n"
                "Complétez le N° de compte / RIB ou l’IBAN du compte pour sécuriser l'import."
            )

        return False, (
            f"Import bloqué : le fichier contient l'identifiant de compte {shown},\n"
            "mais aucun compte Valoria ne correspond via N° de compte, RIB ou IBAN.\n"
            "Créez ou mettez à jour le compte correspondant avant l'import."
        )

    TransactionsPage.detected_source_identifiers = detected_source_identifiers
    TransactionsPage.account_resolution_result = account_resolution_result
    TransactionsPage.account_matches_detected_identifier = account_matches_detected_identifier
    TransactionsPage.matching_accounts_for_import = matching_accounts_for_import
    TransactionsPage.auto_select_detected_account = auto_select_detected_account
    TransactionsPage.import_account_consistency = import_account_consistency

    _PATCHED = True
