"""Unit tests for container_tracker.bridge.

Bridge methods are pure Python; pywebview / JS integration is verified
manually via the stash-to-global probe (see Step 4 / Step 5 commit
bodies), not here.
"""

import json
import logging
from pathlib import Path

import pytest

from container_tracker import bridge as ct_bridge
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
    "last_refreshed",
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
    # Step 6 regression test: extract_fields now preserves carrier.scac
    # and the bridge prefers it over resolve_scac(carrier_name).
    assert row["scac"] == "EGLV"
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
        "excel_path": "",
    }


def test_get_settings_no_token(isolated_data_dir, mock_keyring):
    ct_config.save_config({
        "company_name": "ACME", "contact_email": "", "excel_path": "",
        "dark_mode": False, "dismissed": [],
    })
    # mock_keyring is empty by default

    assert Bridge().get_settings()["api_token_present"] is False


# ---------------------------------------------------------------------------
# SCAC translation (Task 1 Step 6)
# ---------------------------------------------------------------------------

def test_scac_uses_cached_field_when_present(sample_tracking_db):
    """Bridge prefers rec['scac'] over resolve_scac(carrier_name).

    A record with the long carrier name AND a cached scac field should
    surface the cached scac — that's exactly the case resolve_scac can't
    handle on its own (long names are not in CARRIER_SCAC_MAP).
    """
    sample_tracking_db({
        "EVRG1234567": {
            "container_number": "EVRG1234567",
            "carrier": "EVERGREEN MARINE CORP",
            "scac": "EGLV",
            "status": "SAILING",
        },
    })
    rows = Bridge().list_containers()
    assert rows[0]["scac"] == "EGLV"


def test_scac_falls_back_to_resolve_for_legacy_records(sample_tracking_db):
    """Records missing the scac field fall back to resolve_scac(carrier).

    Legacy records (refreshed before the Step 6 fix) only have carrier;
    the bridge must still produce a sensible scac via CARRIER_SCAC_MAP.
    """
    sample_tracking_db({
        "MSCU2222222": {
            "container_number": "MSCU2222222",
            "carrier": "EVERGREEN",  # short name in CARRIER_SCAC_MAP
            "status": "SAILING",
        },
    })
    rows = Bridge().list_containers()
    assert rows[0]["scac"] == "EGLV"


# ---------------------------------------------------------------------------
# Refresh / mutations / settings (Tasks 2-4 Step 6)
#
# All ShipsGo API calls are mocked via _FakeShipsGoClient — never hit the
# network. Bridge.save_json calls are also tracked via a small spy when
# tests need to assert "wrote exactly once".
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


class _FakeShipsGoClient:
    """Drop-in replacement for ShipsGoClient. Tests configure the
    listing, get-shipment results, and create-shipment behavior;
    instances record call args for assertions."""

    def __init__(
        self,
        listing=None,
        get_results=None,
        get_raises=None,
        create_response=None,
        list_raises=None,
    ):
        self._listing = listing or []
        self._get_results = get_results or {}
        self._get_raises = get_raises or {}
        self._create_response = create_response
        self._list_raises = list_raises
        self.list_calls = 0
        self.get_calls: list[str] = []
        self.create_calls: list[dict] = []

    @classmethod
    def factory(cls, **kwargs):
        """Return a callable that pretends to be ShipsGoClient(token).
        Captures the constructed instance so tests can inspect calls."""
        captured: dict = {}
        def make(token):
            inst = cls(**kwargs)
            captured["instance"] = inst
            captured["token"] = token
            return inst
        make.captured = captured
        return make

    def list_shipments(self, take=100):
        self.list_calls += 1
        if self._list_raises is not None:
            raise self._list_raises
        return list(self._listing)

    def get_shipment(self, sid):
        self.get_calls.append(sid)
        if sid in self._get_raises:
            raise self._get_raises[sid]
        return self._get_results.get(sid, {})

    def create_shipment(self, container_number="", carrier_scac=""):
        self.create_calls.append({"container_number": container_number,
                                  "carrier_scac": carrier_scac})
        if isinstance(self._create_response, Exception):
            raise self._create_response
        return self._create_response or {}


def _fixture_payload():
    """The sanitized ShipsGo response from the shared fixture."""
    return json.loads((FIXTURES / "shipsgo_response.json").read_text())


@pytest.fixture
def patched_token(monkeypatch):
    """Pretend the keyring has a token so refresh/add don't bail early."""
    monkeypatch.setattr(ct_bridge.ct_credentials, "get_api_token",
                        lambda: "fake-token")


@pytest.fixture
def save_spy(monkeypatch):
    """Wrap ct_config.save_json to count invocations on TRACKING_DB_FILE."""
    real = ct_config.save_json
    calls = {"tracking_writes": 0, "config_writes": 0, "all": []}
    def wrapped(path, data):
        calls["all"].append((path, data))
        if Path(path) == ct_config.TRACKING_DB_FILE:
            calls["tracking_writes"] += 1
        elif Path(path) == ct_config.CONFIG_FILE:
            calls["config_writes"] += 1
        return real(path, data)
    monkeypatch.setattr(ct_bridge.ct_config, "save_json", wrapped)
    monkeypatch.setattr(ct_config, "save_json", wrapped)
    return calls


# --- refresh_all -----------------------------------------------------------

def test_refresh_all_no_token_returns_error_dict(isolated_data_dir, mock_keyring):
    # mock_keyring empty → get_api_token returns "".
    result = Bridge().refresh_all()
    assert result == {
        "updated": 0, "failed": [],
        "duration_ms": 0, "error": "API token not configured",
        "excel_read_failed": False, "excel_write_failed": False,
        "excel_missing": False,
        "unmatched": [], "excel_rows_updated": 0,
    }


def test_refresh_all_list_shipments_failure(isolated_data_dir, monkeypatch,
                                             patched_token, sample_tracking_db):
    sample_tracking_db()
    boom = RuntimeError("boom")
    factory = _FakeShipsGoClient.factory(list_raises=boom)
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().refresh_all()

    assert result["updated"] == 0
    assert result["failed"] == []
    assert result["error"].startswith("list_shipments failed:")


def test_refresh_all_partial_failure(isolated_data_dir, monkeypatch,
                                      patched_token, save_spy):
    # Two records — one succeeds, one fails.
    payload = _fixture_payload()
    inner = payload["shipment"]
    cn_good = inner["container_number"].upper()
    cn_bad = "BADX9999999"
    db = {
        cn_good: {"container_number": cn_good, "shipment_id": inner["id"]},
        cn_bad:  {"container_number": cn_bad,  "shipment_id": "bad-sid"},
    }
    ct_config.TRACKING_DB_FILE.write_text(json.dumps(db))

    factory = _FakeShipsGoClient.factory(
        listing=[{"id": inner["id"], "container_number": cn_good}],
        get_results={inner["id"]: payload},
        get_raises={"bad-sid": RuntimeError("404")},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().refresh_all()

    assert result["updated"] == 1
    assert result["error"] is None
    assert len(result["failed"]) == 1
    assert result["failed"][0]["cn"] == cn_bad
    assert "404" in result["failed"][0]["error"]
    # Single write at end (legacy behavior).
    assert save_spy["tracking_writes"] == 1
    # Persisted state has the success record updated.
    persisted = json.loads(ct_config.TRACKING_DB_FILE.read_text())
    assert persisted[cn_good]["status"] == "SAILING"
    assert "last_refreshed" in persisted[cn_good]


def test_refresh_all_writes_once_at_end(isolated_data_dir, monkeypatch,
                                         patched_token, save_spy):
    payload = _fixture_payload()
    inner = payload["shipment"]
    base_cn = inner["container_number"].upper()
    db = {f"{base_cn[:-3]}{i:03d}": {"container_number": f"{base_cn[:-3]}{i:03d}",
                                       "shipment_id": f"sid-{i}"}
          for i in range(3)}
    ct_config.TRACKING_DB_FILE.write_text(json.dumps(db))

    factory = _FakeShipsGoClient.factory(
        listing=[],
        get_results={f"sid-{i}": payload for i in range(3)},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().refresh_all()

    assert result["updated"] == 3
    assert save_spy["tracking_writes"] == 1


def test_refresh_all_resolves_cn_to_sid_via_list_shipments(
        isolated_data_dir, monkeypatch, patched_token):
    # Record has no shipment_id; the list_shipments map provides it.
    payload = _fixture_payload()
    inner = payload["shipment"]
    cn = inner["container_number"].upper()
    db = {cn: {"container_number": cn}}
    ct_config.TRACKING_DB_FILE.write_text(json.dumps(db))

    factory = _FakeShipsGoClient.factory(
        listing=[{"id": inner["id"], "container_number": cn}],
        get_results={inner["id"]: payload},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().refresh_all()

    assert result["updated"] == 1
    assert result["error"] is None
    persisted = json.loads(ct_config.TRACKING_DB_FILE.read_text())
    assert persisted[cn]["shipment_id"] == inner["id"]


# --- refresh_one -----------------------------------------------------------

def test_refresh_one_no_token_returns_error_dict(isolated_data_dir,
                                                   mock_keyring):
    result = Bridge().refresh_one("ABCD1234567")
    assert result == {"cn": "ABCD1234567", "ok": False,
                      "error": "API token not configured"}


# --- add_container ---------------------------------------------------------

def test_add_container_creates_record_and_calls_create_shipment(
        isolated_data_dir, monkeypatch, patched_token, save_spy):
    factory = _FakeShipsGoClient.factory(
        create_response={"id": "abc", "container_number": "MSKU1234567"},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().add_container("MSKU1234567", "MAERSK")

    assert result["ok"] is True
    assert result["was_existing"] is False
    assert result["error"] is None
    assert result["container"]["cn"] == "MSKU1234567"
    db = ct_config.load_tracking_db()
    assert db["MSKU1234567"]["shipment_id"] == "abc"
    assert factory.captured["instance"].create_calls == [
        {"container_number": "MSKU1234567", "carrier_scac": "MAEU"},
    ]
    # Add path writes once on success.
    assert save_spy["tracking_writes"] == 1


def test_add_container_invalid_length(isolated_data_dir, monkeypatch,
                                       patched_token):
    factory = _FakeShipsGoClient.factory()
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().add_container("ABC123", "MAERSK")

    assert result["ok"] is False
    assert result["error"] == "Container number must be 11 characters"
    assert result["container"] is None
    # Fake never instantiated because we bail before constructing the client.
    assert "instance" not in factory.captured


def test_add_container_local_duplicate(isolated_data_dir, monkeypatch,
                                        patched_token, sample_tracking_db):
    sample_tracking_db()  # fixture cn = EVRG1234567
    factory = _FakeShipsGoClient.factory()
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().add_container("EVRG1234567", "EVERGREEN")

    assert result["ok"] is False
    assert result["error"] == "already_exists_local"
    assert "instance" not in factory.captured


def test_add_container_402_not_enough_credits(isolated_data_dir, monkeypatch,
                                                patched_token, save_spy):
    factory = _FakeShipsGoClient.factory(
        create_response={"error": "NOT_ENOUGH_CREDITS"},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().add_container("MSKU1234567", "MAERSK")

    assert result["ok"] is False
    assert result["error"] == "NOT_ENOUGH_CREDITS"
    # DB must not be mutated.
    assert ct_config.load_tracking_db() == {}
    assert save_spy["tracking_writes"] == 0


def test_add_container_409_already_exists(isolated_data_dir, monkeypatch,
                                            patched_token):
    factory = _FakeShipsGoClient.factory(
        create_response={"already_exists": True, "id": "x"},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().add_container("MSKU1234567", "MAERSK")

    # 409 is a successful track operation: the user wants the row, the
    # bridge returns ok=True with was_existing=True so JS renders the row
    # and shows a benign info toast (not an error).
    assert result["ok"] is True
    assert result["was_existing"] is True
    assert result["error"] is None
    assert result["container"]["cn"] == "MSKU1234567"
    db = ct_config.load_tracking_db()
    assert "MSKU1234567" in db
    assert db["MSKU1234567"]["shipment_id"] == "x"


# --- remove_container ------------------------------------------------------

def test_remove_container_existing(isolated_data_dir, sample_tracking_db,
                                     save_spy):
    records = sample_tracking_db()
    cn = next(iter(records))
    # sample_tracking_db itself writes the file before save_spy is engaged
    # (different ordering); reset count so we measure only remove.
    save_spy["tracking_writes"] = 0

    result = Bridge().remove_container(cn)

    assert result == {"ok": True, "error": None}
    assert ct_config.load_tracking_db() == {}
    assert save_spy["tracking_writes"] == 1


def test_remove_container_missing_is_idempotent(isolated_data_dir, save_spy):
    save_spy["tracking_writes"] = 0
    result = Bridge().remove_container("ZZZZ9999999")
    assert result == {"ok": True, "error": None}
    # Idempotent → no save side effect when cn wasn't in the DB.
    assert save_spy["tracking_writes"] == 0


# --- save_settings ---------------------------------------------------------

def test_save_settings_company_only(isolated_data_dir, mock_keyring):
    ct_config.save_config({
        "company_name": "OLD CO", "contact_email": "", "excel_path": "",
        "dark_mode": False, "dismissed": [],
    })

    result = Bridge().save_settings("ACME LTD", None)

    assert result == {"ok": True, "error": None}
    assert ct_config.load_config()["company_name"] == "ACME LTD"
    # Keyring untouched.
    assert mock_keyring.set_calls == []


def test_save_settings_with_token(isolated_data_dir, mock_keyring):
    ct_config.save_config({
        "company_name": "ACME", "contact_email": "", "excel_path": "",
        "dark_mode": False, "dismissed": [],
    })

    result = Bridge().save_settings("ACME", "abc123-token")

    assert result == {"ok": True, "error": None}
    assert credentials.get_api_token() == "abc123-token"


def test_save_settings_empty_token_doesnt_clear(isolated_data_dir,
                                                  mock_keyring):
    ct_config.save_config({
        "company_name": "ACME", "contact_email": "", "excel_path": "",
        "dark_mode": False, "dismissed": [],
    })
    mock_keyring.store[(credentials.KEYRING_SERVICE,
                        credentials.KEYRING_USER)] = "orig"

    # Empty string and None must both be no-ops on the keyring.
    Bridge().save_settings("ACME", "")
    assert credentials.get_api_token() == "orig"

    Bridge().save_settings("ACME", None)
    assert credentials.get_api_token() == "orig"

    # Whitespace-only also doesn't clear.
    Bridge().save_settings("ACME", "   ")
    assert credentials.get_api_token() == "orig"


# ---------------------------------------------------------------------------
# Excel I/O integration (Step 6.5)
#
# refresh_all extends to read CNs from the linked workbook, surface
# unmatched CNs in the result, and write the workbook on success — all
# while keeping locked-file errors from aborting the data sync.
# ---------------------------------------------------------------------------

def _link_workbook(path):
    """Helper: write a config.json that links the given xlsx path. Caller
    must already be inside isolated_data_dir."""
    ct_config.save_config({
        "company_name": "", "contact_email": "", "excel_path": str(path),
        "dark_mode": False, "dismissed": [],
    })


def test_refresh_all_no_excel_path_skips_excel_io(
        isolated_data_dir, monkeypatch, patched_token, sample_tracking_db):
    """No linked workbook → Excel keys all default; no openpyxl calls."""
    sample_tracking_db()
    payload = _fixture_payload()
    factory = _FakeShipsGoClient.factory(
        listing=[],
        get_results={payload["shipment"]["id"]: payload},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)
    # Sentinel: replacing the helpers with raisers proves they're never
    # called when no path is configured.
    def boom(*a, **k):  # pragma: no cover - only fires if test fails
        raise AssertionError("excel helper should not be called")
    monkeypatch.setattr(ct_bridge, "read_containers_from_excel", boom)
    monkeypatch.setattr(ct_bridge, "update_excel_with_tracking", boom)

    result = Bridge().refresh_all()

    assert result["excel_read_failed"] is False
    assert result["excel_write_failed"] is False
    assert result["unmatched"] == []
    assert result["excel_rows_updated"] == 0


def test_refresh_all_reads_cns_from_excel_and_adds_to_db(
        isolated_data_dir, monkeypatch, patched_token, sample_workbook):
    """A CN that's only in Excel gets stubbed into db; if it's not on
    ShipsGo, it lands in result["unmatched"]."""
    wb_path = sample_workbook(rows=("EVRG7777777",))
    _link_workbook(wb_path)
    factory = _FakeShipsGoClient.factory(listing=[], get_results={})
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().refresh_all()

    assert result["error"] is None
    assert "EVRG7777777" in result["unmatched"]
    # The stub also got persisted to tracking_data.json.
    persisted = json.loads(ct_config.TRACKING_DB_FILE.read_text())
    assert "EVRG7777777" in persisted


def test_refresh_all_excel_path_missing_file(
        isolated_data_dir, monkeypatch, patched_token, sample_tracking_db,
        save_spy, tmp_path):
    """Linked workbook path that no longer exists → excel_missing=True,
    Excel read+write skipped, but the API fetch still runs and
    tracking_data.json is still written. Distinct from
    excel_read_failed (which is for raised exceptions during read)."""
    sample_tracking_db()
    save_spy["tracking_writes"] = 0
    payload = _fixture_payload()
    inner = payload["shipment"]
    # Path is configured but the file does NOT exist.
    ghost = tmp_path / "deleted_workbook.xlsx"
    assert not ghost.exists()
    _link_workbook(ghost)

    # Hard sentinel: Excel helpers must NOT be called when the file is
    # missing — both read and write should be short-circuited.
    def boom(*a, **k):  # pragma: no cover - only fires if test fails
        raise AssertionError("excel helper should not be called when file missing")
    monkeypatch.setattr(ct_bridge, "read_containers_from_excel", boom)
    monkeypatch.setattr(ct_bridge, "update_excel_with_tracking", boom)

    factory = _FakeShipsGoClient.factory(
        listing=[{"id": inner["id"], "container_number": inner["container_number"]}],
        get_results={inner["id"]: payload},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().refresh_all()

    assert result["excel_missing"] is True
    assert result["excel_read_failed"] is False
    assert result["excel_write_failed"] is False
    assert result["error"] is None
    # API fetch still ran and the JSON DB was still saved.
    assert factory.captured["instance"].list_calls == 1
    assert save_spy["tracking_writes"] == 1


def test_refresh_all_excel_locked_on_read(
        isolated_data_dir, monkeypatch, patched_token, sample_tracking_db,
        save_spy):
    """PermissionError during read → flag set, refresh still completes,
    tracking_data.json still written. Improvement over legacy's
    abort-on-locked-read."""
    sample_tracking_db()
    save_spy["tracking_writes"] = 0
    payload = _fixture_payload()
    inner = payload["shipment"]
    _link_workbook("C:/some/file.xlsx")
    # File "exists" — patch Path.exists to lie so the read branch fires.
    monkeypatch.setattr(ct_bridge.Path, "exists", lambda self: True)

    def locked(_):
        raise PermissionError("file in use")
    monkeypatch.setattr(ct_bridge, "read_containers_from_excel", locked)
    # Write is also short-circuited to avoid touching the fake path.
    monkeypatch.setattr(ct_bridge, "update_excel_with_tracking",
                        lambda p, db: 0)

    factory = _FakeShipsGoClient.factory(
        listing=[{"id": inner["id"], "container_number": inner["container_number"]}],
        get_results={inner["id"]: payload},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().refresh_all()

    assert result["excel_read_failed"] is True
    assert result["error"] is None
    # tracking_data.json still saved despite the read failure.
    assert save_spy["tracking_writes"] == 1


def test_refresh_all_excel_locked_on_write(
        isolated_data_dir, monkeypatch, patched_token, sample_tracking_db,
        save_spy):
    """PermissionError during write → flag set, db saved, refresh
    completes (legacy behavior matches; improvement is the explicit flag
    surfaced to JS)."""
    sample_tracking_db()
    save_spy["tracking_writes"] = 0
    payload = _fixture_payload()
    inner = payload["shipment"]
    _link_workbook("C:/some/file.xlsx")
    monkeypatch.setattr(ct_bridge.Path, "exists", lambda self: True)
    monkeypatch.setattr(ct_bridge, "read_containers_from_excel",
                        lambda p: [])

    def locked(p, db):
        raise PermissionError("file in use")
    monkeypatch.setattr(ct_bridge, "update_excel_with_tracking", locked)

    factory = _FakeShipsGoClient.factory(
        listing=[{"id": inner["id"], "container_number": inner["container_number"]}],
        get_results={inner["id"]: payload},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().refresh_all()

    assert result["excel_write_failed"] is True
    assert result["excel_read_failed"] is False
    assert result["error"] is None
    assert save_spy["tracking_writes"] == 1


def test_refresh_all_unmatched_cns_returned(
        isolated_data_dir, monkeypatch, patched_token, sample_workbook):
    """CN exists in Excel and DB (no shipment_id), API doesn't know it →
    flagged as unmatched, NOT failed."""
    wb_path = sample_workbook(rows=("UNKN1111111",))
    _link_workbook(wb_path)
    factory = _FakeShipsGoClient.factory(listing=[], get_results={})
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().refresh_all()

    assert result["unmatched"] == ["UNKN1111111"]
    # Failed list should NOT contain this CN — unmatched is its own bucket.
    assert all(f["cn"] != "UNKN1111111" for f in result["failed"])


def test_refresh_all_unmatched_excludes_dismissed(
        isolated_data_dir, monkeypatch, patched_token, sample_workbook):
    """A CN in Excel that the user has previously skipped should not
    re-appear in unmatched on subsequent refreshes."""
    wb_path = sample_workbook(rows=("DISM1111111",))
    ct_config.save_config({
        "company_name": "", "contact_email": "", "excel_path": str(wb_path),
        "dark_mode": False, "dismissed": ["DISM1111111"],
    })
    factory = _FakeShipsGoClient.factory(listing=[], get_results={})
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().refresh_all()

    assert "DISM1111111" not in result["unmatched"]
    # Dismissed CN must not be re-stubbed into the DB. If the DB ended up
    # empty (the no-other-CNs case), no save fires and the file may not
    # exist — both are correct.
    if ct_config.TRACKING_DB_FILE.exists():
        persisted = json.loads(ct_config.TRACKING_DB_FILE.read_text())
        assert "DISM1111111" not in persisted


def test_refresh_all_excel_rows_updated_count(
        isolated_data_dir, monkeypatch, patched_token, sample_workbook):
    """Successful Excel write → excel_rows_updated reflects the helper's
    return value."""
    wb_path = sample_workbook(rows=("MSCU1111111",))
    _link_workbook(wb_path)
    payload = _fixture_payload()
    inner = payload["shipment"]
    # Pre-populate db with the matching CN so phase 2 has work to do.
    ct_config.TRACKING_DB_FILE.write_text(json.dumps({
        "MSCU1111111": {"container_number": "MSCU1111111",
                        "shipment_id": inner["id"]},
    }))
    factory = _FakeShipsGoClient.factory(
        listing=[{"id": inner["id"], "container_number": "MSCU1111111"}],
        get_results={inner["id"]: payload},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)
    # Stub the writer so we don't depend on openpyxl's exact behavior;
    # the contract under test is "the helper's return value flows through".
    monkeypatch.setattr(ct_bridge, "update_excel_with_tracking",
                        lambda p, db: 7)

    result = Bridge().refresh_all()

    assert result["excel_rows_updated"] == 7
    assert result["excel_write_failed"] is False


# ---------------------------------------------------------------------------
# list_carriers / set_excel_path / create_excel_template / open_linked_excel
# ---------------------------------------------------------------------------

def test_list_carriers_returns_constant():
    from container_tracker.core.constants import CARRIER_NAMES
    assert Bridge().list_carriers() == list(CARRIER_NAMES)


def test_set_excel_path_valid(isolated_data_dir, sample_workbook):
    wb_path = sample_workbook()
    result = Bridge().set_excel_path(str(wb_path))
    assert result["ok"] is True
    assert result["error"] is None
    assert ct_config.load_config()["excel_path"] == str(wb_path)


def test_set_excel_path_missing_file(isolated_data_dir):
    ct_config.save_config({
        "company_name": "", "contact_email": "", "excel_path": "",
        "dark_mode": False, "dismissed": [],
    })
    result = Bridge().set_excel_path("C:/nope/missing.xlsx")
    assert result["ok"] is False
    assert "not found" in (result["error"] or "").lower()
    # Config not mutated on failure.
    assert ct_config.load_config()["excel_path"] == ""


def test_set_excel_path_empty_clears(isolated_data_dir, sample_workbook):
    wb_path = sample_workbook()
    Bridge().set_excel_path(str(wb_path))
    assert ct_config.load_config()["excel_path"] == str(wb_path)
    result = Bridge().set_excel_path("")
    assert result["ok"] is True
    assert ct_config.load_config()["excel_path"] == ""


def test_create_excel_template_writes_file_and_links(
        isolated_data_dir, tmp_path):
    target = tmp_path / "new_template.xlsx"
    result = Bridge().create_excel_template(str(target))
    assert result["ok"] is True
    assert target.exists()
    assert ct_config.load_config()["excel_path"] == str(target)


def test_create_excel_template_invalid_dir(isolated_data_dir):
    result = Bridge().create_excel_template("C:/nope/never/template.xlsx")
    assert result["ok"] is False
    assert "does not exist" in (result["error"] or "").lower()


def test_open_linked_excel_no_link(isolated_data_dir):
    ct_config.save_config({
        "company_name": "", "contact_email": "", "excel_path": "",
        "dark_mode": False, "dismissed": [],
    })
    result = Bridge().open_linked_excel()
    assert result["ok"] is False
    assert result["error"] == "No file linked"


def test_open_linked_excel_invokes_startfile(
        isolated_data_dir, monkeypatch, sample_workbook):
    """os.startfile is Windows-only; mock it so the test runs anywhere."""
    wb_path = sample_workbook()
    _link_workbook(wb_path)
    calls = []
    monkeypatch.setattr(ct_bridge.os, "startfile",
                        lambda p: calls.append(p), raising=False)
    result = Bridge().open_linked_excel()
    assert result["ok"] is True
    assert calls == [str(wb_path)]


# ---------------------------------------------------------------------------
# register_unmatched / dismiss_unmatched
# ---------------------------------------------------------------------------

def test_register_unmatched_calls_create_shipment_per_cn(
        isolated_data_dir, monkeypatch, patched_token):
    factory = _FakeShipsGoClient.factory(
        create_response={"id": "abc", "container_number": "X"},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    items = [
        {"cn": "EVRG1111111", "carrier": "EVERGREEN"},
        {"cn": "MSCU2222222", "carrier": "MSC"},
    ]
    result = Bridge().register_unmatched(items)

    assert result["registered"] == 2
    assert result["failed"] == []
    assert result["credits_used"] == 2
    calls = factory.captured["instance"].create_calls
    assert calls == [
        {"container_number": "EVRG1111111", "carrier_scac": "EGLV"},
        {"container_number": "MSCU2222222", "carrier_scac": "MSCU"},
    ]


def test_register_unmatched_402_stops_batch(
        isolated_data_dir, monkeypatch, patched_token):
    """NOT_ENOUGH_CREDITS bails the loop — credits don't recover mid-batch."""
    factory = _FakeShipsGoClient.factory(
        create_response={"error": "NOT_ENOUGH_CREDITS"},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    items = [
        {"cn": "AAAA1111111", "carrier": "EVERGREEN"},
        {"cn": "BBBB2222222", "carrier": "MSC"},
        {"cn": "CCCC3333333", "carrier": "MAERSK LINE"},
    ]
    result = Bridge().register_unmatched(items)

    assert result["registered"] == 0
    assert len(result["failed"]) == 1
    assert result["failed"][0]["error"] == "NOT_ENOUGH_CREDITS"
    # Only the first call was attempted; the loop broke immediately.
    assert len(factory.captured["instance"].create_calls) == 1


def test_register_unmatched_409_treated_as_success(
        isolated_data_dir, monkeypatch, patched_token):
    """already_exists isn't an error — counts as registered."""
    factory = _FakeShipsGoClient.factory(
        create_response={"already_exists": True, "id": "x"},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    result = Bridge().register_unmatched(
        [{"cn": "EVRG1111111", "carrier": "EVERGREEN"}])

    assert result["registered"] == 1
    assert result["failed"] == []
    db = ct_config.load_tracking_db()
    assert db["EVRG1111111"]["shipment_id"] == "x"


def test_register_unmatched_no_token(isolated_data_dir, mock_keyring):
    """Same fail-fast pattern as the rest of the bridge."""
    result = Bridge().register_unmatched(
        [{"cn": "EVRG1111111", "carrier": "EVERGREEN"}])
    assert result["registered"] == 0
    assert len(result["failed"]) == 1
    assert "API token" in result["failed"][0]["error"]


def test_register_unmatched_skips_blank_carrier(
        isolated_data_dir, monkeypatch, patched_token):
    factory = _FakeShipsGoClient.factory(
        create_response={"id": "abc"},
    )
    monkeypatch.setattr(ct_bridge, "ShipsGoClient", factory)

    items = [
        {"cn": "EVRG1111111", "carrier": ""},
        {"cn": "MSCU2222222", "carrier": "MSC"},
    ]
    result = Bridge().register_unmatched(items)

    # First item rejected before ShipsGo call; second succeeds.
    assert result["registered"] == 1
    assert len(result["failed"]) == 1
    assert result["failed"][0]["error"] == "missing carrier"


def test_dismiss_unmatched_appends_to_config(isolated_data_dir):
    ct_config.save_config({
        "company_name": "", "contact_email": "", "excel_path": "",
        "dark_mode": False, "dismissed": [],
    })
    result = Bridge().dismiss_unmatched(["AAAA1111111", "bbbb2222222"])
    assert result["ok"] is True
    cfg = ct_config.load_config()
    assert cfg["dismissed"] == ["AAAA1111111", "BBBB2222222"]


def test_dismiss_unmatched_idempotent(isolated_data_dir):
    ct_config.save_config({
        "company_name": "", "contact_email": "",
        "excel_path": "", "dark_mode": False,
        "dismissed": ["EXIST1111111"],
    })
    Bridge().dismiss_unmatched(["EXIST1111111", "NEWXX2222222"])
    Bridge().dismiss_unmatched(["EXIST1111111", "NEWXX2222222"])
    cfg = ct_config.load_config()
    # Each CN appears exactly once even after two dismiss calls.
    assert cfg["dismissed"].count("EXIST1111111") == 1
    assert cfg["dismissed"].count("NEWXX2222222") == 1
