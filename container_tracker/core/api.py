"""ShipsGo API v2 client and SCAC resolution."""

import requests

from container_tracker.core.constants import API_BASE, CARRIER_SCAC_MAP


def resolve_scac(line: str) -> str:
    u = line.strip().upper()
    return CARRIER_SCAC_MAP.get(u, u if len(u) == 4 else u)


class ShipsGoClient:
    """Thin wrapper around the ShipsGo v2 ocean shipments API."""

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Shipsgo-User-Token": token,
        })

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
