# Phase 5 — Backend Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire every action in the main window to real backend behavior. After Phase 5, Refresh pulls live ShipsGo data and writes to the linked Excel; Add & Track registers new containers; Remove Selected deletes from tracking DB; Browse / Create Template / Open in Excel all work on real files; activity log displays real refresh progress. Error paths (401, insufficient credits, malformed Excel) surface as modals. Delete the v1.0.0 monolith at the end since the new UI fully supersedes it.

**Architecture:** Background ops via `QThreadPool.globalInstance()` + `QRunnable` with a separate `QObject` signal-carrier per runnable (standard PySide6 pattern — QRunnable can't emit signals directly). Workers call `logger.info(...)` which routes through `QtLogHandler` → `Signal(str)` → `ActivityLog` slot on the UI thread via default `QueuedConnection`. No direct widget calls from workers. Error modals are shared helper functions on `MainWindow` so any action can raise them.

**Tech Stack:** Python 3.11+, PySide6 ≥ 6.6, pytest (no new deps).

**Spec:** [2026-04-23-pyside6-migration-design.md §3.2, §5.2, §10](../specs/2026-04-23-pyside6-migration-design.md)

---

## Checkpoint structure

Three internal checkpoints. Autonomous cadence (user reviews at phase boundary per this session's instructions).

- **A (Tasks 1–5):** File ops + logging. Activity log shows real log records; tracking data loads from `core.persistence`; Browse / Create Template / Open in Excel all functional (no ShipsGo calls yet).
- **B (Tasks 6–11):** Network ops + error paths. Refresh, Add & Track, Remove Selected, ShipsGoAuthError modal, ExcelFormatError modal.
- **C (Tasks 12–14):** Clean up dead code + full smoke test. Delete monolith + `sample_data.py`; E2E test against the real ShipsGo API using the stored token.

---

## File Structure

Created by end of Phase 5:

```
container_tracker/ui/
  runnables.py         # RefreshSignals/RefreshRunnable, AddTrackSignals/AddTrackRunnable
tests/
  test_runnables.py    # unit tests for runnable.run() with mocked ShipsGoClient
```

Modified:

```
container_tracker/
  __main__.py              # pass qt_handler to MainWindow so it can connect to activity log
container_tracker/ui/
  main_window.py           # connect QtLogHandler; real data load; all button handlers; runnable dispatch; error modals
```

Deleted:

```
container_tracker_gui.py              # obsolete monolith (end of Phase 5 C)
container_tracker/ui/sample_data.py   # superseded by real load_tracking_data (end of Phase 5 C)
```

**Standing conventions:** `mypy --strict container_tracker` clean. One commit per task. No `--no-verify`. Smoke tests use the retry-loop PowerShell pattern. If visual issues appear, document in `docs/superpowers/polish-backlog.md` under "Phase 5 deferred polish" — do NOT try to fix polish inline.

---

## Task 1: Connect `QtLogHandler` to `ActivityLog` widget

**Files:**
- Modify: `container_tracker/__main__.py`
- Modify: `container_tracker/ui/main_window.py`

The handler is constructed in `_configure_logging` but its signal is currently unused. Pass the handler through to `MainWindow`, have the window connect its activity-log widget to the `log_emitted` signal, and append lines on emission.

- [ ] **Step 1: Pass `qt_handler` into MainWindow.__init__**

In `container_tracker/__main__.py`, find `MainWindow(config)` and change to `MainWindow(config, qt_handler)`.

- [ ] **Step 2: Update `MainWindow.__init__` signature**

Add `qt_handler: QtLogHandler` parameter. At the start of `_build_layout` (or right before activity log creation), connect:

```python
from container_tracker.ui.widgets import QtLogHandler

class MainWindow(QMainWindow):
    def __init__(self, config: dict[str, Any], qt_handler: QtLogHandler) -> None:
        super().__init__()
        self._config = config
        self._qt_handler = qt_handler
        ...
```

In `_build_layout`, after constructing `self._activity_log`, add:

```python
self._qt_handler.log_emitted.connect(self._activity_log.appendPlainText)
```

- [ ] **Step 3: Smoke-test with a manual log emission**

Run:

```bash
python -c "
import sys, logging
from PySide6.QtWidgets import QApplication
from container_tracker.ui.widgets import QtLogHandler
from container_tracker.ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)
handler = QtLogHandler()
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)

mw = MainWindow({'company_name': 'Test', 'contact_email': '', 'excel_path': '', 'dark_mode': False, 'dismissed': []}, handler)
logging.getLogger(__name__).info('hello from test')
app.processEvents()
print('activity log contents:', repr(mw._activity_log.toPlainText()))
"
```

Expected: output contains `hello from test` in the activity log.

- [ ] **Step 4: Run full tests + mypy**

`pytest -v && mypy --strict container_tracker`. Note: any test that constructs `MainWindow({...})` with one arg will break. Fix those call sites — expected breakage in `test_widgets.py` / `test_dialogs.py` IF any construct MainWindow. (Quick grep first: `grep -rn "MainWindow(" tests/`.) If breakage, add the handler arg to test calls — can use a bare `QtLogHandler()` instance.

- [ ] **Step 5: Commit**

```bash
git add container_tracker/__main__.py container_tracker/ui/main_window.py tests/
git commit -m "ui: connect QtLogHandler to ActivityLog; logs flow from any module to the pane"
```

---

## Task 2: Replace sample data with real `load_tracking_data`

**Files:**
- Modify: `container_tracker/ui/main_window.py`

`_populate_sample_data` reads from `sample_tracking_db()`. Replace with `core.persistence.load_tracking_data()`. If the DB is empty, the table and stat cards show zero — that's correct for a fresh install.

- [ ] **Step 1: Modify `_populate_sample_data` (rename to `_populate_data`)**

Replace:

```python
from container_tracker.ui.sample_data import sample_tracking_db

def _populate_sample_data(self) -> None:
    db = sample_tracking_db()
    self._model.set_records(list(db.values()))
    self._refresh_stat_cards(db)
```

with:

```python
from container_tracker.core.persistence import load_tracking_data

def _populate_data(self) -> None:
    db = load_tracking_data()
    self._tracking_db = db  # keep a reference for mutations
    self._model.set_records(list(db.values()))
    self._refresh_stat_cards(db)
```

Also rename the call in `__init__` from `self._populate_sample_data()` to `self._populate_data()`. Add `self._tracking_db: dict[str, dict[str, Any]] = {}` as an instance attribute declared in `__init__` before `_populate_data` is called (helps mypy and keeps state explicit).

- [ ] **Step 2: Remove the sample-data import**

`from container_tracker.ui.sample_data import sample_tracking_db` → delete. Keep `sample_data.py` in place for now; it gets deleted in Task 13.

- [ ] **Step 3: Smoke test**

Run `python -m container_tracker` via PowerShell pattern. Window renders. If the machine's `tracking_data.json` is empty, table shows 0 rows, stat cards show 0 / 0 / 0 / 0. If it has records from prior runs, those render.

- [ ] **Step 4: Full tests + mypy**

Expected: all pass. No test breakage — Phase 3's test for `_proxy.rowCount() == 10` was the spot-check script; it's not a pytest test.

- [ ] **Step 5: Commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: load tracking_data.json instead of sample data; expose self._tracking_db"
```

---

## Task 3: Wire Browse button

**Files:**
- Modify: `container_tracker/ui/main_window.py`

Browse opens a file dialog, validates the workbook can be read, then saves the path into config and refreshes the linked card. If the Excel file is malformed (`ExcelFormatError`), show a modal with the verbatim error message.

- [ ] **Step 1: Re-enable the Browse button in `_build_layout`**

Find the line `self._linked._browse_button.setEnabled(False)` (from Phase 4 CPA Task 3). Delete it.

- [ ] **Step 2: Connect the `browse_requested` signal**

After the `LinkedSpreadsheetCard` is instantiated, add:

```python
self._linked.browse_requested.connect(self._on_browse)
```

- [ ] **Step 3: Implement `_on_browse`**

Add this method to MainWindow:

```python
def _on_browse(self) -> None:
    """Open file dialog, validate, persist."""
    from PySide6.QtWidgets import QFileDialog
    from container_tracker.core.excel import ExcelFormatError, read_container_list
    from container_tracker.core.persistence import save_config
    from pathlib import Path

    start_dir = str(self._config.get("excel_path") or Path.home())
    path, _ = QFileDialog.getOpenFileName(
        self,
        "Select container spreadsheet",
        start_dir,
        "Excel files (*.xlsx *.xlsm)",
    )
    if not path:
        return  # user cancelled

    # Validate by reading the container column.
    try:
        containers = read_container_list(Path(path))
    except ExcelFormatError as exc:
        self._show_error_modal("Can't read spreadsheet", str(exc))
        return

    self._config["excel_path"] = path
    save_config(self._config)
    self._linked.set_path(path)
    logger.info("Linked spreadsheet: %s (%d containers detected)", path, len(containers))
```

- [ ] **Step 4: Add the error modal helper to MainWindow**

```python
def _show_error_modal(self, title: str, message: str) -> None:
    from PySide6.QtWidgets import QMessageBox
    box = QMessageBox(self)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(message)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()
```

- [ ] **Step 5: Run full tests + mypy**

`pytest -v && mypy --strict container_tracker`.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: wire Browse — file dialog, validation, persist excel_path, error modal"
```

---

## Task 4: Wire Create Template button

**Files:**
- Modify: `container_tracker/ui/main_window.py`

- [ ] **Step 1: Re-enable Create Template button**

Delete `self._linked._create_button.setEnabled(False)`.

- [ ] **Step 2: Connect signal and implement handler**

After the `LinkedSpreadsheetCard` instantiation block:

```python
self._linked.create_requested.connect(self._on_create_template)
```

Method:

```python
def _on_create_template(self) -> None:
    """Pick save path, create template, persist."""
    from PySide6.QtWidgets import QFileDialog
    from container_tracker.core.excel import create_template
    from container_tracker.core.persistence import save_config
    from pathlib import Path

    start_path = str(Path.home() / "container_tracking.xlsx")
    path, _ = QFileDialog.getSaveFileName(
        self,
        "Create template spreadsheet",
        start_path,
        "Excel files (*.xlsx)",
    )
    if not path:
        return
    try:
        create_template(Path(path))
    except Exception as exc:
        self._show_error_modal("Can't create template", str(exc))
        return

    self._config["excel_path"] = path
    save_config(self._config)
    self._linked.set_path(path)
    logger.info("Created template at %s and linked it", path)
```

- [ ] **Step 3: Run tests + mypy**, then commit:

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: wire Create Template — save dialog, create blank template, persist path"
```

---

## Task 5: Wire Open in Excel button

**Files:**
- Modify: `container_tracker/ui/main_window.py`

- [ ] **Step 1: Remove the force-disable on `_open_button`**

Delete `self._linked._open_button.setEnabled(False)` from Phase 4 CPA. This restores the widget's built-in "enable when path is set" behavior.

- [ ] **Step 2: Connect the signal**

```python
self._linked.open_requested.connect(self._on_open_excel)
```

- [ ] **Step 3: Implement handler**

```python
def _on_open_excel(self, path: str) -> None:
    """Open the linked spreadsheet in the system default handler (Excel on Windows)."""
    import os
    import subprocess
    import sys
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        logger.info("Opened %s in default handler", path)
    except Exception as exc:
        self._show_error_modal("Can't open spreadsheet", str(exc))
```

- [ ] **Step 4: Refresh linked card state after `__init__` so Open button reflects the current path**

In `_build_layout`, after `self._linked = LinkedSpreadsheetCard(...)` and the signal connections, add:

```python
# Phase 5: ensure Open button reflects current path state (was force-disabled in Phase 4).
self._linked.set_path(str(self._config.get("excel_path", "") or ""))
```

- [ ] **Step 5: Run tests + mypy + commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: wire Open in Excel; restore dynamic enable-when-path-set behavior"
```

---

## CHECKPOINT A — STOP

Verify by running `python -m container_tracker`. The app should:
- Show an empty table if `tracking_data.json` is empty (or real data if not).
- Browse, Create Template, Open in Excel all functional.
- Activity log shows startup lines in v1.0.0 format.

Report: pytest count, mypy output, smoke test result, `git log --oneline -8`.

---

## Task 6: Create `runnables.py` with RefreshRunnable + AddTrackRunnable

**Files:**
- Create: `container_tracker/ui/runnables.py`
- Create: `tests/test_runnables.py`

Standard PySide6 pattern: `QRunnable` subclass owns a `QObject` signal-carrier. Workers call `logger.info` for progress (which flows through `QtLogHandler`); signals carry terminal states only.

- [ ] **Step 1: Write `tests/test_runnables.py`**

```python
"""Unit tests for RefreshRunnable / AddTrackRunnable business logic."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from container_tracker.core.api import ShipsGoAuthError
from container_tracker.ui.runnables import (
    AddTrackRunnable,
    RefreshRunnable,
)


class TestRefreshRunnable:
    def test_successful_refresh_emits_completed_with_updated_db(self, qapp) -> None:
        client = MagicMock()
        client.list_shipments.return_value = [
            {
                "id": "ship_001",
                "container_number": "MSKU1234567",
                "status": "SAILING",
                "carrier": {"name": "MAERSK LINE"},
                "route": {
                    "port_of_loading": {"location": {"name": "Shanghai"}, "date_of_loading": "2026-04-01"},
                    "port_of_discharge": {
                        "location": {"name": "LA"},
                        "date_of_discharge": "2026-05-05",
                        "date_of_discharge_initial": "2026-05-01",
                    },
                    "transit_percentage": 42,
                },
            }
        ]
        # get_shipment returns the same shipment wrapped.
        client.get_shipment.return_value = {"shipment": client.list_shipments.return_value[0]}
        db = {"MSKU1234567": {"container_number": "MSKU1234567", "shipment_id": "ship_001"}}

        runnable = RefreshRunnable(client, db)
        received: list[dict[str, Any]] = []
        runnable.signals.completed.connect(received.append)
        runnable.run()

        assert received, "completed signal never emitted"
        new_db = received[0]
        assert "MSKU1234567" in new_db
        assert new_db["MSKU1234567"]["status"] == "SAILING"
        assert new_db["MSKU1234567"]["eta"] == "2026-05-05"

    def test_auth_error_emits_auth_error_signal(self, qapp) -> None:
        client = MagicMock()
        client.list_shipments.side_effect = ShipsGoAuthError("bad token")
        runnable = RefreshRunnable(client, {})
        auth_received: list[bool] = []
        failed_received: list[str] = []
        runnable.signals.auth_error.connect(lambda: auth_received.append(True))
        runnable.signals.failed.connect(failed_received.append)
        runnable.run()
        assert auth_received == [True]
        assert failed_received == []

    def test_generic_error_emits_failed(self, qapp) -> None:
        client = MagicMock()
        client.list_shipments.side_effect = RuntimeError("network unreachable")
        runnable = RefreshRunnable(client, {})
        failed: list[str] = []
        runnable.signals.failed.connect(failed.append)
        runnable.run()
        assert len(failed) == 1
        assert "network" in failed[0].lower()

    def test_empty_db_still_runs_cleanly(self, qapp) -> None:
        client = MagicMock()
        client.list_shipments.return_value = []
        runnable = RefreshRunnable(client, {})
        completed: list[dict[str, Any]] = []
        runnable.signals.completed.connect(completed.append)
        runnable.run()
        assert completed == [{}]


class TestAddTrackRunnable:
    def test_new_container_registered_and_refreshed(self, qapp) -> None:
        client = MagicMock()
        client.create_shipment.return_value = {"id": "ship_new"}
        client.get_shipment.return_value = {
            "shipment": {
                "id": "ship_new",
                "container_number": "MSKU9999999",
                "status": "BOOKED",
                "carrier": {"name": "MAERSK LINE"},
                "route": {},
            }
        }
        runnable = AddTrackRunnable(client, "MSKU9999999", "MAEU")
        completed: list[dict[str, Any]] = []
        runnable.signals.completed.connect(completed.append)
        runnable.run()
        assert len(completed) == 1
        record = completed[0]
        assert record["container_number"] == "MSKU9999999"
        assert record["shipment_id"] == "ship_new"

    def test_already_exists_emits_already_tracked(self, qapp) -> None:
        client = MagicMock()
        client.create_shipment.return_value = {"already_exists": True}
        runnable = AddTrackRunnable(client, "MSKU1234567", "MAEU")
        already: list[str] = []
        completed: list[dict[str, Any]] = []
        runnable.signals.already_tracked.connect(already.append)
        runnable.signals.completed.connect(completed.append)
        runnable.run()
        assert already == ["MSKU1234567"]
        assert completed == []

    def test_insufficient_credits_emits_no_credits(self, qapp) -> None:
        client = MagicMock()
        client.create_shipment.return_value = {"error": "NOT_ENOUGH_CREDITS"}
        runnable = AddTrackRunnable(client, "MSKU1234567", "MAEU")
        no_credits: list[bool] = []
        runnable.signals.no_credits.connect(lambda: no_credits.append(True))
        runnable.run()
        assert no_credits == [True]

    def test_auth_error_emits_auth_error(self, qapp) -> None:
        client = MagicMock()
        client.create_shipment.side_effect = ShipsGoAuthError("bad")
        runnable = AddTrackRunnable(client, "MSKU1234567", "MAEU")
        auth: list[bool] = []
        runnable.signals.auth_error.connect(lambda: auth.append(True))
        runnable.run()
        assert auth == [True]
```

- [ ] **Step 2: Run tests, confirm they fail**

`pytest tests/test_runnables.py -v` — expect `ModuleNotFoundError`.

- [ ] **Step 3: Implement `container_tracker/ui/runnables.py`**

```python
"""QRunnable workers for ShipsGo background ops.

Pattern: each runnable owns a `QObject` signal-carrier since QRunnable
itself can't emit. Workers call logger.info for progress; signals are for
terminal states (completed, auth_error, failed, etc.). Log records flow
through QtLogHandler → ActivityLog on the UI thread automatically.
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


logger = logging.getLogger(__name__)


# ─── Refresh ────────────────────────────────────────────────────────────

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
                    if isinstance(record.get("delay_days_int"), int) and record["delay_days_int"] > 0:
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


# ─── Add & Track ────────────────────────────────────────────────────────

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
```

- [ ] **Step 4: Run tests, confirm pass**

`pytest tests/test_runnables.py -v`. Expected: 8 pass.

- [ ] **Step 5: Full tests + mypy**

`pytest -v && mypy --strict container_tracker`. Expected: 213 pass (205 + 8 new), mypy clean on 19 files.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/runnables.py tests/test_runnables.py
git commit -m "ui: add RefreshRunnable + AddTrackRunnable (QRunnable + QObject signal carriers)"
```

---

## Task 7: Wire Refresh button

**Files:**
- Modify: `container_tracker/ui/main_window.py`

- [ ] **Step 1: Re-enable the Refresh button**

Delete `self._refresh_button.setEnabled(False)` from the action-row block.

- [ ] **Step 2: Connect click + add handlers**

After the button is created, connect:

```python
self._refresh_button.clicked.connect(self._on_refresh)
```

Handler methods:

```python
def _ensure_client(self) -> ShipsGoClient | None:
    """Lazy-construct a ShipsGoClient using the current keyring token. Returns None if no token."""
    from container_tracker.core.persistence import get_api_token
    token = get_api_token()
    if not token:
        self._show_auth_error_modal()
        return None
    if self._client is None or getattr(self._client, "_last_token", None) != token:
        self._client = ShipsGoClient(token)
        self._client._last_token = token  # type: ignore[attr-defined]
    return self._client

def _on_refresh(self) -> None:
    from container_tracker.core.persistence import save_tracking_data
    from container_tracker.core.excel import write_tracking_report, ExcelFormatError
    from container_tracker.ui.runnables import RefreshRunnable
    from PySide6.QtCore import QThreadPool
    from pathlib import Path

    client = self._ensure_client()
    if client is None:
        return

    self._refresh_button.setEnabled(False)

    runnable = RefreshRunnable(client, dict(self._tracking_db))

    def on_completed(new_db: dict[str, dict[str, Any]]) -> None:
        self._tracking_db = new_db
        save_tracking_data(new_db)
        self._model.set_records(list(new_db.values()))
        self._refresh_stat_cards(new_db)
        # Also write to linked Excel if a path is configured.
        excel_path = self._config.get("excel_path", "")
        if excel_path:
            try:
                count = write_tracking_report(Path(excel_path), new_db)
                logger.info("Excel updated: %d rows", count)
            except ExcelFormatError as exc:
                self._show_error_modal("Can't update spreadsheet", str(exc))
            except Exception as exc:
                logger.info("Excel update failed: %s", exc)
        self._refresh_button.setEnabled(True)

    def on_failed(msg: str) -> None:
        self._show_error_modal("Refresh failed", msg)
        self._refresh_button.setEnabled(True)

    def on_auth() -> None:
        self._show_auth_error_modal()
        self._refresh_button.setEnabled(True)

    runnable.signals.completed.connect(on_completed)
    runnable.signals.failed.connect(on_failed)
    runnable.signals.auth_error.connect(on_auth)
    QThreadPool.globalInstance().start(runnable)
```

Also add `self._client: ShipsGoClient | None = None` as an instance attribute in `__init__` before `_build_layout` runs.

Add imports at the top of `main_window.py`:

```python
from container_tracker.core.api import ShipsGoAuthError, ShipsGoClient
```

- [ ] **Step 3: Add `_show_auth_error_modal` helper**

```python
def _show_auth_error_modal(self) -> None:
    """401 from ShipsGo — prompt user to open Settings."""
    from PySide6.QtWidgets import QMessageBox
    box = QMessageBox(self)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("API key invalid")
    box.setText(
        "Your ShipsGo API key is invalid. Open Settings to update it."
    )
    open_settings = box.addButton("Open Settings…", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() is open_settings:
        self._on_settings_clicked()
```

- [ ] **Step 4: Full tests + mypy**

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: wire Refresh — QThreadPool dispatch, DB + Excel update, 401 modal on auth error"
```

---

## Task 8: Wire Add & Track button

**Files:**
- Modify: `container_tracker/ui/main_window.py`

- [ ] **Step 1: Re-enable Add & Track**

Delete `self._add_button.setEnabled(False)`.

- [ ] **Step 2: Connect and implement**

```python
self._add_button.clicked.connect(self._on_add_track)
```

Handler:

```python
def _on_add_track(self) -> None:
    from container_tracker.core.api import resolve_scac
    from container_tracker.core.persistence import save_tracking_data
    from container_tracker.ui.runnables import AddTrackRunnable
    from PySide6.QtCore import QThreadPool

    text = self._add_input.text().strip().upper()
    if len(text) < 10:
        self._show_error_modal("Invalid container number", "Container numbers should be at least 10 characters.")
        return
    carrier_name = self._carrier_combo.currentText()
    scac = resolve_scac(carrier_name)

    client = self._ensure_client()
    if client is None:
        return

    self._add_button.setEnabled(False)

    runnable = AddTrackRunnable(client, text, scac)

    def on_completed(record: dict[str, Any]) -> None:
        cn = record.get("container_number", "").upper()
        if cn:
            self._tracking_db[cn] = record
            save_tracking_data(self._tracking_db)
            self._model.set_records(list(self._tracking_db.values()))
            self._refresh_stat_cards(self._tracking_db)
            logger.info("Added %s to tracking", cn)
        self._add_input.clear()
        self._add_button.setEnabled(True)

    def on_already_tracked(cn: str) -> None:
        self._show_error_modal("Already tracked", f"{cn} is already in your tracking list. Use Refresh to update it.")
        self._add_button.setEnabled(True)

    def on_no_credits() -> None:
        self._show_error_modal("Not enough credits", "ShipsGo reports you don't have enough credits to track a new container. Visit shipsgo.com to top up.")
        self._add_button.setEnabled(True)

    def on_auth() -> None:
        self._show_auth_error_modal()
        self._add_button.setEnabled(True)

    def on_failed(msg: str) -> None:
        self._show_error_modal("Add failed", msg)
        self._add_button.setEnabled(True)

    runnable.signals.completed.connect(on_completed)
    runnable.signals.already_tracked.connect(on_already_tracked)
    runnable.signals.no_credits.connect(on_no_credits)
    runnable.signals.auth_error.connect(on_auth)
    runnable.signals.failed.connect(on_failed)
    QThreadPool.globalInstance().start(runnable)
```

- [ ] **Step 3: Full tests + mypy + commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: wire Add & Track — validate, dispatch runnable, handle auth/credits/duplicate"
```

---

## Task 9: Wire Remove Selected button

**Files:**
- Modify: `container_tracker/ui/main_window.py`

- [ ] **Step 1: Re-enable Remove button**

Delete `self._remove_button.setEnabled(False)`.

- [ ] **Step 2: Connect and implement**

```python
self._remove_button.clicked.connect(self._on_remove_selected)
```

Handler:

```python
def _on_remove_selected(self) -> None:
    from PySide6.QtWidgets import QMessageBox
    from container_tracker.core.persistence import save_tracking_data

    selection = self._table.selectionModel().selectedRows()
    if not selection:
        self._show_error_modal("No selection", "Select one or more rows to remove.")
        return

    # Map proxy rows back to source rows, then to records.
    source_rows: list[int] = []
    container_numbers: list[str] = []
    for proxy_index in selection:
        source_index = self._proxy.mapToSource(proxy_index)
        record = self._model.record_at(source_index.row())
        if record is None:
            continue
        source_rows.append(source_index.row())
        container_numbers.append(str(record.get("container_number", "")))

    if not container_numbers:
        return

    confirm = QMessageBox.question(
        self,
        "Remove from tracking",
        f"Remove {len(container_numbers)} container(s) from tracking?\n\n"
        + ", ".join(container_numbers),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if confirm != QMessageBox.StandardButton.Yes:
        return

    # Remove from tracking_db and model.
    for cn in container_numbers:
        self._tracking_db.pop(cn, None)
    save_tracking_data(self._tracking_db)
    self._model.remove_rows(source_rows)
    self._refresh_stat_cards(self._tracking_db)
    logger.info("Removed %d container(s): %s", len(container_numbers), container_numbers)
```

- [ ] **Step 3: Tests + mypy + commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: wire Remove Selected — confirm dialog, DB + model mutation, persist"
```

---

## Task 10: (Merged into Tasks 7 & 8 — ShipsGoAuthError modal is already shared via `_show_auth_error_modal`.)

Skip this task; the helper was added in Task 7 and is re-used by Task 8.

---

## Task 11: (Merged into Task 3 — ExcelFormatError modal is already shared via `_show_error_modal`.)

Skip this task; the helper was added in Task 3 and is re-used by Task 7 (Excel write) as well.

---

## CHECKPOINT B — STOP

Smoke test at this point:
- Click Refresh with a valid token and existing tracking data → list_shipments called, progress in activity log, table populates.
- Type a new container number + click Add & Track → creates a shipment. If already tracked, modal says so.
- Select rows + click Remove → confirmation modal, then rows disappear.

Report: pytest count, mypy output, `git log --oneline -15`.

---

## Task 12: Delete obsolete monolith `container_tracker_gui.py`

**Files:**
- Delete: `container_tracker_gui.py`

- [ ] **Step 1: Verify no imports**

```bash
grep -rn "container_tracker_gui\|from container_tracker_gui" --include='*.py' . 2>&1 | grep -v '^docs/' | grep -v 'Binary file' || echo "no python imports found"
```

Expected: "no python imports found".

Also check that `installer.iss`, `ContainerTracker.spec`, and `build.bat` don't reference it as a source file (they reference `dist\ContainerTracker.exe`, not the .py source, so they're fine).

- [ ] **Step 2: Delete**

```bash
git rm container_tracker_gui.py
```

- [ ] **Step 3: Run tests + mypy + smoke test**

`pytest -v && mypy --strict container_tracker`. Launch `python -m container_tracker` to confirm app still launches.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: delete obsolete container_tracker_gui.py monolith (superseded by new ui/)"
```

---

## Task 13: Delete `container_tracker/ui/sample_data.py`

**Files:**
- Delete: `container_tracker/ui/sample_data.py`

- [ ] **Step 1: Verify no imports**

```bash
grep -rn "from container_tracker.ui.sample_data\|import sample_data" --include='*.py' . 2>&1
```

Expected: no results (Task 2 removed the import from main_window.py).

- [ ] **Step 2: Delete**

```bash
git rm container_tracker/ui/sample_data.py
```

- [ ] **Step 3: Tests + mypy + commit**

```bash
git commit -m "chore: delete sample_data.py (superseded by real load_tracking_data)"
```

---

## Task 14: End-to-end smoke test

**Files:** none modified.

- [ ] **Step 1: Full test suite**

`pytest -v` → all pass.
`mypy --strict container_tracker` → clean.

- [ ] **Step 2: Launch and verify via PowerShell**

Use the retry-loop pattern with `MODULE = "container_tracker"`. Verify handle non-zero, title correct, clean exit 0 via WM_CLOSE.

- [ ] **Step 3: Real-data smoke test (if a keyring token is present)**

Optional — if the machine has a real ShipsGo token, launch the app, click Refresh, verify rows populate. Do NOT add test code. Document in the checkpoint report whether this was performed.

- [ ] **Step 4: No commit.**

---

## CHECKPOINT C — STOP — PHASE 5 COMPLETE

Report format:

- Commits added + SHAs
- pytest count, mypy output
- Monolith deletion verified (line count before/after in the repo)
- PowerShell smoke test output
- `git log --oneline -25`
- Polish-backlog additions (if any)

---

## Self-Review

**Spec coverage:**
- §3.2 Threading: QThreadPool + QRunnable + signals + QueuedConnection → Task 6, 7, 8.
- §4.1 ShipsGoAuthError → Task 7 `_show_auth_error_modal`.
- §4.3 ExcelFormatError → Task 3 (Browse) + Task 7 (write after refresh).
- §5.2 Activity log receives via Signal(str), never direct worker calls → Task 1.
- §10 Success criteria: Refresh populates data (Task 7), Add & Track works (Task 8), Remove works (Task 9), invalid API key modal (Task 7 helper).

**Placeholder scan:** no TBDs, TODOs, or "similar to".

**Type consistency:**
- `ShipsGoClient` constructor signature unchanged from Phase 1 Task 5 — used in `_ensure_client`.
- `RefreshRunnable(client, db)` and `AddTrackRunnable(client, container, scac)` — signatures match between Task 6 tests and Tasks 7, 8 call sites.
- `extract_fields(dict) -> dict` unchanged from Phase 1 — used in runnables.
- `save_tracking_data(dict)` / `load_tracking_data() -> dict` unchanged from Phase 1 — used throughout.
- `write_tracking_report(Path, dict) -> int` — used in Task 7 with the signature from Phase 1 Task 7.

**Polish deferrals:** any visual issues encountered go to `docs/superpowers/polish-backlog.md`, section "Phase 5 deferred polish." Do not fix polish inline.
