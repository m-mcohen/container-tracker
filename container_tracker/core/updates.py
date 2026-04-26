"""GitHub Releases polling for the in-app update banner."""

import logging
import threading
from typing import Callable

import requests

from container_tracker.core.constants import GITHUB_REPO, __version__

logger = logging.getLogger(__name__)


def check_for_update_async(on_update: Callable[[str, str], None]) -> None:
    """Background GitHub Releases check.

    ``on_update(tag, html_url)`` is invoked on a worker thread iff a newer
    release than the local ``__version__`` exists. Always non-blocking; failures
    log at INFO and are swallowed.
    """
    def _go():
        try:
            if "<<" in GITHUB_REPO or "/" not in GITHUB_REPO:
                return
            r = requests.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                timeout=5,
            )
            if r.status_code != 200:
                logger.info(f"update check: HTTP {r.status_code}")
                return
            data = r.json()
            tag = str(data.get("tag_name", "")).lstrip("v").strip()
            url = data.get("html_url", "")
            if not tag:
                return
            from packaging.version import parse as _parse
            if _parse(tag) > _parse(__version__):
                on_update(tag, url)
        except Exception as e:
            logger.info(f"update check failed: {e}")
    threading.Thread(target=_go, daemon=True).start()
