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
import time
from datetime import datetime, timezone

from container_tracker.core import config as ct_config
from container_tracker.core import credentials as ct_credentials
from container_tracker.core import status as ct_status
from container_tracker.core.api import ShipsGoClient, resolve_scac

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
        # Prefer the cached scac field from extract_fields() (Step 6 fix);
        # fall back to resolve_scac for legacy unrefreshed records that
        # don't have it yet.
        "scac": rec.get("scac") or (resolve_scac(carrier_name) if carrier_name else ""),
        "status": (rec.get("status") or "").upper(),
        "eta": rec.get("eta", "") or "",
        "orig": rec.get("original_eta", "") or "",
        "delay": delay_str,
        "delayVal": _parse_delay_val(delay_str),
        "pol": rec.get("pol", "") or "",
        "pod": rec.get("pod", "") or "",
        "vessel": rec.get("vessel", "") or "",
        "pct": _parse_pct(rec.get("transit_pct")),
        "last_refreshed": rec.get("last_refreshed", "") or "",
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

    # --- Refresh -----------------------------------------------------------

    def refresh_all(self) -> dict:
        """Refresh every container in tracking_data.json.

        Replicates the legacy GUI's two-phase refresh
        (container_tracker_gui.py:763-846): one ``list_shipments(take=100)``
        to build a sid/cn map, then per-container ``get_shipment(sid)``
        looped sequentially. ``tracking_data.json`` is written exactly
        once at the end.

        Returns ``{"updated": int, "failed": [{"cn", "error"}],
        "duration_ms": int, "error": str | None}``. **Never raises** for
        operational failures — JS branches on ``result["error"]`` /
        ``result["failed"]`` uniformly.
        """
        token = ct_credentials.get_api_token()
        if not token:
            return {"updated": 0, "failed": [], "duration_ms": 0,
                    "error": "API token not configured"}

        db = ct_config.load_tracking_db()
        if not db:
            return {"updated": 0, "failed": [], "duration_ms": 0, "error": None}

        started = time.monotonic()
        client = ShipsGoClient(token)

        # Phase 1: list_shipments map (legacy line 768)
        try:
            listing = client.list_shipments(take=100) or []
        except Exception as e:
            return {
                "updated": 0, "failed": [],
                "duration_ms": int((time.monotonic() - started) * 1000),
                "error": f"list_shipments failed: {e}",
            }

        by_cn: dict[str, dict] = {}
        for s in listing:
            if not isinstance(s, dict):
                continue
            cn_key = (s.get("container_number") or "").upper()
            if cn_key:
                by_cn[cn_key] = s

        # Phase 2: per-container get_shipment(sid) (legacy line 803-819)
        updated = 0
        failed: list[dict] = []
        for cn, rec in db.items():
            cn_up = cn.upper()
            sid = rec.get("shipment_id") or (by_cn.get(cn_up) or {}).get("id")
            if not sid:
                failed.append({"cn": cn_up,
                               "error": "no shipment id (not on ShipsGo)"})
                continue
            try:
                payload = client.get_shipment(sid)
                shipment = (payload.get("shipment", payload)
                            if isinstance(payload, dict) else payload)
                fields = ct_status.extract_fields(shipment)
                rec.update(fields)
                rec["shipment_id"] = sid
                rec["last_refreshed"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                updated += 1
            except Exception as e:
                logger.warning("refresh failed for %s: %s", cn_up, e)
                failed.append({"cn": cn_up, "error": str(e)})

        # Single write at end (legacy line 820 — minimize disk churn).
        ct_config.save_json(ct_config.TRACKING_DB_FILE, db)

        return {
            "updated": updated,
            "failed": failed,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "error": None,
        }

    def refresh_one(self, cn: str) -> dict:
        """Refresh a single container by container number.

        The public signature uses ``cn`` so JS doesn't have to know about
        ShipsGo's shipment_id. The bridge resolves cn → sid internally
        using the same list_shipments map fallback as legacy's two-phase.

        Returns ``{"cn": str, "ok": bool, "error": str | None}``. Like
        ``refresh_all``, never raises for operational failures.
        """
        cn_up = (cn or "").strip().upper()
        if not cn_up:
            return {"cn": "", "ok": False, "error": "empty container number"}

        token = ct_credentials.get_api_token()
        if not token:
            return {"cn": cn_up, "ok": False,
                    "error": "API token not configured"}

        db = ct_config.load_tracking_db()
        rec = db.get(cn_up)
        if rec is None:
            return {"cn": cn_up, "ok": False,
                    "error": "not in tracking database"}

        client = ShipsGoClient(token)
        sid = rec.get("shipment_id")
        if not sid:
            try:
                for s in client.list_shipments(take=100) or []:
                    if (isinstance(s, dict)
                            and (s.get("container_number") or "").upper() == cn_up):
                        sid = s.get("id") or s.get("shipment_id")
                        break
            except Exception as e:
                return {"cn": cn_up, "ok": False,
                        "error": f"list_shipments failed: {e}"}
        if not sid:
            return {"cn": cn_up, "ok": False,
                    "error": "no shipment id (not on ShipsGo)"}

        try:
            payload = client.get_shipment(sid)
            shipment = (payload.get("shipment", payload)
                        if isinstance(payload, dict) else payload)
            fields = ct_status.extract_fields(shipment)
            rec.update(fields)
            rec["shipment_id"] = sid
            rec["last_refreshed"] = datetime.utcnow().isoformat() + "Z"
            ct_config.save_json(ct_config.TRACKING_DB_FILE, db)
            return {"cn": cn_up, "ok": True, "error": None}
        except Exception as e:
            return {"cn": cn_up, "ok": False, "error": str(e)}

    # --- Mutations ---------------------------------------------------------

    def add_container(self, cn: str, carrier: str) -> dict:
        """Add a new container. Calls ShipsGoClient.create_shipment
        immediately (matches legacy container_tracker_gui.py:700-756).

        Returns ``{"ok": bool, "error": str | None, "was_existing": bool,
        "container": dict | None}``.

        Distinct error sentinels for JS routing:
          * ``"NOT_ENOUGH_CREDITS"`` (HTTP 402) — global, JS shows toast
          * ``"already_exists_local"``       — JS keeps modal open w/ inline error
          * ``"Container number must be 11 characters"`` — same
          * any other string                 — same

        409 already_exists is **not** an error: ShipsGo says the container
        is already on the account, we add it locally with whatever data we
        can, and return ``ok=True, was_existing=True`` so JS can render
        the row + show a benign info toast.
        """
        cn_up = (cn or "").strip().upper()
        if len(cn_up) != 11:
            return {"ok": False,
                    "error": "Container number must be 11 characters",
                    "was_existing": False, "container": None}

        db = ct_config.load_tracking_db()
        if cn_up in db:
            return {"ok": False, "error": "already_exists_local",
                    "was_existing": False, "container": None}

        token = ct_credentials.get_api_token()
        if not token:
            return {"ok": False, "error": "API token not configured",
                    "was_existing": False, "container": None}

        scac = resolve_scac(carrier or "")
        client = ShipsGoClient(token)
        try:
            resp = client.create_shipment(container_number=cn_up,
                                          carrier_scac=scac)
        except Exception as e:
            return {"ok": False, "error": str(e),
                    "was_existing": False, "container": None}

        if isinstance(resp, dict) and resp.get("error") == "NOT_ENOUGH_CREDITS":
            return {"ok": False, "error": "NOT_ENOUGH_CREDITS",
                    "was_existing": False, "container": None}

        already = bool(isinstance(resp, dict) and resp.get("already_exists"))
        sid = (resp.get("id") or resp.get("shipment_id")
               if isinstance(resp, dict) else None)

        rec = {
            "shipment_id": sid,
            "container_number": cn_up,
            "carrier": carrier or "",
            "scac": scac,
            "status": "",
            "vessel": "",
            "pol": "",
            "pod": "",
            "eta": "",
            "etd": "",
            "transit_pct": "",
            "original_eta": "",
            "delay_days": "",
            "last_refreshed": "",
        }
        db[cn_up] = rec
        ct_config.save_json(ct_config.TRACKING_DB_FILE, db)

        return {
            "ok": True,
            "error": None,
            "was_existing": already,
            "container": _to_row(cn_up, rec),
        }

    def remove_container(self, cn: str) -> dict:
        """Local-only remove (matches legacy:
        container_tracker_gui.py:667-698 — no API delete call). Idempotent
        on missing cn."""
        cn_up = (cn or "").strip().upper()
        db = ct_config.load_tracking_db()
        if cn_up in db:
            del db[cn_up]
            ct_config.save_json(ct_config.TRACKING_DB_FILE, db)
        return {"ok": True, "error": None}

    # --- Settings ----------------------------------------------------------

    def get_settings(self) -> dict:
        cfg = ct_config.load_config()
        return {
            "company_name": cfg.get("company_name", ""),
            "api_token_present": bool(ct_credentials.get_api_token()),
            "theme": "dark" if cfg.get("dark_mode") else "light",
        }

    def save_settings(self, company_name: str, api_token=None) -> dict:
        """Save company name to config.json. Save api_token to keyring iff
        non-empty (None / empty / whitespace leaves the existing token
        untouched — the new shell uses a masked placeholder for "token
        already set" and treats blank as "don't touch")."""
        try:
            cfg = ct_config.load_config()
            cfg["company_name"] = (company_name or "").strip()
            ct_config.save_config(cfg)
            if api_token:
                tok = str(api_token).strip()
                if tok:
                    ct_credentials.set_api_token(tok)
            return {"ok": True, "error": None}
        except Exception as e:
            logger.exception("save_settings failed")
            return {"ok": False, "error": str(e)}
