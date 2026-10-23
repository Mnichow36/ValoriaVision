"""Dossier de dépôt des sauvegardes (réglable dans Paramètres).

Le choix est mémorisé dans un petit fichier JSON à côté de la base, volontairement
hors de la base : une restauration ou une remise à zéro ne le perd donc pas.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

SETTINGS_FILE = "backup_location.json"


class BackupLocationError(ValueError):
    """Dossier refusé, avec un message lisible par l'utilisateur."""


def _settings_path(data_dir: Path) -> Path:
    return Path(data_dir) / SETTINGS_FILE


def configured_directory(data_dir: Path) -> Path | None:
    """Dossier choisi par l'utilisateur, ou None (dossier par défaut)."""
    try:
        raw = json.loads(_settings_path(data_dir).read_text(encoding="utf-8")).get("directory")
    except (OSError, ValueError, AttributeError):
        return None
    return Path(str(raw)) if raw else None


def effective_directory(data_dir: Path, default_dir: Path) -> Path:
    return configured_directory(data_dir) or Path(default_dir)


def _clean(raw: str | None) -> Path:
    text = (raw or "").strip().strip('"').strip()
    if not text:
        raise BackupLocationError("Indique le chemin du dossier.")
    if "\x00" in text:
        raise BackupLocationError("Chemin invalide.")
    path = Path(os.path.expandvars(os.path.expanduser(text)))
    if not path.is_absolute():
        raise BackupLocationError("Indique un chemin complet, par exemple D:\\Sauvegardes Valoria.")
    return path


def count_backups(path: Path) -> int:
    try:
        return sum(1 for item in path.glob("*.vvb") if item.is_file())
    except OSError:
        return 0


def check_directory(raw: str | None, *, create: bool = False) -> dict[str, Any]:
    """Teste un dossier : existence, droit d'écriture, nombre de sauvegardes."""
    path = _clean(raw)
    if path.exists() and not path.is_dir():
        raise BackupLocationError("Ce chemin désigne un fichier, pas un dossier.")
    existed = path.is_dir()
    if not existed:
        if not create:
            return {"path": str(path), "exists": False, "writable": False, "count": 0,
                    "message": "Ce dossier n’existe pas encore ; il sera créé à l’enregistrement."}
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BackupLocationError(f"Impossible de créer ce dossier : {exc.strerror or exc}.") from exc
    probe = path / f".valoria_test_{uuid.uuid4().hex}"
    try:
        probe.write_bytes(b"ok")
        probe.unlink()
    except OSError as exc:
        raise BackupLocationError(f"Ce dossier n’est pas accessible en écriture : {exc.strerror or exc}.") from exc
    return {"path": str(path), "exists": True, "writable": True, "count": count_backups(path),
            "message": "Dossier accessible en écriture."}


def save_directory(data_dir: Path, raw: str | None) -> dict[str, Any]:
    """Enregistre le dossier (créé au besoin) ; None ou vide rétablit le dossier par défaut."""
    target = _settings_path(data_dir)
    if not (raw or "").strip():
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        return {"path": None}
    status = check_directory(raw, create=True)
    target.write_text(json.dumps({"directory": status["path"]}, ensure_ascii=False), encoding="utf-8")
    return status


_BROWSE_SCRIPT = (
    "import sys\n"
    "import tkinter as tk\n"
    "from tkinter import filedialog\n"
    "root = tk.Tk()\n"
    "root.withdraw()\n"
    "root.attributes('-topmost', True)\n"
    "print(filedialog.askdirectory(title='Dossier des sauvegardes Valoria', initialdir=sys.argv[1] or None) or '')\n"
)


def browse_directory(initial: str | None = None) -> str | None:
    """Ouvre la fenêtre système de choix de dossier (sur l'ordinateur qui exécute l'application)."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", _BROWSE_SCRIPT, initial or ""],
            capture_output=True, text=True, timeout=300, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BackupLocationError("La fenêtre de choix de dossier n’a pas pu s’ouvrir : saisis le chemin.") from exc
    if result.returncode != 0:
        raise BackupLocationError("La fenêtre de choix de dossier n’est pas disponible : saisis le chemin.")
    chosen = result.stdout.strip().splitlines()[-1].strip() if result.stdout.strip() else ""
    if not chosen:
        return None
    return str(Path(chosen))
