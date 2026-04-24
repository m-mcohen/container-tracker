# Phase 6 — Update Check + Banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** On every launch, run `core.updates.check_for_update` in a background thread. If a newer release exists on GitHub, show the `UpdateBanner` (already built in Phase 3). × dismisses for the session only (no persistence). Clicking the banner body opens the release's `html_url` in the default browser via `webbrowser.open`. All failures (offline, 403, 404, malformed) log one line and fail silently — spec §6.

**Architecture:** A new `UpdateCheckRunnable` in `ui/runnables.py`. Dispatched by `MainWindow.showEvent` so the check kicks off just after the window paints (not blocking construction). Signal → slot → banner. Banner's existing `open_url_requested` + `dismissed` signals wire to MainWindow handlers.

**Tech Stack:** No new deps. Uses `core.updates.check_for_update` from Phase 1 and `UpdateBanner` from Phase 3.

**Spec:** [2026-04-23-pyside6-migration-design.md §6, §4.4](../specs/2026-04-23-pyside6-migration-design.md)

---

## Single checkpoint. Four tasks.

- **Task 1:** Add `UpdateCheckRunnable` + `UpdateCheckSignals` to `ui/runnables.py`. Extend `test_runnables.py`.
- **Task 2:** Wire MainWindow — dispatch runnable on `showEvent`; connect `update_available` signal → banner show; connect banner signals (dismiss, open_url_requested) to handlers.
- **Task 3:** Mocked-integration smoke test — patch `check_for_update` to return a fake `UpdateInfo`; verify banner becomes visible after dispatch.
- **Task 4:** Live-launch smoke test — real `check_for_update` runs against GitHub; app launches, banner stays hidden (current version matches latest release), clean exit.

**Standing conventions:** `mypy --strict container_tracker` clean. One commit per task. Polish deferrals → `docs/superpowers/polish-backlog.md` under "Phase 6 deferred polish."

---

## Task 1: `UpdateCheckRunnable` in `runnables.py`

**Files:**
- Modify: `container_tracker/ui/runnables.py`
- Modify: `tests/test_runnables.py`

- [ ] **Step 1: Append failing tests**

```python
from container_tracker.core.updates import UpdateInfo
from container_tracker.ui.runnables import UpdateCheckRunnable


class TestUpdateCheckRunnable:
    def test_newer_release_emits_update_available(self, qapp, monkeypatch) -> None:
        fake = UpdateInfo(version="1.2.0", html_url="https://github.com/m-mcohen/container-tracker/releases/v1.2.0")
        monkeypatch.setattr(
            "container_tracker.ui.runnables.check_for_update",
            lambda current_version, timeout=5.0: fake,
        )
        runnable = UpdateCheckRunnable(current_version="1.1.0")
        received: list[UpdateInfo] = []
        runnable.signals.update_available.connect(received.append)
        runnable.run()
        assert received == [fake]

    def test_no_update_emits_nothing(self, qapp, monkeypatch) -> None:
        monkeypatch.setattr(
            "container_tracker.ui.runnables.check_for_update",
            lambda current_version, timeout=5.0: None,
        )
        runnable = UpdateCheckRunnable(current_version="1.1.0")
        received: list[UpdateInfo] = []
        runnable.signals.update_available.connect(received.append)
        runnable.run()
        assert received == []

    def test_exception_fails_silently(self, qapp, monkeypatch) -> None:
        def boom(current_version: str, timeout: float = 5.0) -> None:
            raise RuntimeError("network dead")
        monkeypatch.setattr("container_tracker.ui.runnables.check_for_update", boom)
        runnable = UpdateCheckRunnable(current_version="1.1.0")
        received: list[UpdateInfo] = []
        runnable.signals.update_available.connect(received.append)
        # Must NOT raise; must NOT emit.
        runnable.run()
        assert received == []
```

- [ ] **Step 2: Run tests, confirm fail**

Expected: `ImportError` on `UpdateCheckRunnable`.

- [ ] **Step 3: Append to `container_tracker/ui/runnables.py`**

```python
from container_tracker.core.updates import UpdateInfo, check_for_update


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
```

- [ ] **Step 4: Run tests + mypy + commit**

```bash
git add container_tracker/ui/runnables.py tests/test_runnables.py
git commit -m "ui: add UpdateCheckRunnable wrapping core.updates.check_for_update"
```

---

## Task 2: Wire MainWindow — dispatch on showEvent, banner wiring

**Files:**
- Modify: `container_tracker/ui/main_window.py`

- [ ] **Step 1: Connect banner signals in `_build_layout`**

After `self._banner = UpdateBanner()`, add:

```python
self._banner.dismissed.connect(self._on_banner_dismissed)
self._banner.open_url_requested.connect(self._on_banner_open_url)
self._update_check_dispatched = False  # prevents re-dispatch on repeated showEvents
```

- [ ] **Step 2: Override `showEvent` to dispatch the update check once**

Locate the existing `showEvent` method and change to:

```python
def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
    logger.info("MainWindow shown")
    super().showEvent(event)
    if not self._update_check_dispatched:
        self._update_check_dispatched = True
        self._dispatch_update_check()
```

- [ ] **Step 3: Implement `_dispatch_update_check` + banner handlers**

```python
def _dispatch_update_check(self) -> None:
    from PySide6.QtCore import QThreadPool
    from container_tracker.__version__ import __version__
    from container_tracker.ui.runnables import UpdateCheckRunnable

    runnable = UpdateCheckRunnable(current_version=__version__)
    runnable.signals.update_available.connect(self._on_update_available)
    QThreadPool.globalInstance().start(runnable)

def _on_update_available(self, info) -> None:  # type: ignore[no-untyped-def]
    logger.info("Update available: v%s at %s", info.version, info.html_url)
    self._banner.show_update(info.version, info.html_url)

def _on_banner_dismissed(self) -> None:
    # Session-only dismissal — no config change.
    logger.info("Update banner dismissed for this session")

def _on_banner_open_url(self, url: str) -> None:
    import webbrowser
    logger.info("Opening release URL: %s", url)
    webbrowser.open(url)
```

- [ ] **Step 4: Add the `UpdateInfo` type import for the handler**

At the top of `main_window.py`, add (or verify):

```python
from container_tracker.core.updates import UpdateInfo
```

Update `_on_update_available` signature to use the type:

```python
def _on_update_available(self, info: UpdateInfo) -> None:
    ...
```

(Strip the `# type: ignore[no-untyped-def]` comment on that method.)

- [ ] **Step 5: Run tests + mypy + commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: dispatch update check on showEvent; wire banner show + dismiss + open-url"
```

---

## Task 3: Mocked-integration smoke test

**Files:** none modified.

- [ ] **Step 1: Verify banner shows when check returns a fake UpdateInfo**

```bash
python -c "
import sys
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from container_tracker.core.updates import UpdateInfo
from container_tracker.ui.main_window import MainWindow
from container_tracker.ui.widgets import QtLogHandler

app = QApplication.instance() or QApplication(sys.argv)
handler = QtLogHandler()

fake = UpdateInfo(version='1.2.0', html_url='https://github.com/m-mcohen/container-tracker/releases/v1.2.0')

with patch('container_tracker.ui.runnables.check_for_update', return_value=fake):
    mw = MainWindow({'company_name': 'Test', 'contact_email': '', 'excel_path': '', 'dark_mode': False, 'dismissed': []}, handler)
    mw.show()
    # Process events for up to 3 seconds to let the QRunnable complete and the signal deliver.
    QTimer.singleShot(3000, app.quit)
    app.exec()

# After exec returns, inspect banner state.
print('banner shown?', mw._banner.is_shown())
print('banner message:', mw._banner.message_text())
assert mw._banner.is_shown() is True
assert '1.2.0' in mw._banner.message_text()
print('PASS: banner appears when check returns a newer version')
"
```

Expected: `PASS: banner appears when check returns a newer version`.

---

## Task 4: Live smoke test (real GitHub API)

**Files:** none modified.

- [ ] **Step 1: Launch the app, verify no banner appears when current==latest release**

```powershell
# Standard retry-loop pattern with MODULE = "container_tracker"
```

At time of writing, the latest GitHub release is `v1.0.0`. The current `__version__` is `1.1.0`. `check_for_update("1.1.0")` returns None because `1.1.0 > 1.0.0`. Banner stays hidden. App launches normally; exit cleanly.

Expected: handle non-zero, title correct, exit 0. No banner visible in the window. Log file contains a line like `update check: HTTP 200` or similar from `core.updates`.

- [ ] **Step 2: Full test suite + mypy one more time**

```bash
pytest -v && mypy --strict container_tracker
```

Expected: all pass, mypy clean.

- [ ] **Step 3: No commit** — verification only.

---

## PHASE 6 COMPLETE

Report format:

- Commits (expect 2: Task 1 + Task 2)
- pytest count (expect 216: 213 + 3 update-check tests)
- mypy source files (still 19)
- Mocked-integration test PASS line
- Live smoke test result (handle, title, exit, banner hidden)
- `git log --oneline -10`

---

## Self-Review

**Spec coverage §6:**
- "On launch, GET releases/latest with 5s timeout in background thread" → Task 1 (`timeout=5.0` default) + Task 2 (dispatched via QThreadPool, not the UI thread).
- "Compare tag_name (strip leading v) against embedded __version__" → Phase 1 core.updates does this; UpdateCheckRunnable just wraps it.
- "Show non-blocking banner at top of main window" → Task 2 (`self._banner.show_update`).
- "Clicking opens html_url in default browser via webbrowser.open" → Task 2 (`_on_banner_open_url`).
- "× dismisses banner for the session" → banner widget already handles hide; Task 2 adds the log line.
- "All failures log one line and fail silently" → Phase 1 core.updates handles this; UpdateCheckRunnable adds belt-and-suspenders try/except.

**Placeholder scan:** clean.
**Type consistency:** `UpdateInfo` dataclass from `core/updates.py` — signature `(version: str, html_url: str)` — unchanged. Used in `UpdateCheckSignals.update_available` emission + MainWindow handler.
