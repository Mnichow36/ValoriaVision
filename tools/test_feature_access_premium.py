from __future__ import annotations

from app.services.feature_access_service import FeatureAccessService


class FakeDatabase:
    def __init__(self) -> None:
        self.settings: dict[str, str] = {}

    def get_setting(self, key: str, default: str = "") -> str:
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self.settings[key] = value


def main() -> None:
    db = FakeDatabase()
    access = FeatureAccessService(db)

    assert access.edition() == "free"
    assert access.has_feature(FeatureAccessService.FEATURE_SCENARIOS) is False

    for edition in ("premium", "premium_personnel", "patrimoine_expert", "pro"):
        access.set_edition(edition)
        assert access.has_feature(FeatureAccessService.FEATURE_SCENARIOS) is True

    access.set_edition("free")
    assert access.has_feature(FeatureAccessService.FEATURE_SCENARIOS) is False

    print("OK - Accès Premium : module Scénarios verrouillé en Free et disponible en Premium")


if __name__ == "__main__":
    main()
