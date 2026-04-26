"""Unit tests for container_tracker.bridge.

Bridge methods are pure Python; pywebview / JS integration is verified
manually via DevTools console probe (see Step 4 commit body), not here.
"""

from container_tracker.bridge import Bridge
from container_tracker.core import config as ct_config
from container_tracker.core import credentials


# Keys the JS-side ROWS array uses (extracted from container_tracker/web/app.js).
# If app.js's row renderer learns to consume more keys, add them here so the
# bridge contract stays pinned.
ROWS_KEYS = {
    "cn", "carrier", "scac", "status",
    "eta", "orig", "delay", "delayVal",
    "pol", "pod", "vessel", "pct",
}


def test_ping_returns_pong():
    assert Bridge().ping() == "pong"


def test_list_containers_shape():
    rows = Bridge().list_containers()
    assert isinstance(rows, list) and len(rows) >= 1
    for row in rows:
        missing = ROWS_KEYS - set(row.keys())
        assert not missing, (
            f"row {row.get('cn')!r} missing keys {missing}; "
            f"app.js render() will break on these. Either bridge needs to "
            f"populate them or ROWS_KEYS in this test is stale."
        )


def test_get_settings_reads_config(isolated_data_dir, mock_keyring):
    ct_config.save_config({
        "company_name": "ACME", "contact_email": "", "excel_path": "",
        "dark_mode": False, "dismissed": [],
    })
    mock_keyring.store[(credentials.KEYRING_SERVICE,
                        credentials.KEYRING_USER)] = "real-token"

    assert Bridge().get_settings() == {
        "company_name": "ACME",
        "api_token_present": True,
        "theme": "light",
    }


def test_get_settings_no_token(isolated_data_dir, mock_keyring):
    ct_config.save_config({
        "company_name": "ACME", "contact_email": "", "excel_path": "",
        "dark_mode": False, "dismissed": [],
    })
    # mock_keyring is empty by default

    assert Bridge().get_settings()["api_token_present"] is False
