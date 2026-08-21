from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.r7_2.import_ui_feedback_patch import apply_r7_2_import_ui_feedback_patch


def main() -> int:
    """Smoke-test the R7.2.3 all-duplicates UX patch.

    This test does not open a Qt window. It verifies that the patch function can
    be imported and applied without breaking the TransactionsPage monkey-patch.
    The full behaviour is validated in user recette with a real SG re-import.
    """
    apply_r7_2_import_ui_feedback_patch()
    print("Patch UX réimport 100% doublon appliqué.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
