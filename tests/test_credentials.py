"""Unit tests for container_tracker.core.credentials.

The migrate_keyring tests are load-bearing for v1.0.0 → v1.1 upgrades — the
legacy ``KenGabbayTracker_shipsgo_api`` service must move to
``ContainerTracker_shipsgo_api`` exactly once.
"""

from container_tracker.core import credentials
from container_tracker.core.credentials import (
    KEYRING_SERVICE,
    KEYRING_USER,
    LEGACY_KEYRING_SERVICE,
    get_api_token,
    migrate_keyring,
    set_api_token,
)


class TestGetSetApiToken:
    def test_get_returns_empty_when_unset(self, mock_keyring):
        assert get_api_token() == ""

    def test_set_then_get_round_trip(self, mock_keyring):
        set_api_token("abc-token")
        assert get_api_token() == "abc-token"

    def test_get_swallows_keyring_exceptions(self, mock_keyring, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("backend offline")
        monkeypatch.setattr(credentials.keyring, "get_password", boom)
        assert get_api_token() == ""


class TestMigrateKeyring:
    def test_no_op_when_legacy_is_empty(self, mock_keyring):
        migrate_keyring()
        assert mock_keyring.set_calls == []
        assert mock_keyring.delete_calls == []

    def test_copies_legacy_into_new_service_then_deletes(self, mock_keyring):
        mock_keyring.store[(LEGACY_KEYRING_SERVICE, KEYRING_USER)] = "legacy-token"

        migrate_keyring()

        # New service got the value
        assert mock_keyring.store[(KEYRING_SERVICE, KEYRING_USER)] == "legacy-token"
        # Legacy entry was deleted
        assert (LEGACY_KEYRING_SERVICE, KEYRING_USER) not in mock_keyring.store
        assert (LEGACY_KEYRING_SERVICE, KEYRING_USER) in mock_keyring.delete_calls

    def test_does_not_overwrite_existing_new_entry(self, mock_keyring):
        mock_keyring.store[(LEGACY_KEYRING_SERVICE, KEYRING_USER)] = "legacy-token"
        mock_keyring.store[(KEYRING_SERVICE, KEYRING_USER)] = "current-token"

        migrate_keyring()

        # Current value preserved, legacy still deleted.
        assert mock_keyring.store[(KEYRING_SERVICE, KEYRING_USER)] == "current-token"
        assert (LEGACY_KEYRING_SERVICE, KEYRING_USER) not in mock_keyring.store

    def test_idempotent_on_repeat_call(self, mock_keyring):
        mock_keyring.store[(LEGACY_KEYRING_SERVICE, KEYRING_USER)] = "legacy-token"
        migrate_keyring()
        mock_keyring.reset_call_counts()

        migrate_keyring()

        assert mock_keyring.set_calls == []
        assert mock_keyring.delete_calls == []
