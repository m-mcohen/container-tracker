"""Unit tests for container_tracker.bridge.

Bridge methods are pure Python; pywebview / JS integration is verified
manually via the stash-to-global probe (see Step 4 / Step 5 commit
bodies), not here.
"""

import logging

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


def test_list_containers_empty(isolated_data_dir):
    # No tracking_data.json on disk → empty list, not an exception.
    # Fresh installs render an empty dashboard.
    assert ct_config.TRACKING_DB_FILE.exists() is False
    assert Bridge().list_containers() == []


def test_list_containers_translates_shape(sample_tracking_db):
    records = sample_tracking_db()
    cn = next(iter(records))

    rows = Bridge().list_containers()

    assert len(rows) == 1
    row = rows[0]
    # Contract: every key the JS renderer needs must be present.
    assert ROWS_KEYS <= set(row.keys()), (
        f"missing keys {ROWS_KEYS - set(row.keys())}"
    )
    # Spot-check field translation against the sanitized fixture values.
    assert row["cn"] == cn  # "EVRG1234567"
    assert row["eta"] == "2026-04-22"
    assert row["orig"] == "2026-04-15"
    assert row["delay"] == "+7 days"
    assert row["delayVal"] == 7  # parsed int from delay_days string
    assert row["pol"] == "Kaohsiung, TW"
    assert row["pod"] == "Los Angeles, USA"
    assert row["vessel"] == "MV TEST VOYAGER"
    assert row["pct"] == 58
    # Known limitation (flagged for follow-up): the ShipsGo API returns the
    # full carrier name ("EVERGREEN MARINE CORP") plus a separate scac field
    # ("EGLV"), but core.status.extract_fields() drops the scac and only
    # keeps the name. resolve_scac then can't map the full name back to
    # EGLV (the CARRIER_SCAC_MAP entry is "EVERGREEN"). For now scac falls
    # through as the uppercased carrier name. Fix needs a core change to
    # extract_fields — deferred (Step 5 spec forbids core/ edits).
    assert row["scac"] == "EVERGREEN MARINE CORP"
    # Status comes through uppercased.
    assert row["status"] == "SAILING"


def test_list_containers_skips_malformed(sample_tracking_db, caplog):
    # Two entries: one valid, one whose record is structurally hostile
    # (a non-dict value where the bridge expects a dict). The valid row
    # must still come through; the malformed one logs and is skipped.
    import json
    from container_tracker.core.status import extract_fields
    from pathlib import Path

    fixtures = Path(__file__).parent / "fixtures"
    shipment = json.loads((fixtures / "shipsgo_response.json").read_text())
    inner = shipment["shipment"]
    cn = inner["container_number"].upper()
    good = {
        "container_number": cn, "shipment_id": inner["id"],
        "last_refreshed": "2026-04-25", **extract_fields(shipment),
    }
    sample_tracking_db({cn: good, "BADX9999999": "not-even-a-dict"})

    with caplog.at_level(logging.WARNING, logger="container_tracker.bridge"):
        rows = Bridge().list_containers()

    cns = [r["cn"] for r in rows]
    assert cns == [cn], f"expected only valid row, got {cns}"
    assert any("BADX9999999" in m and "skipping" in m
               for m in caplog.messages), (
        f"malformed row should have been logged; got {caplog.messages}"
    )


def test_get_container_found(sample_tracking_db):
    records = sample_tracking_db()
    cn = next(iter(records))

    row = Bridge().get_container(cn)

    assert row is not None
    assert row["cn"] == cn
    assert ROWS_KEYS <= set(row.keys())


def test_get_container_not_found(sample_tracking_db):
    sample_tracking_db()  # populate so we know "missing" means missing
    assert Bridge().get_container("ZZZZ9999999") is None
    assert Bridge().get_container("") is None
    assert Bridge().get_container(None) is None  # type: ignore[arg-type]




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
