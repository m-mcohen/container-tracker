from pathlib import Path

import pytest

from container_tracker.core import persistence


class TestDataDir:
    def test_data_dir_on_windows(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(persistence, "_PLATFORM", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        result = persistence.data_dir()
        assert result == tmp_path / "ContainerTracker"
        assert result.is_dir()

    def test_paths_derive_from_data_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(persistence, "_PLATFORM", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        d = persistence.data_dir()
        assert persistence.config_path() == d / "config.json"
        assert persistence.tracking_data_path() == d / "tracking_data.json"
        assert persistence.log_path() == d / "tracker.log"


class TestConfig:
    def _setup_tmp_appdata(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(persistence, "_PLATFORM", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path))

    def test_load_config_missing_returns_defaults(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._setup_tmp_appdata(monkeypatch, tmp_path)
        cfg = persistence.load_config()
        assert cfg == {
            "company_name": "",
            "contact_email": "",
            "excel_path": "",
            "dark_mode": False,
            "dismissed": [],
        }

    def test_save_then_load_roundtrip(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._setup_tmp_appdata(monkeypatch, tmp_path)
        original = {
            "company_name": "Acme Imports",
            "contact_email": "ops@acme.test",
            "excel_path": str(tmp_path / "containers.xlsx"),
            "dark_mode": True,
            "dismissed": ["MSKU1111111"],
        }
        persistence.save_config(original)
        loaded = persistence.load_config()
        assert loaded == original

    def test_save_strips_api_key_field(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Spec §3/§10.3: api_key must NEVER appear in config.json."""
        self._setup_tmp_appdata(monkeypatch, tmp_path)
        persistence.save_config({
            "company_name": "Acme",
            "contact_email": "a@b.c",
            "excel_path": "",
            "dark_mode": False,
            "dismissed": [],
            "api_key": "SHOULD-NEVER-APPEAR",
        })
        raw = persistence.config_path().read_text()
        assert "SHOULD-NEVER-APPEAR" not in raw
        assert "api_key" not in raw


class TestKeyring:
    def test_get_api_token_returns_stored_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        store: dict[tuple[str, str], str] = {
            (persistence.KEYRING_SERVICE, persistence.KEYRING_USER): "tok-123"
        }
        monkeypatch.setattr(persistence._keyring, "get_password", lambda s, u: store.get((s, u)))
        assert persistence.get_api_token() == "tok-123"

    def test_get_api_token_empty_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(persistence._keyring, "get_password", lambda s, u: None)
        assert persistence.get_api_token() == ""

    def test_set_api_token_stores_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        store: dict[tuple[str, str], str] = {}
        def set_password(s: str, u: str, v: str) -> None:
            store[(s, u)] = v
        monkeypatch.setattr(persistence._keyring, "set_password", set_password)
        persistence.set_api_token("tok-new")
        assert store[(persistence.KEYRING_SERVICE, persistence.KEYRING_USER)] == "tok-new"

    def test_get_api_token_swallows_backend_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def explode(s: str, u: str) -> None:
            raise RuntimeError("no backend")
        monkeypatch.setattr(persistence._keyring, "get_password", explode)
        assert persistence.get_api_token() == ""


class TestIsFirstRun:
    def test_empty_config_and_no_token_is_first_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(persistence, "get_api_token", lambda: "")
        assert persistence.is_first_run({"company_name": "", "contact_email": ""}) is True

    def test_company_present_is_not_first_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(persistence, "get_api_token", lambda: "")
        assert persistence.is_first_run({"company_name": "Acme", "contact_email": ""}) is False

    def test_token_present_is_not_first_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(persistence, "get_api_token", lambda: "tok")
        assert persistence.is_first_run({"company_name": "", "contact_email": ""}) is False


class TestTrackingData:
    def test_roundtrip_empty(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(persistence, "_PLATFORM", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        persistence.save_tracking_data({})
        assert persistence.load_tracking_data() == {}

    def test_roundtrip_records(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(persistence, "_PLATFORM", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        db = {
            "MSKU1234567": {"status": "SAILING", "delay_days_int": 3, "vessel": "MV TEST"},
            "CMAU7654321": {"status": "ARRIVED", "delay_days_int": 0},
        }
        persistence.save_tracking_data(db)
        assert persistence.load_tracking_data() == db
