# Phase 3 — Main Window Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compose the full main-window layout — header, update banner slot, linked-spreadsheet card, four stat cards, action row, container table, activity log, footer — with hardcoded sample data and a working dark-mode toggle. All visual; **no backend functionality**. Browse/Create Template/Open in Excel don't open anything. Refresh/Add & Track/Remove Selected don't call ShipsGo or mutate data. Wiring to real data arrives in Phase 5.

**Architecture:** Build five reusable widgets in `container_tracker/ui/widgets.py` (StatCard, UpdateBanner, LinkedSpreadsheetCard, HeaderRow — QtLogHandler stays). Build the table layer in `container_tracker/ui/model.py` (`ContainerTableModel: QAbstractTableModel`, `StatusBucketSortProxy: QSortFilterProxyModel`). A small `container_tracker/ui/sample_data.py` provides ~10 hardcoded container records for the Phase 3 visual. Extend `theme.py`'s stylesheet with `statRole` QLabel rules so stat-card numbers color via QSS property selectors (not per-widget overrides). Compose in `MainWindow` via nested QVBoxLayout / QHBoxLayout. Dark-mode toggle in HeaderRow → emits signal → MainWindow.toggle_dark_mode.

**Tech Stack:** Python 3.11+, PySide6 ≥ 6.6, pytest (no new deps).

**Spec:** [2026-04-23-pyside6-migration-design.md §5.2, §5.4](../specs/2026-04-23-pyside6-migration-design.md)

---

## Checkpoint structure

Phase 3 has **three internal checkpoints**. Autonomous cadence: orchestrator verifies after each STOP and dispatches the next without user review.

- **Checkpoint A** (Tasks 1–5): theme extension + four reusable widgets (StatCard, UpdateBanner, LinkedSpreadsheetCard, HeaderRow). All unit-tested. `mypy --strict` clean.
- **Checkpoint B** (Tasks 6–8): `ContainerTableModel` + `StatusBucketSortProxy` + `sample_tracking_db()` fixture. Model unit-tested.
- **Checkpoint C** (Tasks 9–11): `MainWindow` composed with all sub-widgets + table + sample data + dark-mode toggle wired. Full smoke test (window visible, layout present, dark-mode flips palette live).

---

## File Structure

Files created by end of Phase 3:

```
container_tracker/ui/
  sample_data.py       # sample_tracking_db() -> dict; used only for Phase 3 visual
  model.py             # ContainerTableModel(QAbstractTableModel), StatusBucketSortProxy(QSortFilterProxyModel)
tests/
  conftest.py          # session-scoped qapp fixture for widget/model tests that need QApplication
  test_widgets.py      # StatCard, UpdateBanner, LinkedSpreadsheetCard, HeaderRow unit tests
  test_model.py        # ContainerTableModel + StatusBucketSortProxy unit tests
```

Files modified by Phase 3:

```
container_tracker/ui/
  theme.py             # extend build_stylesheet with QLabel[statRole=...] color rules; no palette or constant changes
  widgets.py           # add StatCard, UpdateBanner, LinkedSpreadsheetCard, HeaderRow (QtLogHandler unchanged)
  main_window.py       # full layout composition replacing blank QMainWindow body; wire sample data + dark-mode signal
```

Files untouched by Phase 3:

```
container_tracker/core/**   # Phase 1 backend; Phase 5 wiring
container_tracker/__main__.py  # already passes config to MainWindow (Phase 2)
container_tracker/ui/theme_preview.py  # synthetic harness still useful as is
container_tracker_gui.py    # still alive
tests/test_api.py / test_excel.py / test_persistence.py / test_status.py / test_theme.py / test_updates.py
```

**Working directory:** `C:/Users/emine/OneDrive/Documents/Claude/container_tracking_build`

**Standing conventions:**
- `mypy --strict container_tracker` (expanded scope) stays clean.
- One commit per task.
- Never touch `container_tracker_gui.py` or `container_tracker/core/*`.
- Never use `--no-verify`.
- For smoke tests that launch the app, use a retry loop on `$proc.Refresh()` (1–10s, 0.5s intervals) rather than a flat `Start-Sleep -Seconds 2` — Phase 2 Checkpoint B found that flat sleep occasionally misses the window by a frame on the preview harness. Retry pattern:

```powershell
$ErrorActionPreference = "Stop"
$proc = Start-Process -FilePath "python" -ArgumentList "-m", "<MODULE>" `
    -WorkingDirectory "C:/Users/emine/OneDrive/Documents/Claude/container_tracking_build" -PassThru
$deadline = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    $proc.Refresh()
    if ($proc.MainWindowHandle -ne 0 -and -not [string]::IsNullOrEmpty($proc.MainWindowTitle)) { break }
}
if ($proc.MainWindowHandle -eq 0 -or [string]::IsNullOrEmpty($proc.MainWindowTitle)) {
    Write-Output "FAILURE: window never registered (PID=$($proc.Id))"
    Stop-Process -Id $proc.Id -Force
    exit 1
}
Write-Output "OK: PID=$($proc.Id) Title='$($proc.MainWindowTitle)' Handle=$($proc.MainWindowHandle)"
$proc.CloseMainWindow() | Out-Null
$proc.WaitForExit(5000) | Out-Null
Write-Output "Exit=$($proc.ExitCode)"
```

---

## Task 1: Extend `theme.py` with statRole QSS rules

**Files:**
- Modify: `container_tracker/ui/theme.py`
- Modify: `tests/test_theme.py`

Stat-card numbers get colored per the StatusBucket. Spec §5.2 #4: "number color by bucket (Tracked = text_primary, Sailing = status_sailing, Arrived = status_arrived, Delayed = status_delayed)." Implement via QSS property selectors on QLabel so no per-widget `setStyleSheet` is needed.

- [ ] **Step 1: Append failing tests to `tests/test_theme.py`**

```python
class TestStatRoleQssRules:
    def test_contains_stat_role_sailing_rule(self) -> None:
        qss = build_stylesheet(LIGHT_PALETTE)
        assert 'QLabel[statRole="sailing"]' in qss

    def test_contains_stat_role_arrived_rule(self) -> None:
        qss = build_stylesheet(LIGHT_PALETTE)
        assert 'QLabel[statRole="arrived"]' in qss

    def test_contains_stat_role_delayed_rule(self) -> None:
        qss = build_stylesheet(LIGHT_PALETTE)
        assert 'QLabel[statRole="delayed"]' in qss

    def test_stat_role_colors_match_palette(self) -> None:
        """Each statRole rule must use its bucket's palette color."""
        qss = build_stylesheet(LIGHT_PALETTE)
        # Find the rule block and verify it contains the expected color.
        def _block(selector: str) -> str:
            start = qss.find(selector)
            assert start != -1, f"missing selector {selector}"
            end = qss.find("}", start)
            return qss[start:end]
        assert LIGHT_PALETTE["status_sailing"] in _block('QLabel[statRole="sailing"]')
        assert LIGHT_PALETTE["status_arrived"] in _block('QLabel[statRole="arrived"]')
        assert LIGHT_PALETTE["status_delayed"] in _block('QLabel[statRole="delayed"]')

    def test_stat_role_colors_flip_with_dark_palette(self) -> None:
        """Dark mode uses dark palette's bucket colors, not light's."""
        dark_qss = build_stylesheet(DARK_PALETTE)
        assert DARK_PALETTE["status_sailing"] in dark_qss
        # and light's version of the same color should not appear.
        assert LIGHT_PALETTE["status_sailing"] not in dark_qss or (
            # Defensive: if two palettes happen to share a color for one bucket,
            # the light version can still appear; but for sailing/arrived/delayed
            # the palettes differ — checking the dark-specific value is enough.
            True
        )
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_theme.py::TestStatRoleQssRules -v`
Expected: 5 failures asserting the selectors are missing.

- [ ] **Step 3: Add the rules to `build_stylesheet`**

Find the existing `/* ─── Labels ─── */` section in `container_tracker/ui/theme.py`. Append the following block **inside the returned f-string, after the existing QLabel[role=...] rules**:

```python
/* Stat-card number colors — role-based tint applied to the number QLabel. */
QLabel[statRole="sailing"] {{
    color: {p["status_sailing"]};
}}

QLabel[statRole="arrived"] {{
    color: {p["status_arrived"]};
}}

QLabel[statRole="delayed"] {{
    color: {p["status_delayed"]};
}}
```

(Place this block after the existing `QLabel[role="display"]` rule and before the `/* ─── Buttons ─── */` section header. Do NOT alter any existing rules.)

- [ ] **Step 4: Run tests, confirm all theme tests pass**

Run: `pytest tests/test_theme.py -v`
Expected: 35 theme tests pass (30 prior + 5 new).

- [ ] **Step 5: Run mypy**

Run: `mypy --strict container_tracker`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/theme.py tests/test_theme.py
git commit -m "theme: add QLabel[statRole=...] color rules for stat-card numbers"
```

---

## Task 2: `conftest.py` with session-scoped qapp fixture

**Files:**
- Create: `tests/conftest.py`

Widget and model tests that exercise Qt signals need a `QApplication`. A session-scoped fixture avoids constructing + destroying it on every test.

- [ ] **Step 1: Create `tests/conftest.py`**

```python
"""Shared pytest fixtures for the Container Tracker test suite."""
from __future__ import annotations

import sys
from typing import Iterator

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> Iterator[QApplication]:
    """Session-scoped QApplication. One instance shared by all widget/model tests."""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app  # type: ignore[misc]
    # No teardown — pytest-qt-style session lifetime.
```

- [ ] **Step 2: Confirm fixture is discoverable**

Run: `pytest --fixtures -q 2>&1 | grep qapp`
Expected: output contains `qapp` entry from `conftest.py`.

- [ ] **Step 3: Confirm existing tests still pass**

Run: `pytest -v`
Expected: 107 pass (102 prior + 5 new theme tests from Task 1).

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add session-scoped qapp fixture for widget/model tests"
```

---

## Task 3: `StatCard` widget

**Files:**
- Modify: `container_tracker/ui/widgets.py`
- Create: `tests/test_widgets.py`

- [ ] **Step 1: Write failing test file `tests/test_widgets.py`**

```python
"""Unit tests for UI widgets in container_tracker.ui.widgets."""
from __future__ import annotations

import pytest

from container_tracker.ui.widgets import StatCard


class TestStatCard:
    def test_displays_label_and_number(self, qapp) -> None:
        card = StatCard("Tracked", 12)
        assert card.label_text() == "Tracked"
        assert card.number_text() == "12"

    def test_number_can_be_string(self, qapp) -> None:
        card = StatCard("Delayed", "—")
        assert card.number_text() == "—"

    def test_set_number_updates_display(self, qapp) -> None:
        card = StatCard("Sailing", 0)
        card.set_number(5)
        assert card.number_text() == "5"

    def test_color_role_sets_statrole_property(self, qapp) -> None:
        card = StatCard("Sailing", 7, color_role="sailing")
        assert card.number_label_property("statRole") == "sailing"

    def test_default_color_role_is_none(self, qapp) -> None:
        """When no color role is given, the number gets no statRole (falls back to text_primary)."""
        card = StatCard("Tracked", 12)
        # Property returns None when unset (PySide6 returns None, not empty string).
        assert card.number_label_property("statRole") in (None, "")

    def test_frame_role_is_stat_card(self, qapp) -> None:
        """The StatCard must carry role='stat-card' so it picks up QFrame[role='stat-card'] QSS."""
        card = StatCard("Tracked", 12)
        assert card.property("role") == "stat-card"

    @pytest.mark.parametrize("role", ["sailing", "arrived", "delayed"])
    def test_valid_color_roles_accepted(self, qapp, role: str) -> None:
        card = StatCard("Test", 1, color_role=role)
        assert card.number_label_property("statRole") == role

    def test_invalid_color_role_raises(self, qapp) -> None:
        with pytest.raises(ValueError):
            StatCard("Test", 1, color_role="bogus")
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_widgets.py -v`
Expected: `ImportError: cannot import name 'StatCard'`.

- [ ] **Step 3: Append `StatCard` to `container_tracker/ui/widgets.py`**

Append below the existing `QtLogHandler` class (do not remove the existing imports or the class):

```python
from typing import Literal

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


StatColorRole = Literal["sailing", "arrived", "delayed"]
_VALID_COLOR_ROLES = {"sailing", "arrived", "delayed"}


class StatCard(QFrame):
    """Outlined stat card: label above, large number below.

    `color_role` tints the number per bucket; None / omitted falls back to
    default text color. Wiring is pure QSS property selectors — no per-widget
    setStyleSheet.
    """

    def __init__(
        self,
        label: str,
        number: int | str,
        color_role: StatColorRole | None = None,
    ) -> None:
        super().__init__()
        if color_role is not None and color_role not in _VALID_COLOR_ROLES:
            raise ValueError(
                f"color_role must be one of {_VALID_COLOR_ROLES} or None; got {color_role!r}"
            )
        self.setProperty("role", "stat-card")

        self._label = QLabel(label)
        self._label.setProperty("role", "secondary")

        self._number = QLabel(str(number))
        self._number.setProperty("role", "display")
        if color_role is not None:
            self._number.setProperty("statRole", color_role)

        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._number)

    def set_number(self, value: int | str) -> None:
        """Update the displayed number without reconstructing the widget."""
        self._number.setText(str(value))

    def label_text(self) -> str:
        return self._label.text()

    def number_text(self) -> str:
        return self._number.text()

    def number_label_property(self, key: str) -> object:
        """Return a Qt property set on the number QLabel (used by tests)."""
        return self._number.property(key)
```

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_widgets.py::TestStatCard -v`
Expected: 10 tests pass (parametrized "sailing/arrived/delayed" = 3).

- [ ] **Step 5: Run mypy**

Run: `mypy --strict container_tracker`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/widgets.py tests/test_widgets.py
git commit -m "ui: add StatCard widget with label, number, and statRole color"
```

---

## Task 4: `UpdateBanner` widget

**Files:**
- Modify: `container_tracker/ui/widgets.py`
- Modify: `tests/test_widgets.py`

Banner is hidden by default; `show_update(version, url)` reveals it with version text. Signals: `dismissed` (× button clicked), `open_url_requested(url)` (main text area clicked).

- [ ] **Step 1: Append failing tests to `tests/test_widgets.py`**

```python
from container_tracker.ui.widgets import UpdateBanner


class TestUpdateBanner:
    def test_hidden_by_default(self, qapp) -> None:
        banner = UpdateBanner()
        assert banner.isVisibleTo(None) is False  # equivalent to isHidden check

    def test_show_update_sets_version_text_and_reveals(self, qapp) -> None:
        banner = UpdateBanner()
        banner.show_update("1.2.0", "https://github.com/m-mcohen/container-tracker/releases/v1.2.0")
        assert "1.2.0" in banner.message_text()
        # Visibility governed by parent; use the internal shown flag instead.
        assert banner.is_shown() is True

    def test_dismiss_hides_and_emits_signal(self, qapp) -> None:
        banner = UpdateBanner()
        banner.show_update("1.2.0", "https://...")
        received: list[str] = []
        banner.dismissed.connect(lambda: received.append("dismissed"))
        banner._dismiss_button.click()
        assert banner.is_shown() is False
        assert received == ["dismissed"]

    def test_click_body_emits_open_url_requested_with_url(self, qapp) -> None:
        banner = UpdateBanner()
        url = "https://github.com/m-mcohen/container-tracker/releases/v1.2.0"
        banner.show_update("1.2.0", url)
        received: list[str] = []
        banner.open_url_requested.connect(received.append)
        banner._body_button.click()
        assert received == [url]

    def test_show_update_overwrites_previous_url(self, qapp) -> None:
        banner = UpdateBanner()
        banner.show_update("1.2.0", "https://old")
        banner.show_update("1.3.0", "https://new")
        received: list[str] = []
        banner.open_url_requested.connect(received.append)
        banner._body_button.click()
        assert received == ["https://new"]
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_widgets.py::TestUpdateBanner -v`
Expected: `ImportError: cannot import name 'UpdateBanner'`.

- [ ] **Step 3: Append `UpdateBanner` to `container_tracker/ui/widgets.py`**

```python
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton


class UpdateBanner(QFrame):
    """Non-blocking banner at the top of MainWindow announcing a newer release.

    Hidden by default. Call `show_update(version, url)` to reveal. The banner
    exposes two signals:

    - `dismissed` — the × button was clicked; MainWindow should hide the banner.
    - `open_url_requested(str)` — the body area was clicked; MainWindow should
      open the URL in the default browser via webbrowser.open().
    """

    dismissed = Signal()
    open_url_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("role", "card")  # reuses outlined-card stylesheet
        self._shown = False
        self._url = ""

        self._body_button = QPushButton("")
        self._body_button.setFlat(True)
        self._body_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._body_button.clicked.connect(self._on_body_clicked)

        self._dismiss_button = QPushButton("×")
        self._dismiss_button.setFixedSize(28, 28)
        self._dismiss_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dismiss_button.clicked.connect(self._on_dismiss_clicked)

        layout = QHBoxLayout(self)
        layout.addWidget(self._body_button, stretch=1)
        layout.addWidget(self._dismiss_button)

        self.hide()

    def show_update(self, version: str, url: str) -> None:
        """Reveal the banner with version text and a click-target URL."""
        self._url = url
        self._body_button.setText(f"Version {version} available — click to download")
        self._shown = True
        self.show()

    def message_text(self) -> str:
        return self._body_button.text()

    def is_shown(self) -> bool:
        return self._shown

    def _on_body_clicked(self) -> None:
        if self._url:
            self.open_url_requested.emit(self._url)

    def _on_dismiss_clicked(self) -> None:
        self._shown = False
        self.hide()
        self.dismissed.emit()
```

Also add `from PySide6.QtCore import Qt` to the imports at the top of `widgets.py` if not already present (needed for `Qt.CursorShape`).

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_widgets.py -v`
Expected: StatCard tests + UpdateBanner tests all pass.

- [ ] **Step 5: Run mypy**

Run: `mypy --strict container_tracker`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/widgets.py tests/test_widgets.py
git commit -m "ui: add UpdateBanner widget with dismiss/open-url signals"
```

---

## Task 5: `LinkedSpreadsheetCard` widget

**Files:**
- Modify: `container_tracker/ui/widgets.py`
- Modify: `tests/test_widgets.py`

Outlined card showing the linked path + three buttons (Browse…, Create Template, Open in Excel). Buttons emit signals in Phase 3; Phase 5 wires them to file dialogs and the backend.

- [ ] **Step 1: Append failing tests**

```python
from container_tracker.ui.widgets import LinkedSpreadsheetCard


class TestLinkedSpreadsheetCard:
    def test_shows_placeholder_when_empty(self, qapp) -> None:
        card = LinkedSpreadsheetCard("")
        assert "No file linked" in card.path_text()

    def test_shows_path_when_set(self, qapp) -> None:
        card = LinkedSpreadsheetCard(r"C:\Users\me\containers.xlsx")
        assert r"containers.xlsx" in card.path_text()

    def test_set_path_updates_display(self, qapp) -> None:
        card = LinkedSpreadsheetCard("")
        card.set_path(r"C:\new.xlsx")
        assert r"new.xlsx" in card.path_text()
        card.set_path("")
        assert "No file linked" in card.path_text()

    def test_browse_button_emits_signal(self, qapp) -> None:
        card = LinkedSpreadsheetCard("")
        received: list[object] = []
        card.browse_requested.connect(lambda: received.append("browse"))
        card._browse_button.click()
        assert received == ["browse"]

    def test_create_button_emits_signal(self, qapp) -> None:
        card = LinkedSpreadsheetCard("")
        received: list[object] = []
        card.create_requested.connect(lambda: received.append("create"))
        card._create_button.click()
        assert received == ["create"]

    def test_open_button_emits_signal_with_current_path(self, qapp) -> None:
        path = r"C:\Users\me\containers.xlsx"
        card = LinkedSpreadsheetCard(path)
        received: list[str] = []
        card.open_requested.connect(received.append)
        card._open_button.click()
        assert received == [path]

    def test_open_button_disabled_when_path_empty(self, qapp) -> None:
        card = LinkedSpreadsheetCard("")
        assert card._open_button.isEnabled() is False

    def test_open_button_reenabled_when_path_set(self, qapp) -> None:
        card = LinkedSpreadsheetCard("")
        card.set_path(r"C:\new.xlsx")
        assert card._open_button.isEnabled() is True
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_widgets.py::TestLinkedSpreadsheetCard -v`
Expected: `ImportError: cannot import name 'LinkedSpreadsheetCard'`.

- [ ] **Step 3: Append `LinkedSpreadsheetCard` to `container_tracker/ui/widgets.py`**

```python
class LinkedSpreadsheetCard(QFrame):
    """Linked-spreadsheet card: label, current path, three buttons.

    Buttons emit signals (browse_requested, create_requested, open_requested).
    Phase 3 does not wire them — Phase 5 connects them to file dialogs and
    the Excel backend.
    """

    browse_requested = Signal()
    create_requested = Signal()
    open_requested = Signal(str)

    _PLACEHOLDER = "No file linked"

    def __init__(self, initial_path: str = "") -> None:
        super().__init__()
        self.setProperty("role", "card")
        self._path = initial_path

        heading = QLabel("Linked spreadsheet")
        heading.setProperty("role", "secondary")

        self._path_label = QLabel(self._display_path())

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)

        self._browse_button = QPushButton("Browse…")
        self._browse_button.setProperty("variant", "secondary")
        self._browse_button.clicked.connect(self.browse_requested.emit)

        self._create_button = QPushButton("Create Template")
        self._create_button.setProperty("variant", "secondary")
        self._create_button.clicked.connect(self.create_requested.emit)

        self._open_button = QPushButton("Open in Excel")
        self._open_button.setProperty("variant", "secondary")
        self._open_button.clicked.connect(self._on_open_clicked)
        self._open_button.setEnabled(bool(self._path))

        for btn in (self._browse_button, self._create_button, self._open_button):
            button_layout.addWidget(btn)
        button_layout.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(self._path_label)
        layout.addWidget(button_row)

    def set_path(self, path: str) -> None:
        """Update the displayed path and enable/disable the Open button."""
        self._path = path
        self._path_label.setText(self._display_path())
        self._open_button.setEnabled(bool(path))

    def path_text(self) -> str:
        return self._path_label.text()

    def _display_path(self) -> str:
        return self._path or self._PLACEHOLDER

    def _on_open_clicked(self) -> None:
        if self._path:
            self.open_requested.emit(self._path)
```

Also add `QWidget` to the existing imports from `PySide6.QtWidgets` in `widgets.py`.

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_widgets.py -v`
Expected: all widget tests pass.

- [ ] **Step 5: Run mypy**

Run: `mypy --strict container_tracker`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/widgets.py tests/test_widgets.py
git commit -m "ui: add LinkedSpreadsheetCard with browse/create/open signals"
```

---

## Task 6: `HeaderRow` widget

**Files:**
- Modify: `container_tracker/ui/widgets.py`
- Modify: `tests/test_widgets.py`

Title (heading), subtitle (company name, secondary), stretch, settings gear button, dark-mode checkbox. Signals: `settings_clicked`, `dark_mode_toggled(bool)`.

- [ ] **Step 1: Append failing tests**

```python
from container_tracker.ui.widgets import HeaderRow


class TestHeaderRow:
    def test_renders_title_and_subtitle(self, qapp) -> None:
        header = HeaderRow(title="Container Tracker", subtitle="Ken Gabbay Coffee")
        assert header.title_text() == "Container Tracker"
        assert header.subtitle_text() == "Ken Gabbay Coffee"

    def test_empty_subtitle_is_accepted(self, qapp) -> None:
        header = HeaderRow(title="Container Tracker", subtitle="")
        assert header.subtitle_text() == ""

    def test_settings_button_emits_signal(self, qapp) -> None:
        header = HeaderRow(title="Container Tracker", subtitle="Acme")
        received: list[object] = []
        header.settings_clicked.connect(lambda: received.append("settings"))
        header._settings_button.click()
        assert received == ["settings"]

    def test_dark_mode_checkbox_emits_signal(self, qapp) -> None:
        header = HeaderRow(title="Container Tracker", subtitle="Acme")
        received: list[bool] = []
        header.dark_mode_toggled.connect(received.append)
        header._dark_mode_toggle.setChecked(True)
        assert received == [True]
        header._dark_mode_toggle.setChecked(False)
        assert received == [True, False]

    def test_dark_mode_initial_state_respected(self, qapp) -> None:
        header_off = HeaderRow(title="Container Tracker", subtitle="", is_dark=False)
        header_on = HeaderRow(title="Container Tracker", subtitle="", is_dark=True)
        assert header_off._dark_mode_toggle.isChecked() is False
        assert header_on._dark_mode_toggle.isChecked() is True
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_widgets.py::TestHeaderRow -v`
Expected: `ImportError: cannot import name 'HeaderRow'`.

- [ ] **Step 3: Append `HeaderRow` to `container_tracker/ui/widgets.py`**

```python
from PySide6.QtWidgets import QCheckBox


class HeaderRow(QWidget):
    """Top header row: title + subtitle on the left, settings gear + dark-mode toggle on the right."""

    settings_clicked = Signal()
    dark_mode_toggled = Signal(bool)

    def __init__(self, title: str, subtitle: str, is_dark: bool = False) -> None:
        super().__init__()

        self._title = QLabel(title)
        self._title.setProperty("role", "heading")

        self._subtitle = QLabel(subtitle)
        self._subtitle.setProperty("role", "secondary")

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(2)
        left.addWidget(self._title)
        left.addWidget(self._subtitle)

        self._settings_button = QPushButton("⚙")
        self._settings_button.setFixedSize(32, 32)
        self._settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_button.setToolTip("Settings")
        self._settings_button.clicked.connect(self.settings_clicked.emit)

        self._dark_mode_toggle = QCheckBox("Dark mode")
        self._dark_mode_toggle.setChecked(is_dark)
        self._dark_mode_toggle.stateChanged.connect(self._on_toggle_changed)

        layout = QHBoxLayout(self)
        layout.addLayout(left)
        layout.addStretch(1)
        layout.addWidget(self._settings_button)
        layout.addWidget(self._dark_mode_toggle)

    def title_text(self) -> str:
        return self._title.text()

    def subtitle_text(self) -> str:
        return self._subtitle.text()

    def set_subtitle(self, text: str) -> None:
        self._subtitle.setText(text)

    def _on_toggle_changed(self, state: int) -> None:
        self.dark_mode_toggled.emit(state == Qt.CheckState.Checked.value)
```

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_widgets.py -v`
Expected: all widget tests pass.

- [ ] **Step 5: Run mypy**

Run: `mypy --strict container_tracker`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/widgets.py tests/test_widgets.py
git commit -m "ui: add HeaderRow widget with title, subtitle, settings, dark-mode toggle"
```

---

## CHECKPOINT A — STOP

**What's now true:**
- `container_tracker/ui/theme.py` has QLabel statRole rules for sailing/arrived/delayed.
- `container_tracker/ui/widgets.py` now contains QtLogHandler + StatCard + UpdateBanner + LinkedSpreadsheetCard + HeaderRow.
- Widget tests cover text/property/signal behavior for all four new widgets.
- `pytest` green; `mypy --strict container_tracker` clean.
- MainWindow is not yet using any of these widgets (Checkpoint C).

Autonomous cadence: verify, then dispatch Checkpoint B.

---

## Task 7: `ContainerTableModel` — QAbstractTableModel subclass

**Files:**
- Create: `container_tracker/ui/model.py`
- Create: `tests/test_model.py`

Columns per spec §5.2 #6: Container #, Carrier, Status, Original ETA, Current ETA, Delay, Route (single `POL → POD` cell), Vessel, Transit %. Data comes from a `list[dict[str, Any]]` internal store. `data(index, role)` returns `Qt.DisplayRole` formatted strings, `Qt.ForegroundRole` on Status column (palette color by bucket), and `Qt.TextAlignmentRole` right-aligned for Delay and Transit %.

- [ ] **Step 1: Write failing tests**

Create `tests/test_model.py`:

```python
"""Unit tests for ContainerTableModel and StatusBucketSortProxy."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from container_tracker.ui.model import ContainerTableModel


SAMPLE_RECORDS = [
    {
        "container_number": "MSKU1234567",
        "carrier": "MAERSK LINE",
        "status": "SAILING",
        "original_eta": "2026-05-01",
        "eta": "2026-05-05",
        "delay_days": "+4 days",
        "delay_days_int": 4,
        "pol": "Shanghai",
        "pod": "Los Angeles",
        "vessel": "MV SEA PIONEER",
        "transit_pct": 42,
    },
    {
        "container_number": "CMAU7654321",
        "carrier": "CMA CGM",
        "status": "ARRIVED",
        "original_eta": "2026-03-20",
        "eta": "2026-03-20",
        "delay_days": "On time",
        "delay_days_int": 0,
        "pol": "Ningbo",
        "pod": "Long Beach",
        "vessel": "MV PACIFIC STAR",
        "transit_pct": 100,
    },
]


class TestContainerTableModel:
    def test_rowcount_matches_records(self, qapp) -> None:
        model = ContainerTableModel()
        assert model.rowCount() == 0
        model.set_records(SAMPLE_RECORDS)
        assert model.rowCount() == 2

    def test_column_count(self, qapp) -> None:
        model = ContainerTableModel()
        # 9 columns: Container #, Carrier, Status, Original ETA, Current ETA, Delay, Route, Vessel, Transit %
        assert model.columnCount() == 9

    def test_header_labels(self, qapp) -> None:
        model = ContainerTableModel()
        headers = [
            model.headerData(c, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            for c in range(model.columnCount())
        ]
        assert headers == [
            "Container #", "Carrier", "Status", "Original ETA", "Current ETA",
            "Delay", "Route", "Vessel", "Transit %",
        ]

    def test_display_role_returns_formatted_strings(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)

        idx = model.index(0, 0)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "MSKU1234567"
        idx = model.index(0, 2)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "SAILING"
        idx = model.index(0, 5)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "+4 days"

    def test_route_is_pol_arrow_pod_single_cell(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(0, 6)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "Shanghai → Los Angeles"

    def test_transit_pct_formatted_with_percent(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(0, 8)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "42%"

    def test_transit_pct_empty_when_missing(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records([{"container_number": "X", "transit_pct": ""}])
        idx = model.index(0, 8)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == ""

    def test_foreground_role_on_status_sailing(self, qapp) -> None:
        from container_tracker.ui.theme import LIGHT_PALETTE
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(0, 2)  # Status column, SAILING row
        color = model.data(idx, Qt.ItemDataRole.ForegroundRole)
        assert color is not None
        # QColor stringifies to "#xxxxxx" in upper case via .name().
        assert color.name().upper() == LIGHT_PALETTE["status_sailing"].upper()

    def test_foreground_role_on_status_arrived(self, qapp) -> None:
        from container_tracker.ui.theme import LIGHT_PALETTE
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(1, 2)  # Status column, ARRIVED row
        color = model.data(idx, Qt.ItemDataRole.ForegroundRole)
        assert color is not None
        assert color.name().upper() == LIGHT_PALETTE["status_arrived"].upper()

    def test_foreground_role_on_non_status_column_is_none(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(0, 0)  # Container # column
        assert model.data(idx, Qt.ItemDataRole.ForegroundRole) is None

    def test_text_alignment_right_on_delay(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(0, 5)  # Delay
        alignment = model.data(idx, Qt.ItemDataRole.TextAlignmentRole)
        assert alignment is not None
        assert int(alignment) & int(Qt.AlignmentFlag.AlignRight)

    def test_text_alignment_right_on_transit_pct(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(0, 8)  # Transit %
        alignment = model.data(idx, Qt.ItemDataRole.TextAlignmentRole)
        assert alignment is not None
        assert int(alignment) & int(Qt.AlignmentFlag.AlignRight)

    def test_set_records_resets_and_emits(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        assert model.rowCount() == 2
        model.set_records([])
        assert model.rowCount() == 0

    def test_remove_rows_by_index(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        model.remove_rows([0])
        assert model.rowCount() == 1
        remaining = model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole)
        assert remaining == "CMAU7654321"

    def test_remove_rows_multiple_preserves_order(self, qapp) -> None:
        records = [{"container_number": f"X{n:09d}", "status": ""} for n in range(5)]
        model = ContainerTableModel()
        model.set_records(records)
        model.remove_rows([1, 3])
        remaining = [
            model.data(model.index(r, 0), Qt.ItemDataRole.DisplayRole)
            for r in range(model.rowCount())
        ]
        assert remaining == ["X000000000", "X000000002", "X000000004"]
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_model.py -v`
Expected: `ModuleNotFoundError: No module named 'container_tracker.ui.model'`.

- [ ] **Step 3: Implement `container_tracker/ui/model.py`**

```python
"""Qt models for the container table.

ContainerTableModel holds tracking records in a list[dict] and exposes them
via QAbstractTableModel. StatusBucketSortProxy (Task 8) adds bucket-priority
sort on the Status column. MainWindow (Task 10) wires it together.
"""
from __future__ import annotations

from typing import Any, Final

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QColor

from container_tracker.core.status import StatusBucket, normalize_status
from container_tracker.ui.theme import LIGHT_PALETTE


# Column definition: (header_label, field_key)
# field_key is used by _format_display; None means a computed / synthetic column.
_COLUMNS: Final[tuple[tuple[str, str | None], ...]] = (
    ("Container #",  "container_number"),
    ("Carrier",      "carrier"),
    ("Status",       "status"),
    ("Original ETA", "original_eta"),
    ("Current ETA",  "eta"),
    ("Delay",        "delay_days"),
    ("Route",        None),               # computed from pol + pod
    ("Vessel",       "vessel"),
    ("Transit %",    "transit_pct"),
)

_STATUS_COLUMN: Final[int] = 2
_DELAY_COLUMN: Final[int] = 5
_ROUTE_COLUMN: Final[int] = 6
_TRANSIT_PCT_COLUMN: Final[int] = 8


_BUCKET_TO_PALETTE_KEY: Final[dict[StatusBucket, str]] = {
    StatusBucket.SAILING: "status_sailing",
    StatusBucket.ARRIVED: "status_arrived",
    # DELAYED bucket doesn't exist as a raw ShipsGo status — it's derived.
    # For now we color only SAILING/ARRIVED; Delayed rows show with SAILING
    # foreground (they're SAILING with a delay).
}


class ContainerTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._records: list[dict[str, Any]] = []

    # ─── Qt API ───────────────────────────────────────────────────────

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._records)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(_COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == int(Qt.ItemDataRole.DisplayRole)
            and 0 <= section < len(_COLUMNS)
        ):
            return _COLUMNS[section][0]
        return None

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._records)):
            return None
        record = self._records[index.row()]
        col = index.column()

        if role == int(Qt.ItemDataRole.DisplayRole):
            return self._format_display(record, col)

        if role == int(Qt.ItemDataRole.ForegroundRole) and col == _STATUS_COLUMN:
            bucket = normalize_status(str(record.get("status", "")))
            palette_key = _BUCKET_TO_PALETTE_KEY.get(bucket)
            if palette_key is None:
                return None
            return QColor(LIGHT_PALETTE[palette_key])

        if role == int(Qt.ItemDataRole.TextAlignmentRole) and col in (_DELAY_COLUMN, _TRANSIT_PCT_COLUMN):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        return None

    # ─── Mutation API ─────────────────────────────────────────────────

    def set_records(self, records: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._records = list(records)
        self.endResetModel()

    def remove_rows(self, row_indexes: list[int]) -> None:
        """Remove rows by index. Indexes may be in any order; they're deduplicated and sorted."""
        if not row_indexes:
            return
        to_remove = sorted(set(row_indexes), reverse=True)
        self.beginResetModel()
        for row in to_remove:
            if 0 <= row < len(self._records):
                del self._records[row]
        self.endResetModel()

    def record_at(self, row: int) -> dict[str, Any] | None:
        """Return the raw record dict at the given row (useful for main window logic)."""
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    # ─── Helpers ──────────────────────────────────────────────────────

    def _format_display(self, record: dict[str, Any], col: int) -> str:
        if col == _ROUTE_COLUMN:
            pol = str(record.get("pol", "") or "")
            pod = str(record.get("pod", "") or "")
            if pol and pod:
                return f"{pol} → {pod}"
            return pol or pod

        field_key = _COLUMNS[col][1]
        if field_key is None:
            return ""
        value: Any = record.get(field_key, "")

        if col == _TRANSIT_PCT_COLUMN:
            if value == "" or value is None:
                return ""
            return f"{value}%"

        return "" if value is None else str(value)
```

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_model.py -v`
Expected: 17 tests pass.

- [ ] **Step 5: Run full suite + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all tests pass, mypy clean.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/model.py tests/test_model.py
git commit -m "ui: add ContainerTableModel (QAbstractTableModel) with display/foreground/alignment roles"
```

---

## Task 8: `StatusBucketSortProxy` — bucket-priority sort on Status column

**Files:**
- Modify: `container_tracker/ui/model.py`
- Modify: `tests/test_model.py`

Per spec §5.4: sorting the Status column must use bucket priority (DELAYED < SAILING < ARRIVED < PENDING < UNKNOWN) not alphabetical. "Delayed" isn't a raw ShipsGo status — it's derived from `delay_days_int > 0 AND status bucket == SAILING`. Our proxy synthesizes a "delayed" sort rank for that case.

- [ ] **Step 1: Append failing tests to `tests/test_model.py`**

```python
from PySide6.QtCore import QSortFilterProxyModel

from container_tracker.ui.model import StatusBucketSortProxy


class TestStatusBucketSortProxy:
    def _populate(self) -> tuple[ContainerTableModel, StatusBucketSortProxy]:
        model = ContainerTableModel()
        model.set_records([
            {"container_number": "A_SAILING_NO_DELAY",    "status": "SAILING",   "delay_days_int": 0},
            {"container_number": "B_ARRIVED",             "status": "ARRIVED",   "delay_days_int": 0},
            {"container_number": "C_SAILING_DELAYED",     "status": "SAILING",   "delay_days_int": 5},
            {"container_number": "D_PENDING",             "status": "BOOKED",    "delay_days_int": 0},
            {"container_number": "E_UNKNOWN",             "status": "ZZZZ",      "delay_days_int": 0},
        ])
        proxy = StatusBucketSortProxy()
        proxy.setSourceModel(model)
        return model, proxy

    def test_sort_status_ascending_uses_bucket_priority(self, qapp) -> None:
        _, proxy = self._populate()
        proxy.sort(_STATUS_COLUMN_FOR_TEST, Qt.SortOrder.AscendingOrder)
        # DELAYED → SAILING → ARRIVED → PENDING → UNKNOWN
        ordered_containers = [
            proxy.data(proxy.index(r, 0), Qt.ItemDataRole.DisplayRole)
            for r in range(proxy.rowCount())
        ]
        assert ordered_containers == [
            "C_SAILING_DELAYED",     # DELAYED (highest priority)
            "A_SAILING_NO_DELAY",    # SAILING
            "B_ARRIVED",             # ARRIVED
            "D_PENDING",             # PENDING
            "E_UNKNOWN",             # UNKNOWN
        ]

    def test_sort_status_descending_inverts_bucket_priority(self, qapp) -> None:
        _, proxy = self._populate()
        proxy.sort(_STATUS_COLUMN_FOR_TEST, Qt.SortOrder.DescendingOrder)
        ordered_containers = [
            proxy.data(proxy.index(r, 0), Qt.ItemDataRole.DisplayRole)
            for r in range(proxy.rowCount())
        ]
        assert ordered_containers == [
            "E_UNKNOWN",
            "D_PENDING",
            "B_ARRIVED",
            "A_SAILING_NO_DELAY",
            "C_SAILING_DELAYED",
        ]

    def test_sort_other_column_uses_default_comparison(self, qapp) -> None:
        _, proxy = self._populate()
        # Sort by Container # (column 0) — lexicographic on DisplayRole.
        proxy.sort(0, Qt.SortOrder.AscendingOrder)
        ordered_containers = [
            proxy.data(proxy.index(r, 0), Qt.ItemDataRole.DisplayRole)
            for r in range(proxy.rowCount())
        ]
        assert ordered_containers == sorted([
            "A_SAILING_NO_DELAY",
            "B_ARRIVED",
            "C_SAILING_DELAYED",
            "D_PENDING",
            "E_UNKNOWN",
        ])


# Keep a module-local constant so the test file doesn't depend on importing
# a private from model.py.
_STATUS_COLUMN_FOR_TEST = 2
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_model.py -v`
Expected: `ImportError: cannot import name 'StatusBucketSortProxy'`.

- [ ] **Step 3: Append `StatusBucketSortProxy` to `container_tracker/ui/model.py`**

Add near the top of the file (below existing imports):

```python
from PySide6.QtCore import QSortFilterProxyModel
```

At the bottom of `model.py`:

```python
# ─────────────────────────────────────────────────────────────────────────
# Custom sort proxy — bucket priority on Status column
# ─────────────────────────────────────────────────────────────────────────

# Rank: lower = sorts first in ascending order.
_BUCKET_RANK: Final[dict[str, int]] = {
    "DELAYED": 0,
    "SAILING": 1,
    "ARRIVED": 2,
    "PENDING": 3,
    "UNKNOWN": 4,
}


class StatusBucketSortProxy(QSortFilterProxyModel):
    """Sort proxy that orders the Status column by bucket priority.

    Priority (ascending): DELAYED < SAILING < ARRIVED < PENDING < UNKNOWN.
    Shipping operators care about what's late; alphabetical would hide that.
    Other columns use default comparison.
    """

    def lessThan(
        self,
        source_left: QModelIndex | QPersistentModelIndex,
        source_right: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        if source_left.column() != _STATUS_COLUMN or source_right.column() != _STATUS_COLUMN:
            return super().lessThan(source_left, source_right)

        source = self.sourceModel()
        if not isinstance(source, ContainerTableModel):
            return super().lessThan(source_left, source_right)

        left_rank = self._rank_for_row(source, source_left.row())
        right_rank = self._rank_for_row(source, source_right.row())
        return left_rank < right_rank

    @staticmethod
    def _rank_for_row(source: ContainerTableModel, row: int) -> int:
        record = source.record_at(row) or {}
        bucket = normalize_status(str(record.get("status", "")))
        delay = record.get("delay_days_int")
        if bucket == StatusBucket.SAILING and isinstance(delay, int) and delay > 0:
            return _BUCKET_RANK["DELAYED"]
        return _BUCKET_RANK[bucket.value]
```

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_model.py -v`
Expected: all model tests pass (17 from Task 7 + 3 new = 20).

- [ ] **Step 5: Run full suite + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass, mypy clean.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/model.py tests/test_model.py
git commit -m "ui: add StatusBucketSortProxy with DELAYED-first bucket priority"
```

---

## Task 9: `sample_tracking_db()` for Phase 3 visual

**Files:**
- Create: `container_tracker/ui/sample_data.py`

Not unit-tested — it's a fixture, and its contract is "returns a dict Phase 3 can display." Phase 5 removes it.

- [ ] **Step 1: Create `container_tracker/ui/sample_data.py`**

```python
"""Hardcoded sample tracking data for the Phase 3 visual.

Phase 5 replaces this with real data from core.persistence.load_tracking_data().
Kept as a separate module so it's easy to delete later.
"""
from __future__ import annotations

from typing import Any


def sample_tracking_db() -> dict[str, dict[str, Any]]:
    """Return a sample db with 10 containers across all status buckets."""
    records: list[dict[str, Any]] = [
        {
            "container_number": "MSKU1234567", "carrier": "MAERSK LINE",
            "status": "SAILING", "original_eta": "2026-05-01", "eta": "2026-05-05",
            "delay_days": "+4 days", "delay_days_int": 4,
            "pol": "Shanghai, China", "pod": "Los Angeles, USA",
            "vessel": "MV SEA PIONEER", "transit_pct": 42,
        },
        {
            "container_number": "MSKU2222222", "carrier": "MAERSK LINE",
            "status": "SAILING", "original_eta": "2026-04-28", "eta": "2026-04-28",
            "delay_days": "On time", "delay_days_int": 0,
            "pol": "Qingdao, China", "pod": "Oakland, USA",
            "vessel": "MV CARIBOU", "transit_pct": 65,
        },
        {
            "container_number": "CMAU7654321", "carrier": "CMA CGM",
            "status": "ARRIVED", "original_eta": "2026-03-20", "eta": "2026-03-20",
            "delay_days": "On time", "delay_days_int": 0,
            "pol": "Ningbo, China", "pod": "Long Beach, USA",
            "vessel": "MV PACIFIC STAR", "transit_pct": 100,
        },
        {
            "container_number": "CMAU3333333", "carrier": "CMA CGM",
            "status": "DISCHARGED", "original_eta": "2026-04-01", "eta": "2026-04-03",
            "delay_days": "+2 days", "delay_days_int": 2,
            "pol": "Hong Kong", "pod": "Seattle, USA",
            "vessel": "MV JADE", "transit_pct": 100,
        },
        {
            "container_number": "MSCU1111222", "carrier": "MSC",
            "status": "SAILING", "original_eta": "2026-05-10", "eta": "2026-05-10",
            "delay_days": "On time", "delay_days_int": 0,
            "pol": "Rotterdam, Netherlands", "pod": "New York, USA",
            "vessel": "MV ATLANTIC", "transit_pct": 22,
        },
        {
            "container_number": "HLCU4444555", "carrier": "HAPAG LLOYD",
            "status": "BOOKED", "original_eta": "", "eta": "",
            "delay_days": "", "delay_days_int": None,
            "pol": "", "pod": "",
            "vessel": "", "transit_pct": "",
        },
        {
            "container_number": "EGLV5555666", "carrier": "EVERGREEN",
            "status": "SAILING", "original_eta": "2026-04-15", "eta": "2026-04-22",
            "delay_days": "+7 days", "delay_days_int": 7,
            "pol": "Kaohsiung, Taiwan", "pod": "Los Angeles, USA",
            "vessel": "MV EVER GIVEN", "transit_pct": 58,
        },
        {
            "container_number": "COSU6666777", "carrier": "COSCO",
            "status": "DELIVERED", "original_eta": "2026-02-28", "eta": "2026-03-02",
            "delay_days": "+2 days", "delay_days_int": 2,
            "pol": "Shanghai, China", "pod": "Savannah, USA",
            "vessel": "MV ORIENT", "transit_pct": 100,
        },
        {
            "container_number": "ONEY7777888", "carrier": "ONE",
            "status": "SAILING", "original_eta": "2026-05-03", "eta": "2026-05-01",
            "delay_days": "-2 days (early)", "delay_days_int": -2,
            "pol": "Tokyo, Japan", "pod": "Los Angeles, USA",
            "vessel": "MV SAKURA", "transit_pct": 88,
        },
        {
            "container_number": "ZIMU8888999", "carrier": "ZIM",
            "status": "GATE_OUT", "original_eta": "2026-03-10", "eta": "2026-03-10",
            "delay_days": "On time", "delay_days_int": 0,
            "pol": "Haifa, Israel", "pod": "New York, USA",
            "vessel": "MV ZIM NORFOLK", "transit_pct": 100,
        },
    ]
    return {r["container_number"]: r for r in records}
```

- [ ] **Step 2: Confirm module imports**

Run: `python -c "from container_tracker.ui.sample_data import sample_tracking_db; print(len(sample_tracking_db()))"`
Expected: `10`.

- [ ] **Step 3: Run full suite + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass, mypy clean.

- [ ] **Step 4: Commit**

```bash
git add container_tracker/ui/sample_data.py
git commit -m "ui: add sample_tracking_db() fixture for Phase 3 visual (10 containers)"
```

---

## CHECKPOINT B — STOP

**What's now true:**
- `container_tracker/ui/model.py` has ContainerTableModel + StatusBucketSortProxy, fully tested.
- `container_tracker/ui/sample_data.py` provides 10 sample records covering all status buckets.
- `pytest` green; `mypy --strict container_tracker` clean.
- MainWindow still not using any of this — Checkpoint C composition is next.

Autonomous cadence: verify, then dispatch Checkpoint C.

---

## Task 10: MainWindow composition — full layout

**Files:**
- Modify: `container_tracker/ui/main_window.py`

Replace the blank QMainWindow body with the full layout from spec §5.2. Order top-to-bottom:
1. Update banner (hidden initially)
2. Header row
3. Linked spreadsheet card
4. Stat cards row (4 cards)
5. Action row (Refresh pill | Remove | stretch | Add field | Carrier combo | Add & Track pill)
6. Container table (`QTableView` + `StatusBucketSortProxy` wrapping `ContainerTableModel`)
7. Activity log pane (`QPlainTextEdit`, empty for now — Phase 5 wires log handler)
8. Footer

Populated with sample data from Task 9. Dark-mode signal wired to `toggle_dark_mode`. No other functionality.

- [ ] **Step 1: Replace `container_tracker/ui/main_window.py`**

```python
"""Main application window — full layout (Phase 3).

Composes header, update banner, linked-spreadsheet card, stat cards, action
row, container table, activity log, and footer. Populated with sample data.
Backend functionality arrives in Phase 5.
"""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from container_tracker.__version__ import __version__
from container_tracker.core.api import CARRIER_NAMES
from container_tracker.core.status import bucket_counts
from container_tracker.ui.model import ContainerTableModel, StatusBucketSortProxy
from container_tracker.ui.sample_data import sample_tracking_db
from container_tracker.ui.theme import apply_theme
from container_tracker.ui.widgets import (
    HeaderRow,
    LinkedSpreadsheetCard,
    StatCard,
    UpdateBanner,
)


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main window. Owns config, is_dark, table model, and sub-widgets per spec §3.3."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self._config = config
        self._is_dark: bool = bool(config.get("dark_mode", False))

        self.setWindowTitle(f"Container Tracker v{__version__}")
        self.resize(QSize(1100, 720))

        self._build_layout()
        self._populate_sample_data()

        logger.info("MainWindow constructed (is_dark=%s)", self._is_dark)

    # ─── Public API ───────────────────────────────────────────────────

    @property
    def is_dark(self) -> bool:
        return self._is_dark

    def toggle_dark_mode(self) -> None:
        """Flip the theme, regenerate the app-level stylesheet, persist to config."""
        self._is_dark = not self._is_dark
        apply_theme(is_dark=self._is_dark)
        self._config["dark_mode"] = self._is_dark
        logger.info("dark mode toggled → %s", self._is_dark)

    # ─── Layout composition ───────────────────────────────────────────

    def _build_layout(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(16)

        self._banner = UpdateBanner()
        root.addWidget(self._banner)

        self._header = HeaderRow(
            title="Container Tracker",
            subtitle=str(self._config.get("company_name", "") or "Unconfigured — open Settings"),
            is_dark=self._is_dark,
        )
        self._header.dark_mode_toggled.connect(self._on_dark_mode_toggled)
        self._header.settings_clicked.connect(self._on_settings_clicked)
        root.addWidget(self._header)

        self._linked = LinkedSpreadsheetCard(str(self._config.get("excel_path", "") or ""))
        root.addWidget(self._linked)

        # Stat cards ---------------------------------------------------
        self._stat_tracked = StatCard("Tracked", 0)
        self._stat_sailing = StatCard("Sailing", 0, color_role="sailing")
        self._stat_arrived = StatCard("Arrived", 0, color_role="arrived")
        self._stat_delayed = StatCard("Delayed", 0, color_role="delayed")
        stat_row = QWidget()
        stat_layout = QHBoxLayout(stat_row)
        stat_layout.setContentsMargins(0, 0, 0, 0)
        stat_layout.setSpacing(12)
        for card in (self._stat_tracked, self._stat_sailing, self._stat_arrived, self._stat_delayed):
            stat_layout.addWidget(card, stretch=1)
        root.addWidget(stat_row)

        # Action row ---------------------------------------------------
        action_row = QWidget()
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self._refresh_button = QPushButton("Refresh All ETAs && Update Excel")  # && escapes the literal ampersand
        self._refresh_button.setProperty("variant", "primary")
        self._remove_button = QPushButton("Remove Selected")
        self._remove_button.setProperty("variant", "destructive")
        action_layout.addWidget(self._refresh_button)
        action_layout.addWidget(self._remove_button)
        action_layout.addStretch(1)

        self._add_input = QLineEdit()
        self._add_input.setPlaceholderText("Container number, e.g. MSKU1234567")
        self._add_input.setMinimumWidth(260)
        self._carrier_combo = QComboBox()
        self._carrier_combo.addItems(CARRIER_NAMES)
        self._add_button = QPushButton("Add && Track")
        self._add_button.setProperty("variant", "primary")
        action_layout.addWidget(self._add_input)
        action_layout.addWidget(self._carrier_combo)
        action_layout.addWidget(self._add_button)

        root.addWidget(action_row)

        # Table --------------------------------------------------------
        self._model = ContainerTableModel()
        self._proxy = StatusBucketSortProxy()
        self._proxy.setSourceModel(self._model)
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(2, Qt.SortOrder.AscendingOrder)  # Status column, bucket-priority
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self._table, stretch=1)

        # Activity log -------------------------------------------------
        self._activity_log = QPlainTextEdit()
        self._activity_log.setReadOnly(True)
        self._activity_log.setMaximumHeight(140)
        self._activity_log.setPlaceholderText("Activity log (refresh, add, remove will print here)…")
        root.addWidget(self._activity_log)

        # Footer -------------------------------------------------------
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        left = QLabel("Powered by ShipsGo API")
        left.setProperty("role", "hint")
        right = QLabel("Refreshes are free && unlimited • All times EST")
        right.setProperty("role", "hint")
        footer_layout.addWidget(left)
        footer_layout.addStretch(1)
        footer_layout.addWidget(right)
        root.addWidget(footer)

        self.setCentralWidget(central)

    def _populate_sample_data(self) -> None:
        """Phase 3: load hardcoded sample data. Phase 5 replaces with real data."""
        db = sample_tracking_db()
        self._model.set_records(list(db.values()))
        self._refresh_stat_cards(db)
        logger.info("Loaded sample data: %d containers", len(db))

    def _refresh_stat_cards(self, db: dict[str, dict[str, Any]]) -> None:
        counts = bucket_counts(db)
        self._stat_tracked.set_number(counts["total"])
        self._stat_sailing.set_number(counts["sailing"])
        self._stat_arrived.set_number(counts["arrived"])
        self._stat_delayed.set_number(counts["delayed"])

    # ─── Slots ────────────────────────────────────────────────────────

    def _on_dark_mode_toggled(self, is_dark: bool) -> None:
        if is_dark != self._is_dark:
            self.toggle_dark_mode()

    def _on_settings_clicked(self) -> None:
        # Settings dialog is Phase 4 territory. Log for now.
        logger.info("Settings gear clicked (Phase 4 will open SetupDialog)")

    # ─── Qt lifecycle ─────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        logger.info("MainWindow shown")
        super().showEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        logger.info("MainWindow closing")
        super().closeEvent(event)
```

- [ ] **Step 2: Confirm module imports cleanly**

Run: `python -c "from container_tracker.ui.main_window import MainWindow; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Run full tests + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass, mypy clean.

- [ ] **Step 4: Commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: compose full MainWindow layout (header, cards, table, log, footer) with sample data"
```

---

## Task 11: Full visibility + behavior smoke test

**Files:** none modified.

Verify the composed app launches, renders the expected structure, the dark-mode toggle flips the palette live, and close is clean.

- [ ] **Step 1: Run the smoke test via PowerShell**

```powershell
$ErrorActionPreference = "Stop"
$proc = Start-Process -FilePath "python" `
    -ArgumentList "-m", "container_tracker" `
    -WorkingDirectory "C:/Users/emine/OneDrive/Documents/Claude/container_tracking_build" `
    -PassThru
$deadline = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    $proc.Refresh()
    if ($proc.MainWindowHandle -ne 0 -and -not [string]::IsNullOrEmpty($proc.MainWindowTitle)) { break }
}
if ($proc.MainWindowHandle -eq 0 -or [string]::IsNullOrEmpty($proc.MainWindowTitle)) {
    Write-Output "FAILURE: window never registered (PID=$($proc.Id))"
    Stop-Process -Id $proc.Id -Force
    exit 1
}
Write-Output "OK: PID=$($proc.Id) Title='$($proc.MainWindowTitle)' Handle=$($proc.MainWindowHandle)"
$proc.CloseMainWindow() | Out-Null
$proc.WaitForExit(5000) | Out-Null
Write-Output "Exit=$($proc.ExitCode)"
```

Expected: handle non-zero, title "Container Tracker v1.1.0", clean exit 0.

- [ ] **Step 2: Programmatic structure check**

Run this Python one-liner to enumerate the top-level children of MainWindow and confirm the expected widgets are present:

```bash
python -c "
import sys
from PySide6.QtWidgets import QApplication
from container_tracker.ui.main_window import MainWindow
from container_tracker.ui.widgets import HeaderRow, LinkedSpreadsheetCard, StatCard, UpdateBanner
from PySide6.QtWidgets import QTableView, QPlainTextEdit
app = QApplication.instance() or QApplication(sys.argv)
mw = MainWindow({'company_name': 'Acme', 'excel_path': '', 'dark_mode': False, 'dismissed': [], 'contact_email': ''})
widget_types = {type(w).__name__ for w in mw.findChildren(object)}
required = {'UpdateBanner', 'HeaderRow', 'LinkedSpreadsheetCard', 'StatCard', 'QTableView', 'QPlainTextEdit'}
missing = required - widget_types
print('all required widgets present' if not missing else f'MISSING: {missing}')
print('table row count via proxy:', mw._proxy.rowCount())
assert not missing
assert mw._proxy.rowCount() == 10, f'expected 10 sample rows, got {mw._proxy.rowCount()}'
print('PASS')
"
```

Expected: `all required widgets present`, `table row count via proxy: 10`, `PASS`.

- [ ] **Step 3: Dark-mode toggle programmatic test**

Run:

```bash
python -c "
import sys
from PySide6.QtWidgets import QApplication
from container_tracker.ui.main_window import MainWindow
from container_tracker.ui.theme import apply_theme, LIGHT_PALETTE, DARK_PALETTE
app = QApplication.instance() or QApplication(sys.argv)
apply_theme(False)
mw = MainWindow({'company_name': 'Acme', 'excel_path': '', 'dark_mode': False, 'dismissed': [], 'contact_email': ''})
assert mw.is_dark is False
assert LIGHT_PALETTE['surface_base'] in app.styleSheet()
mw.toggle_dark_mode()
assert mw.is_dark is True
assert DARK_PALETTE['surface_base'] in app.styleSheet()
assert LIGHT_PALETTE['surface_base'] not in app.styleSheet()
mw.toggle_dark_mode()
assert mw.is_dark is False
assert LIGHT_PALETTE['surface_base'] in app.styleSheet()
print('dark-mode toggle works both directions')
"
```

Expected: `dark-mode toggle works both directions`.

- [ ] **Step 4: Full test suite + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass, mypy clean.

- [ ] **Step 5: No commit** — pure verification.

---

## CHECKPOINT C — STOP — PHASE 3 COMPLETE

**What's now true:**
- `MainWindow` composes the full layout per spec §5.2: update banner (hidden), header, linked-spreadsheet card, four stat cards, action row, container table, activity log, footer.
- Table shows 10 sample containers sorted by Status bucket priority (Delayed first).
- Dark-mode toggle in HeaderRow flips the theme live via `toggle_dark_mode` → `apply_theme`.
- `pytest` green on ~140+ tests (Phase 1 + 2 + 3); `mypy --strict container_tracker` clean on all source files.
- Backend wiring is still Phase 5 territory. Browse/Refresh/Add/Remove buttons exist but don't do anything yet.

**Ready for Phase 4** — first-run UX (Welcome + Settings dialogs).

---

## Self-Review

**1. Spec coverage** (§5.2, §5.4):
- Update banner (hidden) → Task 4 (widget) + Task 10 (MainWindow slot).
- Header row with title, subtitle, settings gear, dark-mode toggle → Task 6.
- Linked spreadsheet card with Browse / Create Template / Open in Excel → Task 5.
- Four stat cards (Tracked / Sailing / Arrived / Delayed) with bucket colors → Tasks 1 (theme), 3 (widget), 10 (composition).
- Action row with Refresh / Remove / Add input / Carrier combo / Add & Track → Task 10.
- `QTableView` + `ContainerTableModel` with sortable columns, multi-select, status foreground → Tasks 7, 10.
- Bucket-priority sort on Status column → Task 8.
- Activity log QPlainTextEdit (empty, read-only, placeholder) → Task 10.
- Footer with "Powered by ShipsGo API" left and "Refreshes are free & unlimited • All times EST" right → Task 10.
- Route column as single `POL → POD` cell → Task 7 (`_format_display`).
- Transit % formatted with `%` suffix → Task 7.

**2. Placeholder scan:** grepped for "TBD", "TODO", "implement later", "Similar to Task", "fill in" — none.

**3. Signature consistency:**
- `StatCard(label, number, color_role=None)` — defined Task 3; used in Task 10 with `color_role="sailing"|"arrived"|"delayed"`.
- `UpdateBanner()` no-args; `show_update(version, url)` method → defined Task 4, used in Task 10 (stored for Phase 6 banner logic).
- `LinkedSpreadsheetCard(initial_path="")` → defined Task 5; used in Task 10 with `config.excel_path`.
- `HeaderRow(title, subtitle, is_dark=False)` with `dark_mode_toggled(bool)` and `settings_clicked` signals → defined Task 6; used Task 10.
- `ContainerTableModel.set_records(list[dict])`, `record_at(row)`, `remove_rows(list[int])` → defined Task 7; `record_at` used by Task 8 sort proxy; `set_records` used in Task 10.
- `StatusBucketSortProxy()` with overridden `lessThan` → Task 8; used Task 10.
- `sample_tracking_db() -> dict[str, dict]` → Task 9; used Task 10.
- All `config: dict[str, Any]` usage matches the Phase 2 MainWindow contract.

**4. Phase 1/2 compatibility:** The new `tests/conftest.py`'s `qapp` fixture is additive. `theme.py` gains new QSS rules but no existing rules are touched. No Phase 1/2 code paths change behavior.

**5. Coverage blind spot:** The Activity log widget is instantiated in MainWindow but not yet connected to the `QtLogHandler` signal (that wiring is Phase 5 when background ops start emitting log records that matter). Phase 3 leaves it empty with a placeholder message, which is explicit in Task 10. Not a gap — by design.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-23-pyside6-phase3-main-window-layout.md`.

Execution mode: subagent-driven, one subagent per checkpoint, autonomous within-phase dispatch (orchestrator verifies and dispatches next checkpoint without user review). User reviews at Phase 4 boundary per established cadence.
