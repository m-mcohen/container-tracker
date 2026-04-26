"""Bridge layer between the pywebview window's JS and the Python core.

Step 4 wires the bridge plumbing only — every data-returning method ships
hardcoded dummy data of the correct shape. Step 5 will replace the bodies
with calls into core/api.py + core/excel.py + the local tracking_data.json
without changing the public contract.

Public contract (consumed by container_tracker/web/app.js):

  list_containers() -> list[dict]
      Each entry uses the JS-side ROWS shape:
        { cn, carrier, scac, status, eta, orig, delay, delayVal,
          pol, pod, vessel, pct }
      The bridge owns the translation from core.status.extract_fields()
      output (Python-side) to this shape (JS-side). Mapping for Step 5:
        cn        ← record["container_number"]
        carrier   ← f["carrier"]
        scac      ← carrier.scac (or resolve_scac on the carrier name)
        status    ← f["status"].upper()
        eta       ← f["eta"]
        orig      ← f["original_eta"]
        delay     ← f["delay_days"] display string
        delayVal  ← parsed integer day-count from f["delay_days"]
        pol       ← f["pol"]
        pod       ← f["pod"]
        vessel    ← f["vessel"]
        pct       ← f["transit_pct"] (int 0-100, or None when not yet sailed)

  get_container(container_no) -> dict | None
      Returns drawer-detail shape for one container; None if unknown.
      Step 5 maps from a shipsgo client.get_shipment(sid) response.

  get_settings() -> dict
      { company_name, api_token_present, theme }
      Step 4 already wires this to core.config.load_config() and
      core.credentials.get_api_token() — no DUMMY for this one. The
      api_token_present field is a bool (never expose the token itself).

  ping() -> str
      Returns "pong". Smoke-test method for verifying the bridge is
      reachable from JS without exercising any other surface.

Threading: pywebview invokes js_api methods on a worker thread. Methods
must be thread-safe relative to anything they touch. Step 4's methods are
pure / read-only so this is moot; Step 5/6 will need to be careful.

Method names are exposed to JS verbatim — pywebview surfaces every public
attribute of the bridge instance under window.pywebview.api.<name>. Names
with leading underscores stay Python-private.
"""

from __future__ import annotations

from container_tracker.core import config as ct_config
from container_tracker.core import credentials as ct_credentials


# Hardcoded dummy data for Step 4. Mirrors a representative subset of the
# ROWS array currently in app.js (one delayed-sailing, one on-time-sailing,
# one arrived, one booked-pending). Step 5 replaces with live data.
_DUMMY_CONTAINERS: list[dict] = [
    {
        "cn": "EGLV5555666", "carrier": "EVERGREEN", "scac": "EGLV",
        "status": "SAILING", "eta": "2026-04-22", "orig": "2026-04-15",
        "delay": "+7 days", "delayVal": 7,
        "pol": "Kaohsiung, TW", "pod": "Los Angeles, USA",
        "vessel": "MV EVER GIVEN", "pct": 58,
    },
    {
        "cn": "MSKU2222222", "carrier": "MAERSK LINE", "scac": "MAEU",
        "status": "SAILING", "eta": "2026-04-28", "orig": "2026-04-28",
        "delay": "On time", "delayVal": 0,
        "pol": "Qingdao, CN", "pod": "Oakland, USA",
        "vessel": "MV CARIBOU", "pct": 65,
    },
    {
        "cn": "CMAU7654321", "carrier": "CMA CGM", "scac": "CMDU",
        "status": "ARRIVED", "eta": "2026-03-20", "orig": "2026-03-20",
        "delay": "On time", "delayVal": 0,
        "pol": "Ningbo, CN", "pod": "Long Beach, USA",
        "vessel": "MV PACIFIC STAR", "pct": 100,
    },
    {
        "cn": "HLCU4444555", "carrier": "HAPAG LLOYD", "scac": "HLCU",
        "status": "BOOKED", "eta": "", "orig": "",
        "delay": "", "delayVal": None,
        "pol": "", "pod": "", "vessel": "", "pct": None,
    },
]


class Bridge:
    """Exposed to JS via webview.create_window(..., js_api=Bridge())."""

    # --- Smoke test --------------------------------------------------------

    def ping(self) -> str:
        return "pong"

    # --- Containers --------------------------------------------------------

    def list_containers(self) -> list[dict]:
        # Step 5 will replace with live data sourced from
        # tracking_data.json + extract_fields(). Returning a list copy
        # so JS-side mutations can't poison the in-process dummy.
        return [dict(c) for c in _DUMMY_CONTAINERS]

    def get_container(self, container_no: str) -> dict | None:
        # Step 5 will source from client.get_shipment(record["shipment_id"])
        # and translate the full payload (movements, vessel detail, etc.)
        # into the drawer-detail shape. For Step 4, return the matching
        # row from _DUMMY_CONTAINERS or None.
        cn = (container_no or "").strip().upper()
        for row in _DUMMY_CONTAINERS:
            if row["cn"] == cn:
                return dict(row)
        return None

    # --- Settings ----------------------------------------------------------

    def get_settings(self) -> dict:
        # Reads from core directly — the contract is already final for
        # this method, so Step 5 won't need to touch it.
        cfg = ct_config.load_config()
        return {
            "company_name": cfg.get("company_name", ""),
            "api_token_present": bool(ct_credentials.get_api_token()),
            "theme": "dark" if cfg.get("dark_mode") else "light",
        }
