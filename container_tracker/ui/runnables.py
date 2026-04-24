"""QRunnable workers for ShipsGo background ops.

Pattern: each runnable owns a `QObject` signal-carrier since QRunnable
itself can't emit. Workers call logger.info for progress; signals are for
terminal states (completed, auth_error, failed, etc.). Log records flow
through QtLogHandler -> ActivityLog on the UI thread automatically.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal

from container_tracker.core.api import (
    ShipsGoAuthError,
    ShipsGoClient,
    extract_fields,
)
from container_tracker.core.updates import UpdateInfo, check_for_update


logger = logging.getLogger(__name__)


# --- Refresh -----------------------------------------------------------

class RefreshSignals(QObject):
    completed = Signal(dict)     # updated db
    failed = Signal(str)         # error message
    auth_error = Signal()        # HTTP 401


class RefreshRunnable(QRunnable):
    def __init__(self, client: ShipsGoClient, db: dict[str, dict[str, Any]]) -> None:
        super().__init__()
        self.signals = RefreshSignals()
        self._client = client
        self._db = db

    def run(self) -> None:
        try:
            logger.info("Refreshing...")
            all_shipments = self._client.list_shipments()
            logger.info("Found %d shipments", len(all_shipments))

            # Build lookup by id and by container_number.
            shipment_map: dict[str, dict[str, Any]] = {}
            for s in all_shipments:
                if not isinstance(s, dict):
                    continue
                if sid := s.get("id"):
                    shipment_map[str(sid)] = s
                if cnum := (s.get("container_number") or "").upper():
                    shipment_map[cnum] = s

            new_db = dict(self._db)

            # Populate from API if local DB is empty (first-run after install).
            if not new_db and all_shipments:
                for s in all_shipments:
                    if not isinstance(s, dict):
                        continue
                    cnum = (s.get("container_number") or "").upper()
                    if not cnum:
                        continue
                    carrier = s.get("carrier") or {}
                    new_db[cnum] = {
                        "container_number": cnum,
                        "shipping_line": carrier.get("name", "") if isinstance(carrier, dict) else "",
                        "carrier_scac": carrier.get("scac", "") if isinstance(carrier, dict) else "",
                        "shipment_id": s.get("id", ""),
                        "registered_at": s.get("created_at", ""),
                        "last_refreshed": None,
                    }

            matched = 0
            unmatched = 0
            delayed = 0
            for key, record in new_db.items():
                sid = str(record.get("shipment_id", "") or "")
                cnum = record.get("container_number", "").upper()
                shipment = shipment_map.get(sid) or shipment_map.get(cnum)
                if shipment:
                    full_id = shipment.get("id")
                    if full_id:
                        try:
                            shipment = self._client.get_shipment(full_id)
                            record["shipment_id"] = full_id
                        except ShipsGoAuthError:
                            raise
                        except Exception as exc:
                            logger.info("  get_shipment(%s) failed: %s", full_id, exc)
                    fields = extract_fields(shipment)
                    record.update(fields)
                    record["last_refreshed"] = datetime.now(timezone.utc).isoformat()
                    matched += 1
                    delay_val = record.get("delay_days_int")
                    if isinstance(delay_val, int) and delay_val > 0:
                        delayed += 1
                    logger.info(
                        "  %s: Status=%s, ETA=%s, %s -> %s",
                        key,
                        record.get("status", ""),
                        record.get("eta", ""),
                        record.get("pol", ""),
                        record.get("pod", ""),
                    )
                else:
                    unmatched += 1
                    logger.info("  %s: no matching shipment found", key)
                    record["last_refreshed"] = datetime.now(timezone.utc).isoformat()

            logger.info("--- DONE: %d matched, %d unmatched, %d delayed", matched, unmatched, delayed)
            self.signals.completed.emit(new_db)
        except ShipsGoAuthError:
            logger.info("Refresh failed: invalid API key (HTTP 401)")
            self.signals.auth_error.emit()
        except Exception as exc:
            logger.info("Refresh failed: %s", exc)
            self.signals.failed.emit(str(exc))


# --- Add & Track -------------------------------------------------------

class AddTrackSignals(QObject):
    completed = Signal(dict)         # new record dict
    already_tracked = Signal(str)    # container number
    no_credits = Signal()
    auth_error = Signal()
    failed = Signal(str)


class AddTrackRunnable(QRunnable):
    def __init__(self, client: ShipsGoClient, container_number: str, carrier_scac: str) -> None:
        super().__init__()
        self.signals = AddTrackSignals()
        self._client = client
        self._container = container_number.strip().upper()
        self._scac = carrier_scac.strip().upper()

    def run(self) -> None:
        try:
            logger.info("Adding %s (carrier %s)...", self._container, self._scac)
            result = self._client.create_shipment(
                container_number=self._container,
                carrier_scac=self._scac,
            )
            if result.get("already_exists"):
                logger.info("  %s already tracked (no credit used)", self._container)
                self.signals.already_tracked.emit(self._container)
                return
            if result.get("error") == "NOT_ENOUGH_CREDITS":
                logger.info("  ShipsGo: not enough credits")
                self.signals.no_credits.emit()
                return

            shipment_id = str(result.get("id", "") or "")
            logger.info("  Registered %s (shipment_id=%s)", self._container, shipment_id)

            # Fetch full details so the record starts with populated fields.
            record: dict[str, Any] = {
                "container_number": self._container,
                "carrier_scac": self._scac,
                "shipment_id": shipment_id,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "last_refreshed": datetime.now(timezone.utc).isoformat(),
            }
            if shipment_id:
                try:
                    shipment = self._client.get_shipment(shipment_id)
                    record.update(extract_fields(shipment))
                except ShipsGoAuthError:
                    raise
                except Exception as exc:
                    logger.info("  get_shipment(%s) failed: %s", shipment_id, exc)
            self.signals.completed.emit(record)
        except ShipsGoAuthError:
            logger.info("Add failed: invalid API key (HTTP 401)")
            self.signals.auth_error.emit()
        except Exception as exc:
            logger.info("Add failed: %s", exc)
            self.signals.failed.emit(str(exc))


# --- Update check ------------------------------------------------------

class UpdateCheckSignals(QObject):
    update_available = Signal(UpdateInfo)


class UpdateCheckRunnable(QRunnable):
    """Run the GitHub releases check off the UI thread.

    Emits `update_available` only when a newer release is found. All failures
    (network error, malformed response, no tag, current-or-older version) log
    a line via core.updates and emit nothing — per spec §6 "fail silently."
    """

    def __init__(self, current_version: str, timeout: float = 5.0) -> None:
        super().__init__()
        self.signals = UpdateCheckSignals()
        self._current_version = current_version
        self._timeout = timeout

    def run(self) -> None:
        try:
            result = check_for_update(self._current_version, timeout=self._timeout)
        except Exception as exc:  # defensive: core.updates swallows, but belt-and-suspenders
            logger.info("update check raised unexpectedly: %s", exc)
            return
        if result is not None:
            self.signals.update_available.emit(result)
