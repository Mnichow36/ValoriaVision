from __future__ import annotations


class I18nService:
    """Translation-key service prepared for future multi-language UI.

    V0.6.0 stores translation keys in the database. The UI remains French by
    default for now.
    """

    def __init__(self, db) -> None:
        self.db = db

    def t(self, key: str, locale: str = "fr") -> str:
        return self.db.translation_value(locale, key) or key
