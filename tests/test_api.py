import json
from pathlib import Path

from container_tracker.core.api import (
    CARRIER_NAMES,
    CARRIER_SCAC_MAP,
    extract_fields,
    resolve_scac,
)


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestResolveScac:
    def test_known_carrier_by_long_name(self) -> None:
        assert resolve_scac("MAERSK LINE") == "MAEU"
        assert resolve_scac("Hapag-Lloyd") == "HLCU"

    def test_case_and_whitespace_normalized(self) -> None:
        assert resolve_scac("  maersk  ") == "MAEU"

    def test_four_letter_code_passthrough(self) -> None:
        assert resolve_scac("MSCU") == "MSCU"

    def test_unknown_returns_upper_input(self) -> None:
        assert resolve_scac("NONSENSE") == "NONSENSE"


class TestCarrierMetadata:
    def test_scac_map_covers_named_carriers(self) -> None:
        # Every long name in CARRIER_NAMES (except "OTHER") resolves to a SCAC
        for name in CARRIER_NAMES:
            if name == "OTHER":
                continue
            assert resolve_scac(name) != "", f"{name} has no SCAC mapping"

    def test_all_scacs_are_four_letters(self) -> None:
        for scac in CARRIER_SCAC_MAP.values():
            assert len(scac) == 4 and scac.isalpha(), f"bad SCAC: {scac}"


class TestExtractFields:
    def test_sailing_shipment_fields(self) -> None:
        result = extract_fields(_load("shipsgo_sailing.json"))
        assert result["status"] == "SAILING"
        assert result["carrier"] == "MAERSK LINE"
        assert result["pol"] == "Shanghai, China"
        assert result["pod"] == "Los Angeles, USA"
        assert result["etd"] == "2026-04-01"
        assert result["eta"] == "2026-05-05"
        assert result["original_eta"] == "2026-05-01"
        assert result["delay_days_int"] == 4
        assert result["delay_days"] == "+4 days"
        assert result["vessel"] == "MV SEA PIONEER"
        assert result["transit_pct"] == 42

    def test_arrived_shipment_fields(self) -> None:
        result = extract_fields(_load("shipsgo_arrived.json"))
        assert result["status"] == "ARRIVED"
        assert result["pol"] == "Ningbo, China"
        assert result["pod"] == "Long Beach, USA"
        assert result["eta"] == "2026-03-20"
        assert result["original_eta"] == "2026-03-20"
        assert result["delay_days_int"] == 0
        assert result["delay_days"] == "On time"
        assert result["vessel"] == "MV PACIFIC STAR"
        assert result["transit_pct"] == 100

    def test_unwrapped_payload_also_works(self) -> None:
        # If caller passes shipment dict directly (not wrapped in {"shipment": ...})
        raw = _load("shipsgo_sailing.json")["shipment"]
        result = extract_fields(raw)
        assert result["status"] == "SAILING"
        assert result["pol"] == "Shanghai, China"

    def test_missing_route_degrades_gracefully(self) -> None:
        result = extract_fields({"shipment": {"status": "BOOKED"}})
        assert result["status"] == "BOOKED"
        assert result["pol"] == ""
        assert result["pod"] == ""
        assert result["eta"] == ""
        assert result["original_eta"] == ""
        assert result["delay_days"] == ""
        assert result["delay_days_int"] is None

    def test_early_arrival_formats_negative(self) -> None:
        payload = {"shipment": {
            "status": "SAILING",
            "route": {
                "port_of_discharge": {
                    "date_of_discharge": "2026-05-01",
                    "date_of_discharge_initial": "2026-05-04",
                }
            }
        }}
        result = extract_fields(payload)
        assert result["delay_days_int"] == -3
        assert result["delay_days"] == "-3 days (early)"

    def test_vessel_from_last_movement_with_vessel(self) -> None:
        # Most recent movement with a vessel wins; earlier null-vessel movements ignored.
        payload = {"shipment": {
            "containers": [{"movements": [
                {"vessel": {"name": "MV A"}},
                {"vessel": None},
                {"vessel": {"name": "MV B"}},
            ]}]
        }}
        assert extract_fields(payload)["vessel"] == "MV B"
