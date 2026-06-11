"""Unit tests for container_tracker.core.api."""

import pytest

from container_tracker.core.api import resolve_scac


class TestResolveScac:
    @pytest.mark.parametrize("name,expected", [
        ("MAERSK", "MAEU"),
        ("MAERSK LINE", "MAEU"),
        ("maersk line", "MAEU"),  # case-insensitive
        ("  MSC  ", "MSCU"),       # trims whitespace
        ("HAPAG-LLOYD", "HLCU"),
        ("EVERGREEN", "EGLV"),
    ])
    def test_known_carriers_resolve_to_scac(self, name, expected):
        assert resolve_scac(name) == expected

    def test_4_letter_unknown_pass_through(self):
        # Already a SCAC-shaped string — pass through uppercased.
        assert resolve_scac("XYZA") == "XYZA"
        assert resolve_scac("xyza") == "XYZA"

    def test_unknown_carrier_maps_to_others(self):
        # Free-text carrier names must not leak to the API as a fake SCAC.
        assert resolve_scac("Some Random Carrier") == "OTHERS"
        assert resolve_scac("My Cousin's Boat") == "OTHERS"

    def test_4_letter_non_alpha_maps_to_others(self):
        # 4 chars but not letters — not SCAC-shaped.
        assert resolve_scac("12AB") == "OTHERS"
