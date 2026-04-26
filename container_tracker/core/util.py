"""OS / time helpers. Pure utilities; no module-level side effects."""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

EST = timezone(timedelta(hours=-5))


def resource_path(rel: str) -> Path:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return Path(base) / rel


def app_icon_path() -> Path:
    """Return path to bundled app.ico. In dev, it lives at the project root;
    in a PyInstaller bundle, it's at the _MEIPASS root (--add-data 'app.ico;.')."""
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS) / "app.ico"
    # In dev, walk up from this file (container_tracker/core/util.py) to the project root.
    return Path(__file__).resolve().parents[2] / "app.ico"


def open_in_explorer(path: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", str(path)])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        logger.info(f"open_in_explorer failed: {e}")


def now_est() -> str:
    return datetime.now(EST).strftime("%Y-%m-%d %I:%M %p EST")


def now_est_short() -> str:
    return datetime.now(EST).strftime("%I:%M %p")
