from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

print("Diagnostic Valoria Vision V0.6.6-R5")
print("=" * 50)
print("Dossier:", ROOT)
print("Python:", sys.executable)
print("Version Python:", sys.version)

def check(name: str):
    try:
        module = __import__(name)
        version = getattr(module, "__version__", "OK")
        print(f"OK {name}: {version}")
        return True
    except Exception as exc:
        print(f"ERREUR {name}: {exc}")
        return False

ok = True
for module in ["PySide6", "plotly", "cryptography", "keyring", "openpyxl"]:
    ok = check(module) and ok

plotly_js = ROOT / "data" / "runtime" / "plotly.min.js"
print("Plotly local:", plotly_js, "OK" if plotly_js.exists() else "ABSENT")
if plotly_js.exists():
    print("Taille Plotly local:", plotly_js.stat().st_size, "octets")

print("Base SQLite:", ROOT / "data" / "valoria_vision.db")
print("Vault sécurisé:", ROOT / "data" / "secure" / "valoria_vision.vvdb")

raise SystemExit(0 if ok else 1)
