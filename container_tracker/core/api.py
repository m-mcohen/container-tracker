"""ShipsGo API v2 client and response parsing.

Pure logic. Constructing a client does not make a network call.
"""
from __future__ import annotations


CARRIER_SCAC_MAP: dict[str, str] = {
    "MAERSK":       "MAEU",
    "MAERSK LINE":  "MAEU",
    "MSC":          "MSCU",
    "CMA CGM":      "CMDU",
    "HAPAG LLOYD":  "HLCU",
    "HAPAG-LLOYD":  "HLCU",
    "COSCO":        "COSU",
    "EVERGREEN":    "EGLV",
    "ONE":          "ONEY",
    "YANG MING":    "YMLU",
    "ZIM":          "ZIMU",
    "HMM":          "HDMU",
    "OOCL":         "OOLU",
    "PIL":          "PILU",
}

CARRIER_NAMES: list[str] = [
    "MAERSK LINE", "MSC", "CMA CGM", "HAPAG LLOYD", "COSCO",
    "EVERGREEN", "ONE", "YANG MING", "ZIM", "HMM", "OOCL", "PIL", "OTHER",
]


def resolve_scac(line: str) -> str:
    """Resolve a shipping-line name to a SCAC code.

    Known names map via CARRIER_SCAC_MAP. A four-letter input is assumed to
    already be a SCAC. Otherwise the uppercased input is returned unchanged.
    """
    upper = line.strip().upper()
    return CARRIER_SCAC_MAP.get(upper, upper)


from typing import Any

from container_tracker.core.status import compute_delay_days


def extract_fields(shipment: dict[str, Any]) -> dict[str, Any]:
    """Pull display-ready fields from a ShipsGo v2 shipment response.

    Accepts either `{"shipment": {...}}` (the GET-by-id shape) or the bare
    shipment dict. All missing fields degrade to empty strings; `delay_days_int`
    is None when original/current ETA can't be compared.
    """
    if "shipment" in shipment and isinstance(shipment["shipment"], dict):
        shipment = shipment["shipment"]

    fields: dict[str, Any] = {
        "status": shipment.get("status", ""),
        "vessel": "",
        "pol": "",
        "pod": "",
        "eta": "",
        "etd": "",
        "carrier": "",
        "transit_pct": "",
        "original_eta": "",
        "delay_days": "",
        "delay_days_int": None,
    }

    carrier = shipment.get("carrier") or {}
    if isinstance(carrier, dict):
        fields["carrier"] = carrier.get("name", carrier.get("scac", ""))

    route = shipment.get("route") or {}

    pol = route.get("port_of_loading") or route.get("origin") or {}
    pol_loc = pol.get("location") or {}
    fields["pol"] = pol_loc.get("name", "")
    fields["etd"] = pol.get("date_of_loading", pol.get("date_of_dep", ""))

    pod = route.get("port_of_discharge") or route.get("destination") or {}
    pod_loc = pod.get("location") or {}
    fields["pod"] = pod_loc.get("name", "")
    fields["eta"] = pod.get("date_of_discharge", pod.get("date_of_eta", ""))
    fields["original_eta"] = pod.get(
        "date_of_discharge_initial",
        pod.get("date_of_eta_initial", ""),
    )

    fields["transit_pct"] = route.get("transit_percentage", "")

    # Trim any ISO date strings down to YYYY-MM-DD.
    for key in ("eta", "etd", "original_eta"):
        value = fields[key]
        if value and "T" in str(value):
            fields[key] = str(value).split("T")[0]

    # Delay — numeric and formatted. Either may be absent.
    try:
        diff = compute_delay_days(fields["original_eta"], fields["eta"])
        fields["delay_days_int"] = diff
        if diff > 0:
            fields["delay_days"] = f"+{diff} days"
        elif diff < 0:
            fields["delay_days"] = f"{diff} days (early)"
        else:
            fields["delay_days"] = "On time"
    except ValueError:
        fields["delay_days_int"] = None
        fields["delay_days"] = ""

    # Vessel — most recent movement with a vessel dict wins.
    containers = shipment.get("containers") or []
    if containers and isinstance(containers[0], dict):
        movements = containers[0].get("movements") or []
        for movement in reversed(movements):
            if isinstance(movement, dict) and movement.get("vessel"):
                vessel = movement["vessel"]
                if isinstance(vessel, dict) and vessel.get("name"):
                    fields["vessel"] = vessel["name"]
                    break

    return fields


import requests


API_BASE = "https://api.shipsgo.com/v2"


class ShipsGoAuthError(Exception):
    """Raised when ShipsGo rejects the API token (HTTP 401).

    The UI layer catches this specifically to surface a modal prompting the
    user to open Settings and update their key.
    """


class ShipsGoClient:
    """Synchronous client for the ShipsGo v2 ocean-shipments endpoints.

    Constructor is cheap — builds a requests.Session but makes no network
    calls. Thread-safety: reuse a single client across background QRunnables
    is fine, but each call is independent (no shared mutable state beyond the
    session's connection pool).
    """

    def __init__(self, token: str) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Shipsgo-User-Token": token,
        })

    def create_shipment(
        self,
        container_number: str = "",
        carrier_scac: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, str] = {}
        if container_number:
            payload["container_number"] = container_number.strip().upper()
        if carrier_scac:
            payload["carrier_scac"] = carrier_scac.strip().upper()
        response = self.session.post(
            f"{API_BASE}/ocean/shipments",
            json=payload,
            timeout=30,
        )
        if response.status_code == 401:
            raise ShipsGoAuthError("ShipsGo rejected the API token")
        if response.status_code == 409:
            return {"already_exists": True}
        if response.status_code == 402:
            return {"error": "NOT_ENOUGH_CREDITS"}
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def list_shipments(self, take: int = 100) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{API_BASE}/ocean/shipments",
            params={"take": take},
            timeout=30,
        )
        if response.status_code == 401:
            raise ShipsGoAuthError("ShipsGo rejected the API token")
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            result = data.get("shipments", data.get("data", []))
            return result  # type: ignore[return-value]
        return data  # type: ignore[no-any-return]

    def get_shipment(self, shipment_id: str) -> dict[str, Any]:
        response = self.session.get(
            f"{API_BASE}/ocean/shipments/{shipment_id}",
            timeout=30,
        )
        if response.status_code == 401:
            raise ShipsGoAuthError("ShipsGo rejected the API token")
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]
