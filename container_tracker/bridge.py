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
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from container_tracker.core import config as ct_config
from container_tracker.core import credentials as ct_credentials
from container_tracker.core import status as ct_status
from container_tracker.core.api import ShipsGoClient, resolve_scac
from container_tracker.core.constants import CARRIER_NAMES
from container_tracker.core.excel import (
    create_template_excel,
    read_containers_from_excel,
    update_excel_with_tracking,
)

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
        """Refresh every container in tracking_data.json + sync Excel.

        Replicates the legacy GUI's three-phase refresh
        (container_tracker_gui.py:763-846):
          1. Read CNs from the linked Excel workbook (Step 6.5) and merge
             discovered CNs into the in-memory db as stubs (skipping any
             cn in cfg["dismissed"]).
          2. ``list_shipments(take=100)`` to build a cn→shipment map.
          3. Per-container ``get_shipment(sid)`` looped sequentially.
          4. Write tracking_data.json once.
          5. Write the linked Excel workbook (Step 6.5).

        Excel I/O failures are surfaced as flags in the returned dict but
        do **not** abort the refresh — improvement over the legacy GUI's
        early-return on locked-file read. The JS side branches on
        ``excel_read_failed`` / ``excel_write_failed`` to render banners.

        Returns the dict shape consumed by web/app.js handleRefresh:
          ``{updated, failed, duration_ms, error,
             excel_read_failed, excel_write_failed,
             unmatched, excel_rows_updated}``
        Never raises for operational failures.
        """
        cfg = ct_config.load_config()
        excel_path = (cfg.get("excel_path") or "").strip()
        dismissed = set(s.upper() for s in (cfg.get("dismissed") or []))

        base = {
            "updated": 0,
            "failed": [],
            "duration_ms": 0,
            "error": None,
            "excel_read_failed": False,
            "excel_write_failed": False,
            "excel_missing": False,
            "unmatched": [],
            "excel_rows_updated": 0,
        }
        # Treat "linked path that no longer exists" as an explicit error
        # state, distinct from "no file linked at all" (which is silent).
        # Surfacing this lets JS render a persistent banner so the user
        # can re-link via Settings — silent skip would leave them
        # wondering why the workbook isn't updating.
        excel_missing = bool(excel_path) and not Path(excel_path).exists()

        token = ct_credentials.get_api_token()
        if not token:
            return {**base, "error": "API token not configured"}

        started = time.monotonic()
        db = ct_config.load_tracking_db()

        # Phase 0: read CNs from Excel and merge as stubs (legacy line 781-793).
        # Skip both read AND write if the linked file is missing — the
        # API fetch still runs so JSON state stays current.
        excel_read_failed = False
        if excel_path and not excel_missing:
            try:
                for raw in read_containers_from_excel(excel_path):
                    cn_up = (raw or "").strip().upper()
                    if not cn_up:
                        continue
                    if cn_up in db:
                        continue
                    if cn_up in dismissed:
                        continue
                    db[cn_up] = {"container_number": cn_up,
                                 "last_refreshed": None}
            except Exception as e:
                logger.warning("Excel read failed: %s", e)
                excel_read_failed = True

        if not db:
            # Nothing to refresh and no API call needed.
            return {**base,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "excel_read_failed": excel_read_failed,
                    "excel_missing": excel_missing}

        client = ShipsGoClient(token)

        # Phase 1: list_shipments map (legacy line 768).
        try:
            listing = client.list_shipments(take=100) or []
        except Exception as e:
            return {
                **base,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "error": f"list_shipments failed: {e}",
                "excel_read_failed": excel_read_failed,
                "excel_missing": excel_missing,
            }

        by_cn: dict[str, dict] = {}
        for s in listing:
            if not isinstance(s, dict):
                continue
            cn_key = (s.get("container_number") or "").upper()
            if cn_key:
                by_cn[cn_key] = s

        # Phase 2: per-container get_shipment(sid) (legacy line 803-819).
        # CNs without a resolvable shipment_id (typically Excel-discovered
        # stubs) land in ``unmatched`` rather than ``failed`` — that's the
        # signal the JS side uses to fire the post-refresh register banner.
        updated = 0
        failed: list[dict] = []
        unmatched: list[str] = []
        for cn, rec in db.items():
            cn_up = cn.upper()
            sid = rec.get("shipment_id") or (by_cn.get(cn_up) or {}).get("id")
            if not sid:
                if cn_up not in dismissed:
                    unmatched.append(cn_up)
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

        # Single tracking_data.json write at end (legacy line 820).
        ct_config.save_json(ct_config.TRACKING_DB_FILE, db)

        # Phase 3: write back to Excel (legacy line 821-829).
        excel_write_failed = False
        excel_rows_updated = 0
        if excel_path and not excel_missing:
            try:
                excel_rows_updated = (
                    update_excel_with_tracking(excel_path, db) or 0)
            except Exception as e:
                logger.warning("Excel write failed: %s", e)
                excel_write_failed = True

        return {
            "updated": updated,
            "failed": failed,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "error": None,
            "excel_read_failed": excel_read_failed,
            "excel_write_failed": excel_write_failed,
            "excel_missing": excel_missing,
            "unmatched": unmatched,
            "excel_rows_updated": excel_rows_updated,
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
            "excel_path": cfg.get("excel_path", "") or "",
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

    # --- Excel link management (Step 6.5) ---------------------------------

    def list_carriers(self) -> list[str]:
        """Return the dropdown carrier list. Sourced from CARRIER_NAMES so
        the JS-side register-unmatched modal stays in sync with add."""
        return list(CARRIER_NAMES)

    def set_excel_path(self, path: str) -> dict:
        """Persist the linked-workbook path to config.json. Empty string
        clears the link. Validates that a non-empty path exists; missing
        files return ok=False without writing config."""
        try:
            p = (path or "").strip()
            cfg = ct_config.load_config()
            if not p:
                cfg["excel_path"] = ""
                ct_config.save_config(cfg)
                return {"ok": True, "error": None, "path": ""}
            if not Path(p).exists():
                return {"ok": False, "error": "File not found", "path": p}
            cfg["excel_path"] = p
            ct_config.save_config(cfg)
            return {"ok": True, "error": None, "path": p}
        except Exception as e:
            logger.exception("set_excel_path failed")
            return {"ok": False, "error": str(e), "path": path or ""}

    def create_excel_template(self, path: str) -> dict:
        """Generate a fresh Container_Tracking template at ``path`` and
        link it. Validates the parent directory exists; on success the
        path is written to ``cfg["excel_path"]``."""
        try:
            p = (path or "").strip()
            if not p:
                return {"ok": False, "error": "No path supplied", "path": ""}
            target = Path(p)
            if not target.parent.exists():
                return {"ok": False,
                        "error": f"Folder does not exist: {target.parent}",
                        "path": p}
            create_template_excel(p)
            cfg = ct_config.load_config()
            cfg["excel_path"] = p
            ct_config.save_config(cfg)
            return {"ok": True, "error": None, "path": p}
        except Exception as e:
            logger.exception("create_excel_template failed")
            return {"ok": False, "error": str(e), "path": path or ""}

    def open_linked_excel(self) -> dict:
        """Open the currently-linked workbook in Excel. Returns ok=False
        if no link is set or the file no longer exists."""
        cfg = ct_config.load_config()
        p = (cfg.get("excel_path") or "").strip()
        if not p:
            return {"ok": False, "error": "No file linked"}
        if not Path(p).exists():
            return {"ok": False, "error": "Linked file not found"}
        try:
            os.startfile(p)  # type: ignore[attr-defined]
            return {"ok": True, "error": None}
        except Exception as e:
            logger.warning("open_linked_excel failed: %s", e)
            return {"ok": False, "error": str(e)}

    def pick_excel_file(self) -> dict:
        """Show the native Open dialog and return the chosen path. The
        bridge owns this call (rather than JS) so it can reach
        ``webview.windows[0]``."""
        try:
            import webview  # local import: tests don't need pywebview installed
            wins = getattr(webview, "windows", None) or []
            if not wins:
                return {"path": None, "error": "No window"}
            result = wins[0].create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("Excel Files (*.xlsx)", "All files (*.*)"),
            )
            if not result:
                return {"path": None, "error": None}
            chosen = result[0] if isinstance(result, (list, tuple)) else result
            return {"path": chosen, "error": None}
        except Exception as e:
            logger.warning("pick_excel_file failed: %s", e)
            return {"path": None, "error": str(e)}

    def pick_excel_save_path(self) -> dict:
        """Show the native Save-As dialog for a new template."""
        try:
            import webview
            wins = getattr(webview, "windows", None) or []
            if not wins:
                return {"path": None, "error": "No window"}
            result = wins[0].create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename="Container_Tracking.xlsx",
                file_types=("Excel Files (*.xlsx)",),
            )
            if not result:
                return {"path": None, "error": None}
            chosen = result[0] if isinstance(result, (list, tuple)) else result
            return {"path": chosen, "error": None}
        except Exception as e:
            logger.warning("pick_excel_save_path failed: %s", e)
            return {"path": None, "error": str(e)}

    # --- Unmatched-CN flow (Step 6.5) -------------------------------------

    def register_unmatched(self, items: list) -> dict:
        """Register a batch of Excel-discovered CNs with ShipsGo.

        ``items`` is a list of ``{"cn": str, "carrier": str}`` entries
        sourced from the JS register-unmatched modal. Each entry's
        ``carrier`` is a display name (CARRIER_NAMES); the bridge
        resolves it to a SCAC before calling ``create_shipment``.

        HTTP 402 (NOT_ENOUGH_CREDITS) stops further attempts immediately
        — credits don't come back across the loop, so subsequent calls
        would all fail the same way. 409 already_exists is treated as
        success, matching add_container's contract.
        """
        registered = 0
        failures: list[dict] = []
        if not isinstance(items, list) or not items:
            return {"registered": 0, "failed": [], "credits_used": 0}

        token = ct_credentials.get_api_token()
        if not token:
            return {"registered": 0,
                    "failed": [{"cn": "", "error": "API token not configured"}],
                    "credits_used": 0}

        db = ct_config.load_tracking_db()
        client = ShipsGoClient(token)

        for entry in items:
            if not isinstance(entry, dict):
                failures.append({"cn": "", "error": "malformed entry"})
                continue
            cn_up = (entry.get("cn") or "").strip().upper()
            carrier = (entry.get("carrier") or "").strip()
            if not cn_up:
                failures.append({"cn": cn_up, "error": "missing cn"})
                continue
            if not carrier:
                failures.append({"cn": cn_up, "error": "missing carrier"})
                continue
            scac = resolve_scac(carrier)
            try:
                resp = client.create_shipment(container_number=cn_up,
                                              carrier_scac=scac)
            except Exception as e:
                failures.append({"cn": cn_up, "error": str(e)})
                continue
            if isinstance(resp, dict) and resp.get("error") == "NOT_ENOUGH_CREDITS":
                failures.append({"cn": cn_up, "error": "NOT_ENOUGH_CREDITS"})
                # Bail: credits won't recover within this batch.
                break
            sid = (resp.get("id") or resp.get("shipment_id")
                   if isinstance(resp, dict) else None)
            rec = db.get(cn_up) or {"container_number": cn_up}
            rec["shipment_id"] = sid
            rec["carrier"] = carrier
            rec["scac"] = scac
            db[cn_up] = rec
            registered += 1

        ct_config.save_json(ct_config.TRACKING_DB_FILE, db)
        # Credits used == successful registrations. 409 already_exists
        # also counts as registered but doesn't actually consume a credit;
        # the UI message already warns that re-registration is free.
        return {"registered": registered, "failed": failures,
                "credits_used": registered}

    def dismiss_unmatched(self, cns: list) -> dict:
        """Add a batch of CNs to ``cfg["dismissed"]`` so future refreshes
        don't re-prompt for them. Idempotent."""
        try:
            cfg = ct_config.load_config()
            existing = list(cfg.get("dismissed") or [])
            seen = set(s.upper() for s in existing)
            for cn in cns or []:
                cn_up = (cn or "").strip().upper()
                if cn_up and cn_up not in seen:
                    existing.append(cn_up)
                    seen.add(cn_up)
            cfg["dismissed"] = existing
            ct_config.save_config(cfg)
            return {"ok": True, "dismissed": existing}
        except Exception as e:
            logger.exception("dismiss_unmatched failed")
            return {"ok": False, "dismissed": [], "error": str(e)}
