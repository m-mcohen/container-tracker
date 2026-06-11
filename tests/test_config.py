"""Unit tests for container_tracker.core.config — folder & token migrations
plus boot() ordering and idempotency."""

import json

from container_tracker.core import config as ct_config
from container_tracker.core import credentials
from container_tracker.core.config import (
    _migrate_data_folder,
    boot,
    is_first_run,
    load_config,
    migrate_token_from_config,
    save_config,
)


class TestMigrateDataFolder:
    def test_moves_known_files_and_removes_empty_src(self, tmp_path):
        src = tmp_path / "old"
        dst = tmp_path / "new"
        src.mkdir()
        dst.mkdir()
        (src / "config.json").write_text("{}")
        (src / "tracking_data.json").write_text("{}")

        moved = _migrate_data_folder(src, dst)

        assert moved == 2
        assert (dst / "config.json").exists()
        assert (dst / "tracking_data.json").exists()
        assert not src.exists()  # cleaned up since it was emptied

    def test_does_not_overwrite_existing_dst_files(self, tmp_path):
        src = tmp_path / "old"
        dst = tmp_path / "new"
        src.mkdir()
        dst.mkdir()
        (src / "config.json").write_text('{"src": true}')
        (dst / "config.json").write_text('{"dst": true}')

        moved = _migrate_data_folder(src, dst)

        assert moved == 0
        # dst preserved
        assert "dst" in (dst / "config.json").read_text()

    def test_no_op_when_src_missing(self, tmp_path):
        dst = tmp_path / "new"
        dst.mkdir()
        assert _migrate_data_folder(tmp_path / "does-not-exist", dst) == 0


class TestJsonHelpers:
    def test_corrupt_json_preserved_as_bak_and_default_returned(self, tmp_path):
        f = tmp_path / "tracking_data.json"
        f.write_text('{"MSKU1234567": {"status": "SAIL')  # truncated write

        result = ct_config.load_json(f, {})

        assert result == {}
        bak = tmp_path / "tracking_data.json.corrupt.bak"
        assert bak.exists()
        assert bak.read_text().startswith('{"MSKU1234567"')

    def test_save_json_is_atomic_no_tmp_left_behind(self, tmp_path):
        f = tmp_path / "config.json"
        ct_config.save_json(f, {"a": 1})
        assert json.loads(f.read_text()) == {"a": 1}
        assert not (tmp_path / "config.json.tmp").exists()

    def test_save_json_overwrites_existing(self, tmp_path):
        f = tmp_path / "config.json"
        ct_config.save_json(f, {"a": 1})
        ct_config.save_json(f, {"b": 2})
        assert json.loads(f.read_text()) == {"b": 2}

    def test_load_json_missing_file_returns_default(self, tmp_path):
        assert ct_config.load_json(tmp_path / "nope.json", {"x": 1}) == {"x": 1}


class TestMigrateTokenFromConfig:
    def test_strips_shipsgo_api_token_key(self, mock_keyring):
        cfg = {"shipsgo_api_token": "tok-1", "company_name": "Acme"}
        changed = migrate_token_from_config(cfg)
        assert changed is True
        assert "shipsgo_api_token" not in cfg
        assert mock_keyring.store[(credentials.KEYRING_SERVICE,
                                   credentials.KEYRING_USER)] == "tok-1"

    def test_strips_api_key_key(self, mock_keyring):
        # The monolith handled BOTH legacy field names. See container_tracker_gui.py:276
        # in the pre-extraction file: for key in ("shipsgo_api_token", "api_key").
        cfg = {"api_key": "tok-2"}
        changed = migrate_token_from_config(cfg)
        assert changed is True
        assert "api_key" not in cfg
        assert mock_keyring.store[(credentials.KEYRING_SERVICE,
                                   credentials.KEYRING_USER)] == "tok-2"

    def test_returns_false_when_nothing_to_migrate(self, mock_keyring):
        cfg = {"company_name": "Acme"}
        assert migrate_token_from_config(cfg) is False
        assert mock_keyring.set_calls == []


class TestIsFirstRun:
    def test_true_when_no_company_and_no_token(self, mock_keyring):
        assert is_first_run({}) is True

    def test_false_when_company_set(self, mock_keyring):
        assert is_first_run({"company_name": "Acme"}) is False

    def test_false_when_keyring_token_set(self, mock_keyring):
        mock_keyring.store[(credentials.KEYRING_SERVICE,
                            credentials.KEYRING_USER)] = "tok"
        assert is_first_run({}) is False


class TestBoot:
    def test_runs_all_migrations_in_order(
        self, isolated_data_dir, mock_keyring, monkeypatch
    ):
        # Seed: legacy keyring entry + config with a legacy token field.
        mock_keyring.store[(credentials.LEGACY_KEYRING_SERVICE,
                            credentials.KEYRING_USER)] = "legacy-keyring-tok"
        save_config({"company_name": "Acme", "shipsgo_api_token": "config-tok"})

        # Skip folder migrations (no legacy folder layout under tmp_path).
        monkeypatch.setattr(ct_config, "run_folder_migrations", lambda: None)

        boot()

        # 1. Token-from-config migrated FIRST → config-tok lands in keyring.
        # 2. migrate_keyring then sees the new service is already populated and
        #    skips the legacy → new copy, but still deletes the legacy entry.
        # Net result: current install (config-tok) wins over the previous
        # brand's stale keyring entry.
        assert mock_keyring.store[(credentials.KEYRING_SERVICE,
                                   credentials.KEYRING_USER)] == "config-tok"
        assert (credentials.LEGACY_KEYRING_SERVICE,
                credentials.KEYRING_USER) not in mock_keyring.store

        # Config file rewritten without the legacy field.
        cfg = load_config()
        assert "shipsgo_api_token" not in cfg
        assert cfg["company_name"] == "Acme"

    def test_idempotent_no_churn_on_repeat_call(
        self, isolated_data_dir, mock_keyring, monkeypatch
    ):
        # First call to migrate everything.
        mock_keyring.store[(credentials.LEGACY_KEYRING_SERVICE,
                            credentials.KEYRING_USER)] = "legacy-tok"
        save_config({"company_name": "Acme", "shipsgo_api_token": "config-tok"})
        monkeypatch.setattr(ct_config, "run_folder_migrations", lambda: None)

        boot()

        # Reset counters and snapshot mtime AFTER the first migration.
        mock_keyring.reset_call_counts()
        mtime_before = ct_config.CONFIG_FILE.stat().st_mtime_ns

        # Second call must produce zero keyring writes/deletes and zero config
        # mtime change. ("Idempotent" = no churn, not just no crash.)
        boot()

        assert mock_keyring.set_calls == [], (
            f"second boot() wrote to keyring: {mock_keyring.set_calls}"
        )
        assert mock_keyring.delete_calls == [], (
            f"second boot() deleted keyring entries: {mock_keyring.delete_calls}"
        )
        assert ct_config.CONFIG_FILE.stat().st_mtime_ns == mtime_before, (
            "second boot() rewrote config.json"
        )
