"""Bridge layer between the pywebview window's JS and the Python core.

Step 5 wires list_containers / get_container to the on-disk tracking DB.
Refresh from the live ShipsGo API, mutations (add/remove), and
save-settings are Step 6.

Public contract (consumed by container_tracker/web/app.js):

  list_containers() -> list[dict]
      Each entry in the JS-side ROWS shape. Mapped from the flat record
      that core.status.extract_fields() output is merged into:

        JS key      Source
        ────────    ──────
        cn          rec["container_number"] (or the dict key)
        carrier     rec["carrier"] (falls back to rec["shipping_line"] for
                    pre-refresh rows the legacy GUI added)
        scac        resolve_scac(carrier_name)
        status      rec["status"].upper(), or ""
        eta         rec["eta"]
        orig        rec["original_eta"]
        delay       rec["delay_days"] — already display-formatted by
                    extract_fields ("+7 days", "On time", "−2 days
                    (early)", "")
        delayVal    int parsed from delay_days; positive=late,
                    negative=early, 0=on-time, None=unknown
        pol         rec["pol"]
        pod         rec["pod"]
        vessel      rec["vessel"]
        pct         rec["transit_pct"] as int 0–100, or None when
                    extract_fields left it as ""

      Note: tracking_data.json stores extract_fields output flat (the
      legacy GUI does ``rec.update(extract_fields(sh))``), so the bridge
      reads the keys directly. There is NO cached raw ShipsGo response
      to re-extract from on the GUI's data path.

  get_container(cn) -> dict | None
      Single record in the same shape. None if cn is not in the DB.

  get_settings() -> dict
      Final from Step 4. Reads core.config + core.credentials. The
      api_token_present field is bool only; the token value never leaves
      the bridge.

  ping() -> str
      Smoke-test method. Returns "pong".

Errors (Step 5 contract):
  * Missing tracking_data.json → empty list, not an exception. Fresh
    installs render an empty dashboard.
  * One row's record is malformed → log to core.config.LOG_FILE, skip
    that row, continue. One bad row must not blank the whole dashboard.
  * tracking_data.json exists but is corrupt JSON → let it raise. JS
    sees a rejected Promise and logs to console. Step 6 adds proper UI.

Threading: pywebview invokes js_api methods on a worker thread. Step 5
methods are read-only (no in-process mutable state) so this is moot;
Step 6's mutations will need to revisit.
"""

from __future__ import annotations

import logging
import re

from container_tracker.core import config as ct_config
from container_tracker.core import credentials as ct_credentials
from container_tracker.core.api import resolve_scac

logger = logging.getLogger(__name__)


# Match the leading signed integer in delay strings like "+7 days",
# "-2 days (early)", "On time", "". On-time → 0; everything else with no
# leading int → None.
_DELAY_INT = re.compile(r"^([+\-−]?\d+)")


def _parse_delay_val(delay_str: str | None) -> int | None:
    if not delay_str:
        return None
    if delay_str.strip().lower() == "on time":
        return 0
    m = _DELAY_INT.match(delay_str.strip())
    if not m:
        return None
    raw = m.group(1).replace("−", "-")  # extract_fields uses ASCII "-",
                                        # but normalize the unicode minus
                                        # just in case it ever shows up.
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_pct(value) -> int | None:
    """transit_pct is an int 0–100 from the API, but extract_fields
    defaults missing values to "" — translate those to None so the JS
    renderer's "Not yet sailed" branch fires."""
    if value == "" or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_row(cn: str, rec: dict) -> dict:
    """Translate one flat tracking_data.json record into the JS-side
    ROWS shape. May raise if rec is missing required types — caller
    catches per-row."""
    carrier_name = rec.get("carrier") or rec.get("shipping_line") or ""
    delay_str = rec.get("delay_days", "") or ""
    return {
        "cn": str(cn).upper() or str(rec.get("container_number", "")).upper(),
        "carrier": carrier_name,
        "scac": resolve_scac(carrier_name) if carrier_name else "",
        "status": (rec.get("status") or "").upper(),
        "eta": rec.get("eta", "") or "",
        "orig": rec.get("original_eta", "") or "",
        "delay": delay_str,
        "delayVal": _parse_delay_val(delay_str),
        "pol": rec.get("pol", "") or "",
        "pod": rec.get("pod", "") or "",
        "vessel": rec.get("vessel", "") or "",
        "pct": _parse_pct(rec.get("transit_pct")),
    }


class Bridge:
    """Exposed to JS via webview.create_window(..., js_api=Bridge())."""

    # --- Smoke test --------------------------------------------------------

    def ping(self) -> str:
        return "pong"

    # --- Containers --------------------------------------------------------

    def list_containers(self) -> list[dict]:
        db = ct_config.load_tracking_db()
        rows: list[dict] = []
        for cn, rec in db.items():
            try:
                rows.append(_to_row(cn, rec))
            except Exception as e:
                # Per-row swallow: one malformed entry must not blank the
                # whole dashboard. Step 6 will surface this in the UI.
                logger.warning(
                    "skipping malformed tracking_data.json entry %r: %s",
                    cn, e,
                )
        return rows

    def get_container(self, container_no: str) -> dict | None:
        cn = (container_no or "").strip().upper()
        if not cn:
            return None
        db = ct_config.load_tracking_db()
        rec = db.get(cn)
        if rec is None:
            return None
        try:
            return _to_row(cn, rec)
        except Exception as e:
            logger.warning("get_container(%r) translation failed: %s", cn, e)
            return None

    # --- Settings ----------------------------------------------------------

    def get_settings(self) -> dict:
        cfg = ct_config.load_config()
        return {
            "company_name": cfg.get("company_name", ""),
            "api_token_present": bool(ct_credentials.get_api_token()),
            "theme": "dark" if cfg.get("dark_mode") else "light",
        }
