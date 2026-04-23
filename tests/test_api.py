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


import pytest
import responses

from container_tracker.core.api import API_BASE, ShipsGoAuthError, ShipsGoClient


class TestShipsGoClient:
    @responses.activate
    def test_create_shipment_success(self) -> None:
        responses.add(
            responses.POST,
            f"{API_BASE}/ocean/shipments",
            json={"id": "ship_new_001"},
            status=200,
        )
        client = ShipsGoClient("tok-valid")
        result = client.create_shipment(container_number="mSKu1234567", carrier_scac="maeu")
        assert result == {"id": "ship_new_001"}

        # Verify the request body upper-cased the container number and SCAC
        request = responses.calls[0].request
        import json as _json
        body = _json.loads(request.body)
        assert body["container_number"] == "MSKU1234567"
        assert body["carrier_scac"] == "MAEU"
        assert request.headers["X-Shipsgo-User-Token"] == "tok-valid"

    @responses.activate
    def test_create_shipment_already_tracked_409(self) -> None:
        responses.add(
            responses.POST,
            f"{API_BASE}/ocean/shipments",
            json={"error": "already exists"},
            status=409,
        )
        client = ShipsGoClient("tok")
        result = client.create_shipment(container_number="MSKU1234567")
        assert result == {"already_exists": True}

    @responses.activate
    def test_create_shipment_insufficient_credits_402(self) -> None:
        responses.add(
            responses.POST,
            f"{API_BASE}/ocean/shipments",
            json={"error": "no credits"},
            status=402,
        )
        client = ShipsGoClient("tok")
        result = client.create_shipment(container_number="MSKU1234567")
        assert result == {"error": "NOT_ENOUGH_CREDITS"}

    @responses.activate
    def test_create_shipment_401_raises_auth_error(self) -> None:
        responses.add(
            responses.POST,
            f"{API_BASE}/ocean/shipments",
            json={"error": "invalid token"},
            status=401,
        )
        client = ShipsGoClient("tok-bad")
        with pytest.raises(ShipsGoAuthError):
            client.create_shipment(container_number="MSKU1234567")

    @responses.activate
    def test_list_shipments_401_raises_auth_error(self) -> None:
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments",
            json={"error": "invalid token"},
            status=401,
        )
        client = ShipsGoClient("tok-bad")
        with pytest.raises(ShipsGoAuthError):
            client.list_shipments()

    @responses.activate
    def test_get_shipment_401_raises_auth_error(self) -> None:
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments/ship_x",
            json={"error": "invalid token"},
            status=401,
        )
        client = ShipsGoClient("tok-bad")
        with pytest.raises(ShipsGoAuthError):
            client.get_shipment("ship_x")

    @responses.activate
    def test_list_shipments_unwraps_shipments_key(self) -> None:
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments",
            json={"shipments": [{"id": "a"}, {"id": "b"}]},
            status=200,
        )
        client = ShipsGoClient("tok")
        assert client.list_shipments() == [{"id": "a"}, {"id": "b"}]

    @responses.activate
    def test_list_shipments_unwraps_data_key(self) -> None:
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments",
            json={"data": [{"id": "a"}]},
            status=200,
        )
        client = ShipsGoClient("tok")
        assert client.list_shipments() == [{"id": "a"}]

    @responses.activate
    def test_list_shipments_passes_list_through(self) -> None:
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments",
            json=[{"id": "a"}],
            status=200,
        )
        client = ShipsGoClient("tok")
        assert client.list_shipments() == [{"id": "a"}]

    @responses.activate
    def test_get_shipment_returns_json(self) -> None:
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments/ship_x",
            json={"shipment": {"id": "ship_x", "status": "SAILING"}},
            status=200,
        )
        client = ShipsGoClient("tok")
        result = client.get_shipment("ship_x")
        assert result["shipment"]["status"] == "SAILING"

    @responses.activate
    def test_500_raises_http_error(self) -> None:
        import requests
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments",
            status=500,
        )
        client = ShipsGoClient("tok")
        with pytest.raises(requests.HTTPError):
            client.list_shipments()
