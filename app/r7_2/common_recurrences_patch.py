from __future__ import annotations

from app.database import Database
from app.services.recurring_scope_service import RecurringScopeService


_PATCH_MARKER = "_r7_2_lot6_common_recurrences_applied"


def apply_r7_2_common_recurrences_patch() -> None:
    """Rend les récurrences standards communes aux scénarios du Prévisionnel.

    Règle Lot 6 :
    - une récurrence standard appartient à la base prévisionnelle commune ;
    - elle ne doit pas être rattachée exclusivement à Prudent / Réaliste /
      Optimiste ;
    - les scénarios personnalisés restent gérés par le module Scénarios Premium.
    """
    if getattr(Database, _PATCH_MARKER, False):
        return

    original_initialize = Database.initialize
    original_add_recurring_item = Database.add_recurring_item
    original_update_recurring_item = Database.update_recurring_item

    def initialize_with_common_recurrences(self) -> None:
        original_initialize(self)
        # Migration fonctionnelle non destructive : seule l'ancienne étiquette
        # de scénario est normalisée. Montants, dates, fréquences et comptes
        # restent inchangés.
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE recurring_items
                SET scenario = 'Tous',
                    updated_at = CURRENT_TIMESTAMP
                WHERE COALESCE(scenario, '') <> 'Tous'
                """
            )

    def add_recurring_item_common(self, data: dict) -> None:
        payload = RecurringScopeService.normalize_payload(data)
        original_add_recurring_item(self, payload)

    def update_recurring_item_common(self, item_id: int, data: dict) -> None:
        payload = RecurringScopeService.normalize_payload(data)
        original_update_recurring_item(self, item_id, payload)

    Database.initialize = initialize_with_common_recurrences
    Database.add_recurring_item = add_recurring_item_common
    Database.update_recurring_item = update_recurring_item_common
    setattr(Database, _PATCH_MARKER, True)
