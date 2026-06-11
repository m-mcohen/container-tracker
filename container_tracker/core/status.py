"""Validation patterns and shipment-status field extraction from ShipsGo v2."""

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

API_KEY_PATTERN = re.compile(r"^[0-9a-fA-F\-]{30,40}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_setup_fields(company: str, api_key: str, email: str) -> str | None:
    if not company.strip():
        return "Company name is required."
    if not api_key.strip():
        return "ShipsGo API key is required."
    if not API_KEY_PATTERN.match(api_key.strip()):
        return "That API key doesn't look right — check for extra spaces or missing characters."
    if not email.strip() or not EMAIL_PATTERN.match(email.strip()):
        return "Enter a valid email address."
    return None


def extract_fields(shipment: dict) -> dict:
    """Flatten a ShipsGo v2 shipment payload into the keys the UI expects.

    The v2 API wraps single-shipment GETs as ``{"message": ..., "shipment": {...}}``.
    Vessel name is sourced from the most recent movement that actually has one
    (walk movements in reverse).
    """
    if "shipment" in shipment and isinstance(shipment["shipment"], dict):
        shipment = shipment["shipment"]

    f = {"status": "", "vessel": "", "pol": "", "pod": "", "eta": "", "etd": "",
         "carrier": "", "scac": "", "transit_pct": "", "original_eta": "", "delay_days": ""}
    f["status"] = shipment.get("status", "")

    cr = shipment.get("carrier") or {}
    if isinstance(cr, dict):
        f["carrier"] = cr.get("name", cr.get("scac", ""))
        f["scac"] = cr.get("scac", "") or ""

    route = shipment.get("route") or {}

    pol = route.get("port_of_loading") or route.get("origin") or {}
    pl = pol.get("location") or {}
    f["pol"] = pl.get("name", "")
    f["etd"] = pol.get("date_of_loading", pol.get("date_of_dep", ""))

    pod = route.get("port_of_discharge") or route.get("destination") or {}
    dl = pod.get("location") or {}
    f["pod"] = dl.get("name", "")
    f["eta"] = pod.get("date_of_discharge", pod.get("date_of_eta", ""))
    f["original_eta"] = pod.get("date_of_discharge_initial", pod.get("date_of_eta_initial", ""))
    f["transit_pct"] = route.get("transit_percentage", "")

    try:
        es = str(f["eta"]).split("T")[0] if f["eta"] else ""
        os_ = str(f["original_eta"]).split("T")[0] if f["original_eta"] else ""
        if es and os_:
            ed = datetime.strptime(es, "%Y-%m-%d")
            od = datetime.strptime(os_, "%Y-%m-%d")
            diff = (ed - od).days
            if diff > 0:
                f["delay_days"] = f"+{diff} days"
            elif diff < 0:
                f["delay_days"] = f"{diff} days (early)"
            else:
                f["delay_days"] = "On time"
    except Exception as e:
        # A malformed ETA from the API leaves delay_days empty rather than
        # failing the whole extraction — but don't lose the evidence.
        logger.warning("delay_days parse failed (eta=%r original_eta=%r): %s",
                       f.get("eta"), f.get("original_eta"), e)

    containers = shipment.get("containers") or []
    if containers and isinstance(containers[0], dict):
        for m in reversed(containers[0].get("movements") or []):
            if isinstance(m, dict) and m.get("vessel"):
                v = m["vessel"]
                if isinstance(v, dict) and v.get("name"):
                    f["vessel"] = v["name"]
                    break

    for k in ("eta", "etd", "original_eta"):
        if f[k] and "T" in str(f[k]):
            f[k] = str(f[k]).split("T")[0]
    return f
