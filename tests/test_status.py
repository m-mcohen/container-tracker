"""Unit tests for container_tracker.core.status."""

import json
from pathlib import Path

import pytest

from container_tracker.core.status import (
    extract_fields,
    validate_setup_fields,
)


FIXTURES = Path(__file__).parent / "fixtures"


class TestValidateSetupFields:
    def test_all_valid_returns_none(self):
        # 36-char UUID-style key
        key = "12345678-1234-1234-1234-123456789012"
        assert validate_setup_fields("Acme Co", key, "user@example.com") is None

    def test_missing_company(self):
        assert "Company" in validate_setup_fields(
            "", "12345678-1234-1234-1234-123456789012", "u@e.com")

    def test_missing_api_key(self):
        assert "API key is required" in validate_setup_fields("Acme", "", "u@e.com")

    def test_malformed_api_key(self):
        # Wrong length / non-hex chars
        assert "doesn't look right" in validate_setup_fields(
            "Acme", "not-a-uuid", "u@e.com")

    def test_invalid_email(self):
        key = "12345678-1234-1234-1234-123456789012"
        assert "valid email" in validate_setup_fields("Acme", key, "not-an-email")

    def test_empty_email(self):
        key = "12345678-1234-1234-1234-123456789012"
        assert "valid email" in validate_setup_fields("Acme", key, "   ")


class TestExtractFields:
    @pytest.fixture
    def shipment(self):
        return json.loads((FIXTURES / "shipsgo_response.json").read_text())

    def test_extracts_status(self, shipment):
        assert extract_fields(shipment)["status"] == "SAILING"

    def test_extracts_carrier_name(self, shipment):
        assert extract_fields(shipment)["carrier"] == "EVERGREEN MARINE CORP"

    def test_extracts_scac(self, shipment):
        # extract_fields preserves carrier.scac so the bridge does not have
        # to reverse-map a long carrier name back to its 4-letter code.
        assert extract_fields(shipment)["scac"] == "EGLV"

    def test_scac_empty_when_carrier_missing_scac(self):
        # When carrier.scac is absent, scac is "" not None — uniform shape.
        out = extract_fields({"carrier": {"name": "SOME LINE"}})
        assert out["scac"] == ""

    def test_extracts_pol_pod(self, shipment):
        f = extract_fields(shipment)
        assert f["pol"] == "Kaohsiung, TW"
        assert f["pod"] == "Los Angeles, USA"

    def test_eta_is_date_only(self, shipment):
        # API returns ISO datetime; extractor strips the time portion.
        assert extract_fields(shipment)["eta"] == "2026-04-22"
        assert extract_fields(shipment)["original_eta"] == "2026-04-15"

    def test_delay_days_computed_from_eta_diff(self, shipment):
        # 2026-04-22 vs original 2026-04-15 → +7 days delay.
        assert extract_fields(shipment)["delay_days"] == "+7 days"

    def test_vessel_taken_from_latest_movement_with_vessel(self, shipment):
        # First movement has no vessel; second has MV TEST VOYAGER.
        assert extract_fields(shipment)["vessel"] == "MV TEST VOYAGER"

    def test_transit_pct(self, shipment):
        assert extract_fields(shipment)["transit_pct"] == 58

    def test_unwraps_message_wrapper(self, shipment):
        # The fixture is wrapped as {"message": ..., "shipment": {...}}.
        # Passing the unwrapped inner dict should produce the same result.
        unwrapped = shipment["shipment"]
        assert extract_fields({"shipment": unwrapped}) == extract_fields(unwrapped)
