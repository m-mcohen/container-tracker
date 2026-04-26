"""Data directory layout, config persistence, and v1 → v1.1 startup migrations.

Module is import-pure: paths are computed but no directories are created and no
migrations run until a caller invokes the top-level helpers (``boot()``,
``run_folder_migrations()``, ``init_logging()``).
"""

import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from container_tracker.core.constants import APP_SHORT_NAME

logger = logging.getLogger(__name__)


def get_data_dir() -> Path:
    """Return the per-user data directory. Creates it if missing."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    d = base / APP_SHORT_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


DATA_DIR = get_data_dir()
CONFIG_FILE = DATA_DIR / "config.json"
TRACKING_DB_FILE = DATA_DIR / "tracking_data.json"
LOG_FILE = DATA_DIR / "tracker.log"


# ---------------------------------------------------------------------------
# Legacy migration: data folders
# ---------------------------------------------------------------------------

def _migrate_data_folder(src: Path, dst: Path) -> int:
    """Move known data files from src → dst. Returns number of files moved.
    Removes src only if it emptied out."""
    if src is None or not src.exists() or src.resolve() == dst.resolve():
        return 0
    moved = 0
    for name in ("config.json", "tracking_data.json", "tracker.log"):
        s = src / name
        d = dst / name
        if s.exists() and not d.exists():
            try:
                shutil.move(str(s), str(d))
                moved += 1
            except Exception:
                pass
    if moved > 0:
        try:
            remaining = list(src.iterdir())
            if not remaining:
                src.rmdir()
                # Try to clean up the company-level parent if it empties out too.
                try:
                    parent = src.parent
                    appdata = (Path(os.environ.get("APPDATA", ""))
                               if sys.platform == "win32" else None)
                    if (parent.exists() and parent != appdata
                            and not list(parent.iterdir())):
                        parent.rmdir()
                except Exception:
                    pass
        except Exception:
            pass
    return moved


def _legacy_exe_dir() -> Path:
    """The directory next to the executable (oldest data layout)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # Source-tree fallback: project root (two levels up from this file).
    return Path(__file__).resolve().parents[2]


def _legacy_kgc_dir() -> Path | None:
    """The previous brand's APPDATA folder (Ken Gabbay Coffee → KenGabbayTracker)."""
    if sys.platform != "win32":
        return None
    return Path(os.environ.get("APPDATA", Path.home())) / "Ken Gabbay Coffee" / "KenGabbayTracker"


def run_folder_migrations() -> None:
    """Move v0/v1 data files into DATA_DIR. Idempotent."""
    _migrate_data_folder(_legacy_exe_dir(), DATA_DIR)
    kgc = _legacy_kgc_dir()
    if kgc is not None:
        _migrate_data_folder(kgc, DATA_DIR)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def load_json(filepath, default: Any = None):
    p = Path(filepath)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return default if default is not None else {}


def save_json(filepath, data) -> None:
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)


def load_config() -> dict:
    return load_json(CONFIG_FILE, {
        "company_name": "",
        "contact_email": "",
        "excel_path": "",
        "dark_mode": False,
        "dismissed": [],
    })


def save_config(cfg: dict) -> None:
    save_json(CONFIG_FILE, cfg)


# ---------------------------------------------------------------------------
# Legacy migration: token in config.json → keyring
# ---------------------------------------------------------------------------

def migrate_token_from_config(cfg: dict) -> bool:
    """If config.json contains a legacy token field, move it to the keyring.
    Returns True if the config was mutated (caller should save_config)."""
    # Local import: keep core.config and core.credentials cycle-free.
    from container_tracker.core import credentials

    changed = False
    for key in ("shipsgo_api_token", "api_key"):
        if key in cfg:
            tok = str(cfg.pop(key) or "").strip()
            if tok:
                credentials.set_api_token(tok)
                logger.info(f"migrated {key} from config.json to keyring")
            changed = True
    return changed


def is_first_run(cfg: dict) -> bool:
    """True iff there's neither a configured company nor a stored token."""
    from container_tracker.core import credentials
    return not cfg.get("company_name") and not credentials.get_api_token()


# ---------------------------------------------------------------------------
# Logging + startup contract
# ---------------------------------------------------------------------------

def init_logging() -> None:
    """Attach a FileHandler at DATA_DIR/tracker.log to the root logger.
    Idempotent thanks to logging.basicConfig's no-op behavior when handlers
    are already configured."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE)],
    )


def boot() -> None:
    """Run all v1 → v1.1 startup migrations. Idempotent: re-runs are no-ops on
    an already-migrated install. Both entry points must call this once before
    anything reads config or keyring. Returns nothing — callers that need the
    config call ``load_config()`` themselves.

    Order matters:
      1. init_logging — so subsequent steps log to the right file.
      2. run_folder_migrations — relocate data from legacy paths first so that
         load_config below reads from the canonical location.
      3. migrate_token_from_config — move any plain-text token into the keyring
         BEFORE migrate_keyring runs, so that a token already in config wins
         over a stale legacy keyring entry (current install is the source of
         truth, not the previous brand's leftover).
      4. migrate_keyring — copy the legacy KenGabbayTracker keyring entry into
         the new service name (no-op if the new service is already set).
    """
    init_logging()
    run_folder_migrations()
    cfg = load_config()
    if migrate_token_from_config(cfg):
        save_config(cfg)
    # Local import: core.config and core.credentials would otherwise form an
    # import cycle (credentials may want config.LOG_FILE later). Do not hoist.
    from container_tracker.core import credentials
    credentials.migrate_keyring()
