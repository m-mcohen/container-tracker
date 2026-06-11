"""GitHub Releases polling for the in-app update banner."""

import logging
import threading
from typing import Callable

import requests

from container_tracker.core.constants import GITHUB_REPO, __version__

logger = logging.getLogger(__name__)


def check_for_update() -> dict:
    """Synchronous GitHub Releases check.

    Returns ``{"available": bool, "tag": str, "url": str}``. ``tag`` has the
    leading ``v`` stripped. Failures (offline, rate-limited, bad payload) log
    at INFO and report ``available=False`` — the caller never sees an
    exception. Blocks up to the 5s HTTP timeout; call from a worker thread
    (pywebview bridge methods already run on one).
    """
    no_update = {"available": False, "tag": "", "url": ""}
    try:
        if "<<" in GITHUB_REPO or "/" not in GITHUB_REPO:
            return no_update
        r = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            timeout=5,
        )
        if r.status_code != 200:
            logger.info(f"update check: HTTP {r.status_code}")
            return no_update
        data = r.json()
        tag = str(data.get("tag_name", "")).lstrip("v").strip()
        url = data.get("html_url", "")
        if not tag:
            return no_update
        from packaging.version import parse as _parse
        if _parse(tag) > _parse(__version__):
            return {"available": True, "tag": tag, "url": url}
        return no_update
    except Exception as e:
        logger.info(f"update check failed: {e}")
        return no_update


def check_for_update_async(on_update: Callable[[str, str], None]) -> None:
    """Background GitHub Releases check (legacy tkinter GUI codepath).

    ``on_update(tag, html_url)`` is invoked on a worker thread iff a newer
    release than the local ``__version__`` exists. Always non-blocking.
    """
    def _go():
        result = check_for_update()
        if result["available"]:
            on_update(result["tag"], result["url"])
    threading.Thread(target=_go, daemon=True).start()
