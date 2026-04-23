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
