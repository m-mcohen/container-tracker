"""GitHub Releases update check.

Synchronous by design. The UI layer wraps this in a QRunnable for background
execution; the threading concern is kept out of the core module.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from packaging.version import InvalidVersion, parse


logger = logging.getLogger(__name__)

GITHUB_REPO = "m-mcohen/container-tracker"
_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    html_url: str


def check_for_update(current_version: str, timeout: float = 5.0) -> UpdateInfo | None:
    """Return UpdateInfo if GitHub has a newer release, else None.

    All failure modes — network error, HTTP non-200, malformed JSON, missing
    `tag_name`, unparseable version — return None and log a single info line.
    """
    try:
        response = requests.get(_RELEASES_URL, timeout=timeout)
    except requests.RequestException as exc:
        logger.info("update check: request failed: %s", exc)
        return None

    if response.status_code != 200:
        logger.info("update check: HTTP %s", response.status_code)
        return None

    try:
        data = response.json()
    except ValueError as exc:
        logger.info("update check: malformed JSON: %s", exc)
        return None

    tag = str(data.get("tag_name", "")).lstrip("v").strip()
    html_url = str(data.get("html_url", ""))
    if not tag:
        logger.info("update check: release response missing tag_name")
        return None

    try:
        if parse(tag) > parse(current_version):
            return UpdateInfo(version=tag, html_url=html_url)
    except InvalidVersion as exc:
        logger.info("update check: unparseable version %s: %s", tag, exc)
        return None
    return None
