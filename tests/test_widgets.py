"""Unit tests for UI widgets in container_tracker.ui.widgets."""
from __future__ import annotations

import pytest

from container_tracker.ui.widgets import StatCard


class TestStatCard:
    def test_displays_label_and_number(self, qapp) -> None:
        card = StatCard("Tracked", 12)
        assert card.label_text() == "Tracked"
        assert card.number_text() == "12"

    def test_number_can_be_string(self, qapp) -> None:
        card = StatCard("Delayed", "—")
        assert card.number_text() == "—"

    def test_set_number_updates_display(self, qapp) -> None:
        card = StatCard("Sailing", 0)
        card.set_number(5)
        assert card.number_text() == "5"

    def test_color_role_sets_statrole_property(self, qapp) -> None:
        card = StatCard("Sailing", 7, color_role="sailing")
        assert card.number_label_property("statRole") == "sailing"

    def test_default_color_role_is_none(self, qapp) -> None:
        """When no color role is given, the number gets no statRole (falls back to text_primary)."""
        card = StatCard("Tracked", 12)
        # Property returns None when unset (PySide6 returns None, not empty string).
        assert card.number_label_property("statRole") in (None, "")

    def test_frame_role_is_stat_card(self, qapp) -> None:
        """The StatCard must carry role='stat-card' so it picks up QFrame[role='stat-card'] QSS."""
        card = StatCard("Tracked", 12)
        assert card.property("role") == "stat-card"

    @pytest.mark.parametrize("role", ["sailing", "arrived", "delayed"])
    def test_valid_color_roles_accepted(self, qapp, role: str) -> None:
        card = StatCard("Test", 1, color_role=role)
        assert card.number_label_property("statRole") == role

    def test_invalid_color_role_raises(self, qapp) -> None:
        with pytest.raises(ValueError):
            StatCard("Test", 1, color_role="bogus")


from container_tracker.ui.widgets import UpdateBanner


class TestUpdateBanner:
    def test_hidden_by_default(self, qapp) -> None:
        banner = UpdateBanner()
        assert banner.isVisibleTo(None) is False  # equivalent to isHidden check

    def test_show_update_sets_version_text_and_reveals(self, qapp) -> None:
        banner = UpdateBanner()
        banner.show_update("1.2.0", "https://github.com/m-mcohen/container-tracker/releases/v1.2.0")
        assert "1.2.0" in banner.message_text()
        # Visibility governed by parent; use the internal shown flag instead.
        assert banner.is_shown() is True

    def test_dismiss_hides_and_emits_signal(self, qapp) -> None:
        banner = UpdateBanner()
        banner.show_update("1.2.0", "https://...")
        received: list[str] = []
        banner.dismissed.connect(lambda: received.append("dismissed"))
        banner._dismiss_button.click()
        assert banner.is_shown() is False
        assert received == ["dismissed"]

    def test_click_body_emits_open_url_requested_with_url(self, qapp) -> None:
        banner = UpdateBanner()
        url = "https://github.com/m-mcohen/container-tracker/releases/v1.2.0"
        banner.show_update("1.2.0", url)
        received: list[str] = []
        banner.open_url_requested.connect(received.append)
        banner._body_button.click()
        assert received == [url]

    def test_show_update_overwrites_previous_url(self, qapp) -> None:
        banner = UpdateBanner()
        banner.show_update("1.2.0", "https://old")
        banner.show_update("1.3.0", "https://new")
        received: list[str] = []
        banner.open_url_requested.connect(received.append)
        banner._body_button.click()
        assert received == ["https://new"]


from container_tracker.ui.widgets import LinkedSpreadsheetCard


class TestLinkedSpreadsheetCard:
    def test_shows_placeholder_when_empty(self, qapp) -> None:
        card = LinkedSpreadsheetCard("")
        assert "No file linked" in card.path_text()

    def test_shows_path_when_set(self, qapp) -> None:
        card = LinkedSpreadsheetCard(r"C:\Users\me\containers.xlsx")
        assert r"containers.xlsx" in card.path_text()

    def test_set_path_updates_display(self, qapp) -> None:
        card = LinkedSpreadsheetCard("")
        card.set_path(r"C:\new.xlsx")
        assert r"new.xlsx" in card.path_text()
        card.set_path("")
        assert "No file linked" in card.path_text()

    def test_browse_button_emits_signal(self, qapp) -> None:
        card = LinkedSpreadsheetCard("")
        received: list[object] = []
        card.browse_requested.connect(lambda: received.append("browse"))
        card._browse_button.click()
        assert received == ["browse"]

    def test_create_button_emits_signal(self, qapp) -> None:
        card = LinkedSpreadsheetCard("")
        received: list[object] = []
        card.create_requested.connect(lambda: received.append("create"))
        card._create_button.click()
        assert received == ["create"]

    def test_open_button_emits_signal_with_current_path(self, qapp) -> None:
        path = r"C:\Users\me\containers.xlsx"
        card = LinkedSpreadsheetCard(path)
        received: list[str] = []
        card.open_requested.connect(received.append)
        card._open_button.click()
        assert received == [path]

    def test_open_button_disabled_when_path_empty(self, qapp) -> None:
        card = LinkedSpreadsheetCard("")
        assert card._open_button.isEnabled() is False

    def test_open_button_reenabled_when_path_set(self, qapp) -> None:
        card = LinkedSpreadsheetCard("")
        card.set_path(r"C:\new.xlsx")
        assert card._open_button.isEnabled() is True


from container_tracker.ui.widgets import HeaderRow


class TestHeaderRow:
    def test_renders_title_and_subtitle(self, qapp) -> None:
        header = HeaderRow(title="Container Tracker", subtitle="Ken Gabbay Coffee")
        assert header.title_text() == "Container Tracker"
        assert header.subtitle_text() == "Ken Gabbay Coffee"

    def test_empty_subtitle_is_accepted(self, qapp) -> None:
        header = HeaderRow(title="Container Tracker", subtitle="")
        assert header.subtitle_text() == ""

    def test_settings_button_emits_signal(self, qapp) -> None:
        header = HeaderRow(title="Container Tracker", subtitle="Acme")
        received: list[object] = []
        header.settings_clicked.connect(lambda: received.append("settings"))
        header._settings_button.click()
        assert received == ["settings"]

    def test_dark_mode_checkbox_emits_signal(self, qapp) -> None:
        header = HeaderRow(title="Container Tracker", subtitle="Acme")
        received: list[bool] = []
        header.dark_mode_toggled.connect(received.append)
        header._dark_mode_toggle.setChecked(True)
        assert received == [True]
        header._dark_mode_toggle.setChecked(False)
        assert received == [True, False]

    def test_dark_mode_initial_state_respected(self, qapp) -> None:
        header_off = HeaderRow(title="Container Tracker", subtitle="", is_dark=False)
        header_on = HeaderRow(title="Container Tracker", subtitle="", is_dark=True)
        assert header_off._dark_mode_toggle.isChecked() is False
        assert header_on._dark_mode_toggle.isChecked() is True
