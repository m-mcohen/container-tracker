"""ShipsGo API v2 client and SCAC resolution."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from container_tracker.core.constants import API_BASE, CARRIER_SCAC_MAP


def resolve_scac(line: str) -> str:
    """Map a carrier display name to its SCAC. Already-SCAC-shaped input
    (exactly 4 letters) passes through so users can type a real code we
    don't have in the map; anything else unmapped becomes "OTHERS" rather
    than leaking free text to the API."""
    u = line.strip().upper()
    mapped = CARRIER_SCAC_MAP.get(u)
    if mapped:
        return mapped
    return u if len(u) == 4 and u.isalpha() else "OTHERS"


class ShipsGoClient:
    """Thin wrapper around the ShipsGo v2 ocean shipments API."""

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Shipsgo-User-Token": token,
        })
        # Retry transient gateway errors on idempotent GETs only — POST
        # (create_shipment) costs ShipsGo credits and must never be
        # auto-retried.
        retry = Retry(total=2, backoff_factor=0.5,
                      status_forcelist=[502, 503, 504],
                      allowed_methods=["GET"])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def create_shipment(self, container_number: str = "", carrier_scac: str = ""):
        payload = {}
        if container_number:
            payload["container_number"] = container_number.strip().upper()
        if carrier_scac:
            payload["carrier_scac"] = carrier_scac.strip().upper()
        r = self.session.post(f"{API_BASE}/ocean/shipments", json=payload, timeout=30)
        if r.status_code == 409:
            return {"already_exists": True}
        if r.status_code == 402:
            return {"error": "NOT_ENOUGH_CREDITS"}
        r.raise_for_status()
        return r.json()

    def list_shipments(self, take: int = 100):
        r = self.session.get(f"{API_BASE}/ocean/shipments", params={"take": take}, timeout=30)
        r.raise_for_status()
        d = r.json()
        return d.get("shipments", d.get("data", [])) if isinstance(d, dict) else d

    def get_shipment(self, sid):
        r = self.session.get(f"{API_BASE}/ocean/shipments/{sid}", timeout=30)
        r.raise_for_status()
        return r.json()

    def delete_shipment(self, sid):
        r = self.session.delete(f"{API_BASE}/ocean/shipments/{sid}", timeout=30)
        r.raise_for_status()
        return r.json()
