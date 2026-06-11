"""Windows Credential Manager wrapper for the ShipsGo API token.

The token must NEVER be persisted to config.json or any plain-text file. Use
get_api_token / set_api_token only.
"""

import logging

try:
    import keyring
except ImportError:
    keyring = None

from container_tracker.core.constants import APP_SHORT_NAME

logger = logging.getLogger(__name__)

KEYRING_SERVICE = f"{APP_SHORT_NAME}_shipsgo_api"
LEGACY_KEYRING_SERVICE = "KenGabbayTracker_shipsgo_api"
KEYRING_USER = "default"


def get_api_token() -> str:
    if keyring is None:
        return ""
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER) or ""
    except Exception as e:
        logger.warning(f"keyring read failed: {e}")
        return ""


def set_api_token(token: str) -> None:
    if keyring is None:
        logger.warning("keyring not installed; token not persisted")
        return
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, token)
    except Exception as e:
        logger.warning(f"keyring write failed: {e}")


def migrate_keyring() -> None:
    """One-shot migration of the legacy KenGabbayTracker_shipsgo_api entry to
    ContainerTracker_shipsgo_api. Idempotent: a no-op once the legacy entry is
    gone. If the new service is already populated, the legacy entry is deleted
    without overwrite (current value wins)."""
    if keyring is None:
        return
    try:
        old = keyring.get_password(LEGACY_KEYRING_SERVICE, KEYRING_USER)
    except Exception as e:
        logger.info(f"keyring legacy read failed: {e}")
        return
    if not old:
        return
    try:
        current = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        current = None
    if not current:
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USER, old)
            logger.info("migrated keyring entry to new service name")
        except Exception as e:
            logger.info(f"keyring migrate write failed: {e}")
            return
    try:
        keyring.delete_password(LEGACY_KEYRING_SERVICE, KEYRING_USER)
    except Exception as e:
        logger.info(f"keyring legacy delete failed: {e}")
