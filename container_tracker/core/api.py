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
