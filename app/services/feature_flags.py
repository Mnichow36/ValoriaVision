from __future__ import annotations


class FeatureFlagService:
    """Small wrapper around database feature flags.

    V0.6.0 prepares Premium features without activating them by default.
    """

    def __init__(self, db) -> None:
        self.db = db

    def enabled(self, key: str) -> bool:
        return self.db.is_feature_enabled(key)

    def report(self) -> dict:
        return self.db.feature_flags_report()

    def premium_ready(self) -> bool:
        report = self.report()
        return report.get("total_flags", 0) > 0 and report.get("premium_flags", 0) > 0
