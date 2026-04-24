"""Unit tests for SetupDialog."""
from __future__ import annotations

import pytest

from container_tracker.ui.dialogs import SetupDialog


class TestSetupDialogSkeleton:
    def test_welcome_mode_has_no_cancel_button(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        assert dlg._save_button is not None
        assert dlg._cancel_button is None

    def test_settings_mode_has_cancel_button(self, qapp) -> None:
        dlg = SetupDialog(mode="settings")
        assert dlg._save_button is not None
        assert dlg._cancel_button is not None

    def test_welcome_mode_save_disabled_by_default(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        assert dlg._save_button.isEnabled() is False

    def test_welcome_mode_has_three_input_fields(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        assert dlg._company_input is not None
        assert dlg._api_key_input is not None
        assert dlg._email_input is not None

    def test_welcome_mode_prepopulates_empty(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        assert dlg._company_input.text() == ""
        assert dlg._api_key_input.text() == ""
        assert dlg._email_input.text() == ""

    def test_settings_mode_prepopulates_from_initial_values(self, qapp) -> None:
        dlg = SetupDialog(
            mode="settings",
            initial_company="Acme",
            initial_email="ops@acme.test",
            initial_api_key_set=True,
        )
        assert dlg._company_input.text() == "Acme"
        assert dlg._email_input.text() == "ops@acme.test"
        # API key field stays empty in settings mode (placeholder instead).
        assert dlg._api_key_input.text() == ""
        assert dlg._api_key_input.placeholderText() == "Leave empty to keep current key"

    def test_api_key_field_is_password_mode(self, qapp) -> None:
        from PySide6.QtWidgets import QLineEdit
        dlg = SetupDialog(mode="welcome")
        assert dlg._api_key_input.echoMode() == QLineEdit.EchoMode.Password

    def test_settings_mode_shows_version_label(self, qapp) -> None:
        dlg = SetupDialog(mode="settings", app_version="1.1.0")
        # Expose via _version_label text.
        assert "1.1.0" in dlg._version_label.text()

    def test_welcome_mode_does_not_show_version_label(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        assert dlg._version_label is None

    def test_welcome_mode_window_title(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        assert "Welcome" in dlg.windowTitle()

    def test_settings_mode_window_title(self, qapp) -> None:
        dlg = SetupDialog(mode="settings")
        assert "Settings" in dlg.windowTitle()

    def test_invalid_mode_raises(self, qapp) -> None:
        with pytest.raises(ValueError):
            SetupDialog(mode="bogus")  # type: ignore[arg-type]


class TestSetupDialogValidation:
    def test_save_enables_when_all_valid(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        dlg._company_input.setText("Acme")
        dlg._api_key_input.setText("12345678-1234-1234-1234-123456789012")
        dlg._email_input.setText("ops@acme.test")
        # Simulate Qt text-changed firing.
        dlg._revalidate()
        assert dlg._save_button.isEnabled() is True

    def test_save_disabled_when_company_missing(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        dlg._api_key_input.setText("12345678-1234-1234-1234-123456789012")
        dlg._email_input.setText("ops@acme.test")
        dlg._revalidate()
        assert dlg._save_button.isEnabled() is False

    def test_error_label_hidden_until_touched(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        dlg.show()  # required for isVisible() to return True on descendants
        try:
            # Untouched — hidden.
            assert dlg._company_error.isHidden()
            # Touch + revalidate.
            dlg._mark_touched("company")
            dlg._revalidate()
            assert dlg._company_error.isVisible() is True
        finally:
            dlg.close()

    def test_error_label_shows_message_for_invalid_api_key(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        dlg._api_key_input.setText("too-short")
        dlg._mark_touched("api_key")
        dlg._revalidate()
        assert "doesn't look right" in dlg._api_key_error.text().lower()

    def test_error_label_hides_when_field_corrected(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        dlg.show()  # required for isVisible() to return True
        try:
            dlg._api_key_input.setText("bad")
            dlg._mark_touched("api_key")
            dlg._revalidate()
            assert dlg._api_key_error.isVisible() is True
            dlg._api_key_input.setText("12345678-1234-1234-1234-123456789012")
            dlg._revalidate()
            assert dlg._api_key_error.isHidden()
        finally:
            dlg.close()

    def test_settings_mode_empty_api_key_valid_when_key_already_set(self, qapp) -> None:
        dlg = SetupDialog(
            mode="settings",
            initial_company="Acme",
            initial_email="ops@acme.test",
            initial_api_key_set=True,
        )
        # All fields pre-populated (API key left empty since it's set).
        dlg._revalidate()
        assert dlg._save_button.isEnabled() is True

    def test_settings_mode_empty_api_key_invalid_when_key_not_set(self, qapp) -> None:
        dlg = SetupDialog(
            mode="settings",
            initial_company="Acme",
            initial_email="ops@acme.test",
            initial_api_key_set=False,
        )
        dlg._revalidate()
        assert dlg._save_button.isEnabled() is False

    def test_settings_mode_replacing_api_key_validates_new_value(self, qapp) -> None:
        dlg = SetupDialog(
            mode="settings",
            initial_company="Acme",
            initial_email="ops@acme.test",
            initial_api_key_set=True,
        )
        dlg.show()  # required for isVisible() to return True
        try:
            dlg._api_key_input.setText("too-short")
            dlg._mark_touched("api_key")
            dlg._revalidate()
            assert dlg._save_button.isEnabled() is False
            assert dlg._api_key_error.isVisible() is True
        finally:
            dlg.close()
