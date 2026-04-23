"""Config, keyring, and tracking-data persistence.

Platform: Windows in production. `_PLATFORM` is a module attribute (not a
direct `sys.platform` reference) so tests can monkeypatch it cleanly.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import keyring as _keyring


logger = logging.getLogger(__name__)

APP_SHORT_NAME = "ContainerTracker"
KEYRING_SERVICE = f"{APP_SHORT_NAME}_shipsgo_api"
KEYRING_USER = "default"

# Module-level so tests can monkeypatch.
_PLATFORM: str = sys.platform

_DEFAULT_CONFIG: dict[str, Any] = {
    "company_name": "",
    "contact_email": "",
    "excel_path": "",
    "dark_mode": False,
    "dismissed": [],
}


def data_dir() -> Path:
    """Return %APPDATA%\\ContainerTracker on Windows, ~/.config/ContainerTracker elsewhere.

    Creates the directory if missing.
    """
    if _PLATFORM == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path.home() / ".config"
    path = base / APP_SHORT_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return data_dir() / "config.json"


def tracking_data_path() -> Path:
    return data_dir() / "tracking_data.json"


def log_path() -> Path:
    return data_dir() / "tracker.log"


def load_config() -> dict[str, Any]:
    """Read config.json. Missing file -> default dict. Missing keys -> backfilled from defaults."""
    path = config_path()
    if not path.exists():
        return dict(_DEFAULT_CONFIG)
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    merged = dict(_DEFAULT_CONFIG)
    if isinstance(loaded, dict):
        merged.update({k: loaded[k] for k in loaded if k in _DEFAULT_CONFIG})
    return merged


def save_config(config: dict[str, Any]) -> None:
    """Write config.json atomically. Strips any forbidden keys (notably `api_key`)."""
    safe = {k: v for k, v in config.items() if k in _DEFAULT_CONFIG}
    path = config_path()
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(safe, handle, indent=2, default=str)
    tmp.replace(path)


def load_tracking_data() -> dict[str, Any]:
    path = tracking_data_path()
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def save_tracking_data(db: dict[str, Any]) -> None:
    path = tracking_data_path()
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(db, handle, indent=2, default=str)
    tmp.replace(path)


def get_api_token() -> str:
    """Read the ShipsGo token from the OS keyring. Returns "" on any failure."""
    try:
        value = _keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception as exc:  # pragma: no cover - defensive
        logger.info("keyring read failed: %s", exc)
        return ""
    return value or ""


def set_api_token(token: str) -> None:
    """Write the ShipsGo token to the OS keyring. Logs and swallows backend failures."""
    try:
        _keyring.set_password(KEYRING_SERVICE, KEYRING_USER, token)
    except Exception as exc:  # pragma: no cover - defensive
        logger.info("keyring write failed: %s", exc)


def is_first_run(config: dict[str, Any]) -> bool:
    """True iff `company_name` is missing/empty AND no keyring token exists."""
    has_company = bool(config.get("company_name"))
    has_token = bool(get_api_token())
    return not (has_company or has_token)
