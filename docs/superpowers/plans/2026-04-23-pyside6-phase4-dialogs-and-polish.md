# Phase 4 — Dialogs + Phase 3 Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) Clean up five polish issues that surfaced in the Phase 3 visual, and (2) build the Welcome (first-run) and Settings dialogs per spec §5.3 — one `SetupDialog` class used in two modes — and wire them into the app so first-launch opens the Welcome dialog and the gear icon opens Settings from the main window.

**Architecture:** Polish lives alongside its natural owners: palette edits in `theme.py`, table-width fixes in `main_window.py`, button-enable states in `main_window.py`, footer label fix in `main_window.py`. Then `SetupDialog(QDialog)` in new `container_tracker/ui/dialogs.py` with a `mode: Literal["welcome", "settings"]` argument, three validated fields (Company, API key, Email), live-disabled Save button, inline per-field error messages. `__main__.py` gates `MainWindow.show()` on `is_first_run(config)`. `MainWindow._on_settings_clicked` opens `SetupDialog(mode="settings")`. After Save, MainWindow gets a `refresh_from_config()` method that updates header subtitle and linked-spreadsheet path.

**Tech Stack:** Python 3.11+, PySide6 ≥ 6.6, pytest (no new deps).

**Spec:** [2026-04-23-pyside6-migration-design.md §5.3, §6](../specs/2026-04-23-pyside6-migration-design.md)

---

## Checkpoint structure

Phase 4 has **three internal checkpoints**. Cadence: subagent reports back at each STOP, user reviews before next checkpoint dispatches (same pattern as Phase 1).

- **Checkpoint A** (Tasks 1–5): Phase 3 polish — dark-mode accent, table column widths, placeholder buttons disabled, footer `&` fix, stat-card / table data integrity check.
- **Checkpoint B** (Tasks 6–10): `SetupDialog` class implementation with both modes, validation, inline error labels, unit tests.
- **Checkpoint C** (Tasks 11–14): Wire dialogs into app — first-run gate, settings gear, MainWindow refresh hook, end-to-end smoke test.

---

## File Structure

Files created by end of Phase 4:

```
container_tracker/ui/
  dialogs.py           # SetupDialog(QDialog) — welcome + settings modes
  validation.py        # validate_setup_fields(), API_KEY_PATTERN, EMAIL_PATTERN

tests/
  test_dialogs.py      # SetupDialog unit tests (validation, button state, signals, mode behavior)
  test_validation.py   # validate_setup_fields table-driven tests
```

Files modified by Phase 4:

```
container_tracker/ui/
  theme.py             # dark-mode accent + accent_hover palette values (Checkpoint A)
  main_window.py       # table column sizing; disable placeholder buttons; footer &; settings gear wiring; refresh_from_config
  widgets.py           # (maybe) expose LinkedSpreadsheetCard button enable state — decide in Task 3
container_tracker/
  __main__.py          # first-run gate: is_first_run(config) → SetupDialog(welcome).exec() before MainWindow.show()

tests/
  test_theme.py        # update expected dark-mode accent values
```

Files untouched:

```
container_tracker/core/**                    # backend stable since Phase 1
container_tracker/ui/model.py                # table model unchanged
container_tracker/ui/sample_data.py          # Phase 3 sample data remains; Phase 5 replaces it
container_tracker/ui/theme_preview.py        # preview harness unchanged
container_tracker/ui/widgets.py              # widgets stable (probably — decide in Task 3)
container_tracker_gui.py                     # still alive until Phase 5
```

**Standing conventions:**
- `mypy --strict container_tracker` (expanded scope) stays clean after every task.
- One commit per task.
- Never touch `container_tracker_gui.py` or `container_tracker/core/*`.
- Never use `--no-verify`.
- Smoke-test window launches use the 1–10s retry-loop pattern on `$proc.Refresh()` (established in Phase 2 Checkpoint B, canonized in Phase 3):

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

## Task 1: Dark-mode accent color — swap from washed-out pale blue to saturated navy-blue

**Files:**
- Modify: `container_tracker/ui/theme.py`
- Modify: `tests/test_theme.py`

**Problem:** Dark-mode primary CTAs show as pale blue (`#6B9DD4`) that reads as a different design language from the crisp navy of light mode. Spec §5.1 says both modes should "feel like the same product, not two different apps." The current values are too light and desaturated against `#15171C`.

**Decision:** Keep the hue family of light-mode `#1E3A5F` (HSL ~213°, 53%, 25%) but lift lightness to ~48% for dark-mode readability — `#3E74B8` (HSL ~210°, 50%, 48%). Hover lightens further to `#5689C8` (HSL ~212°, 50%, 56%). Keep `status_sailing` distinct at `#6B9DD4` so it reads as a status indicator, not the brand color.

Current values:
- `DARK_PALETTE["accent"] = "#6B9DD4"` → washed out
- `DARK_PALETTE["accent_hover"] = "#84B0E0"` → even more washed out

New values:
- `DARK_PALETTE["accent"] = "#3E74B8"` — saturated mid-navy-blue, reads as "the same brand"
- `DARK_PALETTE["accent_hover"] = "#5689C8"` — lighter hover

**Hover-direction sanity check (do not flip during implementation):** in dark mode, hover raises lightness — base `#3E74B8` (L≈48%) → hover `#5689C8` (L≈56%). This matches the light-mode convention where hover `#2A4D7A` (L≈32%) is also lighter than base `#1E3A5F` (L≈25%). Both modes: hover = "a little lighter than base." Do not invert.

- [ ] **Step 1: Update the palette in `container_tracker/ui/theme.py`**

Open the file and modify the `DARK_PALETTE` dict — two entries only:

```python
    "accent":          "#3E74B8",  # saturated navy-blue — matches light-mode navy weight
    "accent_hover":    "#5689C8",  # lighter hover
```

Do NOT touch `status_sailing` (stays `#6B9DD4`), `accent_subtle` (stays `#1C2836`), or any other entry.

- [ ] **Step 2: Update the palette test to reflect new values**

Open `tests/test_theme.py`. Find `test_palettes_differ` — that test should still pass (surfaces and text_primary are still different between palettes). Find any test that hard-codes the old `#6B9DD4` value. None of the Phase 2 tests hard-code dark-mode accent specifically, but add one new test to lock in the new value:

```python
class TestDarkModeAccentPolish:
    """Phase 4 polish: dark-mode accent is no longer the washed-out pale blue."""

    def test_dark_accent_is_saturated_navy_not_pale_blue(self) -> None:
        # Old value was #6B9DD4 (too light). New value is #3E74B8.
        assert DARK_PALETTE["accent"].upper() == "#3E74B8"
        assert DARK_PALETTE["accent_hover"].upper() == "#5689C8"

    def test_dark_accent_distinct_from_status_sailing(self) -> None:
        """Brand accent and sailing status should not be the same color."""
        assert DARK_PALETTE["accent"] != DARK_PALETTE["status_sailing"]
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_theme.py -v`
Expected: all prior theme tests still pass (35) plus 2 new = 37.

- [ ] **Step 4: Run full suite + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all 155 pass, mypy clean.

- [ ] **Step 5: Visual spot-check (side-by-side)**

Launch the app twice — once with default (light) mode, once with dark. Use the PowerShell smoke-test pattern at the top of the plan:

```powershell
# Launch 1: default (light)
# Observe primary CTA color. Should be crisp navy.
# Close window.

# Before Launch 2: edit %APPDATA%\ContainerTracker\config.json to set "dark_mode": true
# Or toggle via the dark-mode checkbox once the window is open.
# Launch 2: dark mode
# Observe primary CTA color. Should be saturated navy-blue, not pale.
```

Note to reviewer: this step is for the orchestrator / user to eyeball. A subagent can't see the screen. If the dark-mode CTA still looks wrong after the palette swap, flag it in the Checkpoint A report and the user will iterate on values.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/theme.py tests/test_theme.py
git commit -m "theme: swap washed-out dark accent for saturated navy (#3E74B8 / #5689C8)"
```

---

## Task 2: Fix table column widths so all headers are fully visible

**Files:**
- Modify: `container_tracker/ui/main_window.py`

**Problem:** At 1100×720 default window size, table column headers render as "ontainer" instead of "Container #", "riginal ETA" instead of "Original ETA", etc. Sample data may also appear invisible in cells because cell widths are cramped to a default ~100 px.

**Cause:** `QHeaderView::ResizeMode.Interactive` + `setStretchLastSection(True)` leaves all columns at their default width (100 px in Qt defaults) until the user manually drags section dividers. With 9 columns × ~100 px = 900 px minus ~48 px side margins, most columns can't fit their header text.

**Fix:** Switch all columns to `ResizeMode.ResizeToContents` which sizes each column to fit both header text AND the widest cell contents. Then call `resizeColumnsToContents()` **after** `set_records(...)` so the widths reflect actual sample data. Keep `setStretchLastSection(True)` so the final (rightmost) column expands to fill any remaining horizontal space.

- [ ] **Step 1: In `container_tracker/ui/main_window.py`, find the table setup block**

Current block (inside `_build_layout`):

```python
self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
self._table.horizontalHeader().setStretchLastSection(True)
```

Replace with:

```python
header = self._table.horizontalHeader()
header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
header.setStretchLastSection(True)
# Keep user-resizable after the initial sizing so the user can still adjust.
header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
```

Rationale: `ResizeToContents` runs once implicitly when data is loaded, giving good initial widths. Then immediately swap to `Interactive` so the user can manually widen columns if they want. This is the standard Qt idiom for "auto-size once, user-resize after."

Additionally, after `_populate_sample_data()` in `__init__`, add an explicit resize call to catch the sample data:

Locate `self._populate_sample_data()` near the end of `__init__` and add the next line:

```python
self._populate_sample_data()
self._table.resizeColumnsToContents()
```

- [ ] **Step 2: Set an explicit minimum width on narrow columns that can still be cut off**

Some columns' header text is wider than their typical data (e.g., "Container #" is 11 chars but data is 11 chars of fixed-width alphanumerics — tight). Set a 60-px floor for all sections so narrow columns don't collapse below a readable minimum:

After the header configuration block, add:

```python
# Prevent any column from collapsing below a readable width even if the content is empty.
self._table.horizontalHeader().setMinimumSectionSize(60)
```

- [ ] **Step 3: Launch the app and verify all headers are visible**

Run the PowerShell smoke-test pattern with `python -m container_tracker`. After verifying handle + title, also grab the column widths via a one-off Python script:

```bash
python -c "
import sys
from PySide6.QtWidgets import QApplication
from container_tracker.ui.main_window import MainWindow
app = QApplication.instance() or QApplication(sys.argv)
mw = MainWindow({'company_name': 'Acme', 'excel_path': '', 'dark_mode': False, 'dismissed': [], 'contact_email': ''})
mw.show()
app.processEvents()
mw._table.resizeColumnsToContents()
app.processEvents()
header = mw._table.horizontalHeader()
for i in range(mw._proxy.columnCount()):
    name = mw._model.headerData(i, 2, 0)  # Qt.Orientation.Horizontal, Qt.DisplayRole
    width = header.sectionSize(i)
    print(f'  col {i:2d} {name!r:<18} width={width}')
total = sum(header.sectionSize(i) for i in range(mw._proxy.columnCount()))
print(f'  total width={total} (window content area ~1004px at 1100 default)')
"
```

Expected: each column width is large enough to fit its header label (heuristic: ≥ `len(header_text) * 7` px as a rough lower bound). Total should be ≤ ~1100 px, otherwise horizontal scroll appears (which is acceptable; `StretchLastSection` will fill any remainder).

- [ ] **Step 4: Run tests + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass, mypy clean. (This task doesn't add tests — column widths are visual; Step 3 is the verification.)

- [ ] **Step 5: Commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: resize table columns to contents + 60px min section; fixes cut-off headers"
```

---

## Task 3: Disable placeholder buttons until Phase 5 wiring

**Files:**
- Modify: `container_tracker/ui/main_window.py`

**Problem:** Refresh All, Remove Selected, Add & Track, Browse, Create Template, and Open in Excel all look fully functional but are no-ops until Phase 5 wires them to real behavior. Honest WIP state = grayed-out until wired.

**Keep enabled:** Settings gear (Phase 4 Checkpoint C wires it), dark-mode checkbox (works in Phase 3), Add input QLineEdit (can still type), Carrier combo (visual only).

- [ ] **Step 1: In `_build_layout`, disable the action-row buttons after construction**

Find the action-row block. After the existing `self._refresh_button = ...`, `self._remove_button = ...`, and `self._add_button = ...` lines, add `.setEnabled(False)` and a tooltip indicating Phase 5 wiring:

Replace:

```python
self._refresh_button = QPushButton("Refresh All ETAs && Update Excel")  # && escapes the literal ampersand
self._refresh_button.setProperty("variant", "primary")
self._remove_button = QPushButton("Remove Selected")
self._remove_button.setProperty("variant", "destructive")
```

with:

```python
self._refresh_button = QPushButton("Refresh All ETAs && Update Excel")  # && escapes for button mnemonic
self._refresh_button.setProperty("variant", "primary")
self._refresh_button.setEnabled(False)

self._remove_button = QPushButton("Remove Selected")
self._remove_button.setProperty("variant", "destructive")
self._remove_button.setEnabled(False)
```

And after `self._add_button = QPushButton("Add && Track")`:

```python
self._add_button.setProperty("variant", "primary")
self._add_button.setEnabled(False)
```

No tooltips — the grayed-out visual is sufficient signal for the user. "Wiring arrives in Phase 5" is dev language that shouldn't leak into the UI.

- [ ] **Step 2: Disable the LinkedSpreadsheetCard buttons via MainWindow**

`LinkedSpreadsheetCard` already exposes its buttons as `_browse_button`, `_create_button`, and `_open_button` (underscore-prefixed; used by the widget's own tests). MainWindow can reach in and disable them:

Find the line `self._linked = LinkedSpreadsheetCard(...)` in `_build_layout`. Immediately after it, add:

```python
# Phase 4: buttons are placeholders until Phase 5 wires them.
self._linked._browse_button.setEnabled(False)
self._linked._create_button.setEnabled(False)
# _open_button already disabled when path is empty; force disable regardless
# until Phase 5 restores the dynamic enable/disable behavior.
self._linked._open_button.setEnabled(False)
```

No tooltips. Reaching into `_open_button` overrides the widget's built-in "enable when path set" logic; that's fine for Phase 4. Phase 5 re-enables everything and restores dynamic behavior.

- [ ] **Step 3: Launch the app and visually verify**

Run the PowerShell smoke-test pattern with `python -m container_tracker`. Visually confirm:
- Refresh All, Remove Selected, Add & Track: grayed out (no tooltip).
- Browse, Create Template, Open in Excel: grayed out (no tooltip).
- Settings gear: still enabled.
- Dark mode checkbox: still enabled, still flips theme.
- Add input: can still type into it.
- Carrier combo: can still open dropdown.

- [ ] **Step 4: Run tests + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass, mypy clean. Widget tests don't assert enabled state from MainWindow's side, so no test breakage.

- [ ] **Step 5: Commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: disable placeholder buttons with 'Wiring arrives in Phase 5' tooltips"
```

---

## Task 4: Fix footer `&&` rendering to single `&`

**Files:**
- Modify: `container_tracker/ui/main_window.py`

**Problem:** Footer right-side label shows literal `"Refreshes are free && unlimited • All times EST"` because `&&` in a QLabel (without a buddy set) renders literally. QLabel's default `textFormat=AutoText` doesn't treat `&` as a mnemonic escape (that's QPushButton/QMenu). So the double-ampersand reads as double-ampersand.

**Fix:** Use a single `&`. The QPushButton texts that use `&&` for mnemonic escape (on the Refresh and Add & Track buttons) stay as-is — those DO need the escape because QPushButton parses `&` as a mnemonic accelerator.

- [ ] **Step 1: In `_build_layout`, fix the footer label**

Find:

```python
right = QLabel("Refreshes are free && unlimited • All times EST")
```

Replace with:

```python
right = QLabel("Refreshes are free & unlimited • All times EST")
```

- [ ] **Step 2: Launch and verify the footer reads correctly**

Run the PowerShell smoke-test. The footer right-side should now render `"Refreshes are free & unlimited • All times EST"`.

- [ ] **Step 3: Run tests + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass, mypy clean.

- [ ] **Step 4: Commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: fix footer '&&' rendering; QLabel doesn't need mnemonic escape"
```

---

## Task 5: Investigate stat-card / table data consistency

**Files:**
- Modify (if needed): `container_tracker/ui/main_window.py`

**Problem:** User reported stat cards show 10 / 5 / 4 / 2 but the table appears empty. Likely cause: column widths were so narrow (Task 2's bug) that cells had no visible room even though data was present. Tasks 2 + 3 should already resolve it. This task is a **verification step** — confirm the fix, or find a separate bug if stat cards and table genuinely disagree.

- [ ] **Step 1: Programmatic consistency check**

Run this one-liner to confirm stat cards and table show the same underlying data:

```bash
python -c "
import sys
from PySide6.QtWidgets import QApplication
from container_tracker.ui.main_window import MainWindow
from container_tracker.core.status import bucket_counts
app = QApplication.instance() or QApplication(sys.argv)
mw = MainWindow({'company_name': 'Acme', 'excel_path': '', 'dark_mode': False, 'dismissed': [], 'contact_email': ''})
stat_total   = int(mw._stat_tracked.number_text())
stat_sailing = int(mw._stat_sailing.number_text())
stat_arrived = int(mw._stat_arrived.number_text())
stat_delayed = int(mw._stat_delayed.number_text())
table_row_count = mw._proxy.rowCount()
print(f'stat cards: tracked={stat_total} sailing={stat_sailing} arrived={stat_arrived} delayed={stat_delayed}')
print(f'table rows: {table_row_count}')
assert stat_total == table_row_count, f'mismatch: stat_total={stat_total} table_rows={table_row_count}'
print('PASS: stat-card total matches table row count')
"
```

Expected: `stat_total == table_row_count` (both should be 10 for the sample data). If it fails, the stat card calculation is reading different data than the model — that's a real bug worth flagging before moving on.

- [ ] **Step 2: Launch the app, visually verify rows are visible**

Run the PowerShell smoke-test pattern. Launch `python -m container_tracker`, wait for window to register, observe: the table should show 10 rows of sample data (MSKU1234567, CMAU7654321, etc.) with visible cell content. Close cleanly.

If rows still appear empty despite passing Step 1: there's a rendering bug (not a data bug). Common causes:
- Row height too small (default shouldn't be). Verify `self._table.verticalHeader().defaultSectionSize()` returns ~25 px.
- Text foreground same as background (unlikely given the theme).
- Model returning `None` for `DisplayRole` — but tests assert otherwise.

Flag any surprise here and STOP.

- [ ] **Step 3: No code change if Steps 1 + 2 both pass.**

Most likely outcome: Tasks 2 + 3 resolved the issue. This task is a verification; only commit if you actually modified code.

If a fix IS needed, the commit message is:

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: fix stat-card / table data mismatch (details in commit body)"
```

Otherwise proceed without a commit.

---

## CHECKPOINT A — STOP

**What's now true:**
- Dark-mode primary CTAs use saturated navy-blue (`#3E74B8` / `#5689C8`) that matches the weight of light-mode navy.
- Table columns auto-size to content with a 60-px minimum; all headers fully visible at 1100×720.
- Placeholder buttons (Refresh, Remove, Add & Track, Browse, Create Template, Open in Excel) are grayed out with "Wiring arrives in Phase 5" tooltips.
- Footer renders `"Refreshes are free & unlimited • All times EST"` with a single `&`.
- Stat-card counts and table row counts are verified consistent.

**Report format for this checkpoint:**
- Exact `pytest -v` pass count (expected 155 — 153 prior + 2 new palette tests).
- Exact `mypy --strict container_tracker` output.
- Output of the column-width spot-check from Task 2 Step 3.
- Output of the stat/table consistency check from Task 5 Step 1.
- Any visual notes worth flagging before Checkpoint B (e.g., if the new dark accent still feels off despite the palette swap).
- `git log --oneline -10`.

---

## Task 6: `validate_setup_fields` and the two regex patterns

**Files:**
- Create: `container_tracker/ui/validation.py`
- Create: `tests/test_validation.py`

The monolith has this function at `container_tracker_gui.py:362–371`. Port it into a clean module so `SetupDialog` (Task 7) and Phase 6's update check can both consume it. Also defines `API_KEY_PATTERN` and `EMAIL_PATTERN` constants used for live-validation.

- [ ] **Step 1: Write failing tests**

Create `tests/test_validation.py`:

```python
"""Tests for setup-field validation."""
from __future__ import annotations

import pytest

from container_tracker.ui.validation import (
    API_KEY_PATTERN,
    EMAIL_PATTERN,
    validate_setup_fields,
)


class TestApiKeyPattern:
    @pytest.mark.parametrize("key", [
        "12345678-1234-1234-1234-123456789012",  # 36 chars with dashes
        "1234567890abcdefABCDEF1234567890abcd",  # 36 chars, mixed hex
        "a" * 30,                                 # 30 chars minimum
        "a" * 40,                                 # 40 chars maximum
        "ABCDEF1234567890" * 2 + "ABCDEF12",     # 40 chars exactly
    ])
    def test_accepts_valid_keys(self, key: str) -> None:
        assert API_KEY_PATTERN.match(key)

    @pytest.mark.parametrize("key", [
        "",
        "short",
        "a" * 29,           # too short
        "a" * 41,           # too long
        "contains-invalid-character-X-here!!",
        "12345 678 contains spaces",
    ])
    def test_rejects_invalid_keys(self, key: str) -> None:
        assert not API_KEY_PATTERN.match(key)


class TestEmailPattern:
    @pytest.mark.parametrize("email", [
        "user@example.com",
        "a.b@c.d",
        "first.last+tag@sub.example.co.uk",
    ])
    def test_accepts_valid_emails(self, email: str) -> None:
        assert EMAIL_PATTERN.match(email)

    @pytest.mark.parametrize("email", [
        "",
        "no-at-sign",
        "no-dot@example",
        "user@ example.com",   # space
        "@example.com",        # no local part
    ])
    def test_rejects_invalid_emails(self, email: str) -> None:
        assert not EMAIL_PATTERN.match(email)


class TestValidateSetupFields:
    def test_all_valid_returns_none(self) -> None:
        assert validate_setup_fields(
            company="Acme Imports",
            api_key="12345678-1234-1234-1234-123456789012",
            email="ops@acme.test",
        ) == {}

    def test_missing_company_returns_error_on_company_key(self) -> None:
        errors = validate_setup_fields(
            company="",
            api_key="12345678-1234-1234-1234-123456789012",
            email="ops@acme.test",
        )
        assert "company" in errors
        assert "required" in errors["company"].lower()

    def test_missing_api_key_returns_error_on_api_key(self) -> None:
        errors = validate_setup_fields(
            company="Acme",
            api_key="",
            email="ops@acme.test",
        )
        assert "api_key" in errors

    def test_malformed_api_key_returns_error_on_api_key(self) -> None:
        errors = validate_setup_fields(
            company="Acme",
            api_key="not-a-uuid",
            email="ops@acme.test",
        )
        assert "api_key" in errors

    def test_malformed_email_returns_error_on_email(self) -> None:
        errors = validate_setup_fields(
            company="Acme",
            api_key="12345678-1234-1234-1234-123456789012",
            email="not-an-email",
        )
        assert "email" in errors

    def test_multiple_errors_all_returned(self) -> None:
        errors = validate_setup_fields(company="", api_key="", email="")
        assert "company" in errors
        assert "api_key" in errors
        assert "email" in errors

    def test_whitespace_only_company_treated_as_missing(self) -> None:
        errors = validate_setup_fields(
            company="   ",
            api_key="12345678-1234-1234-1234-123456789012",
            email="ops@acme.test",
        )
        assert "company" in errors
```

- [ ] **Step 2: Run tests, confirm fail**

Run: `pytest tests/test_validation.py -v`
Expected: `ModuleNotFoundError: No module named 'container_tracker.ui.validation'`.

- [ ] **Step 3: Implement `container_tracker/ui/validation.py`**

```python
"""Validation for the SetupDialog fields.

Returns per-field error dicts (`{field_key: message}`) so the UI can surface
errors inline under each field. An empty dict means all fields are valid.
"""
from __future__ import annotations

import re


# Spec §5.3: API key regex is ^[0-9a-fA-F-]{30,40}$
API_KEY_PATTERN = re.compile(r"^[0-9a-fA-F\-]{30,40}$")

# Email: single @ and at least one . in the domain, no whitespace.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_setup_fields(company: str, api_key: str, email: str) -> dict[str, str]:
    """Validate the three setup fields. Returns `{field_key: message}` of failures.

    Empty dict means all valid — save button should be enabled.
    """
    errors: dict[str, str] = {}
    if not company.strip():
        errors["company"] = "Company name is required."
    if not api_key.strip():
        errors["api_key"] = "ShipsGo API key is required."
    elif not API_KEY_PATTERN.match(api_key.strip()):
        errors["api_key"] = (
            "That API key doesn't look right — check for extra spaces or missing characters."
        )
    if not email.strip():
        errors["email"] = "Contact email is required."
    elif not EMAIL_PATTERN.match(email.strip()):
        errors["email"] = "Enter a valid email address."
    return errors
```

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_validation.py -v`
Expected: all tests pass.

- [ ] **Step 5: Run mypy**

Run: `mypy --strict container_tracker`
Expected: clean on 17 files (was 16, +validation.py).

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/validation.py tests/test_validation.py
git commit -m "ui: extract validate_setup_fields (per-field error dict)"
```

---

## Task 7: `SetupDialog` skeleton — constructor, layout, fields

**Files:**
- Create: `container_tracker/ui/dialogs.py`
- Create: `tests/test_dialogs.py`

Skeleton first: constructor takes `mode: Literal["welcome", "settings"]`, initial values for the three fields, and (settings-mode only) the app version + data-folder path. Layout is three QLineEdits with per-field inline error QLabels underneath each one, a button row at the bottom. Save button is disabled by default. No validation wiring yet — Task 8.

**Decisions for this task (flagged for orchestrator review):**
- **API key field uses `echoMode=Password`** in both modes — keys are credentials, masking is standard.
- **Settings mode, existing key:** the API key field is left empty with placeholder `"API key is set — leave empty to keep current, or type to replace"`. On save: if empty AND a key already exists in keyring, preserve; if empty AND no keyring entry, this is an error. If non-empty, validate as UUID regex and replace.
- **Inline error labels:** one QLabel per field below the QLineEdit, hidden until the field is touched-and-invalid. Styled with `role="hint"` + `statRole="delayed"` for muted rust color.
- **Contact-email field:** shown in both modes (not flagged as "optional" anywhere; spec §5.3 lists it as required).

- [ ] **Step 1: Write failing tests**

Create `tests/test_dialogs.py`:

```python
"""Unit tests for SetupDialog."""
from __future__ import annotations

import pytest

from container_tracker.ui.dialogs import SetupDialog


class TestSetupDialogSkeleton:
    def test_welcome_mode_has_no_cancel_button(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        assert dlg._save_button is not None
        assert dlg._cancel_button is None

    def test_settings_mode_has_cancel_button(self, qapp) -> None:
        dlg = SetupDialog(mode="settings")
        assert dlg._save_button is not None
        assert dlg._cancel_button is not None

    def test_welcome_mode_save_disabled_by_default(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        assert dlg._save_button.isEnabled() is False

    def test_welcome_mode_has_three_input_fields(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        assert dlg._company_input is not None
        assert dlg._api_key_input is not None
        assert dlg._email_input is not None

    def test_welcome_mode_prepopulates_empty(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        assert dlg._company_input.text() == ""
        assert dlg._api_key_input.text() == ""
        assert dlg._email_input.text() == ""

    def test_settings_mode_prepopulates_from_initial_values(self, qapp) -> None:
        dlg = SetupDialog(
            mode="settings",
            initial_company="Acme",
            initial_email="ops@acme.test",
            initial_api_key_set=True,
        )
        assert dlg._company_input.text() == "Acme"
        assert dlg._email_input.text() == "ops@acme.test"
        # API key field stays empty in settings mode (placeholder instead).
        assert dlg._api_key_input.text() == ""
        assert dlg._api_key_input.placeholderText() == "Leave empty to keep current key"

    def test_api_key_field_is_password_mode(self, qapp) -> None:
        from PySide6.QtWidgets import QLineEdit
        dlg = SetupDialog(mode="welcome")
        assert dlg._api_key_input.echoMode() == QLineEdit.EchoMode.Password

    def test_settings_mode_shows_version_label(self, qapp) -> None:
        dlg = SetupDialog(mode="settings", app_version="1.1.0")
        # Expose via _version_label text.
        assert "1.1.0" in dlg._version_label.text()

    def test_welcome_mode_does_not_show_version_label(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        assert dlg._version_label is None

    def test_welcome_mode_window_title(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        assert "Welcome" in dlg.windowTitle()

    def test_settings_mode_window_title(self, qapp) -> None:
        dlg = SetupDialog(mode="settings")
        assert "Settings" in dlg.windowTitle()

    def test_invalid_mode_raises(self, qapp) -> None:
        with pytest.raises(ValueError):
            SetupDialog(mode="bogus")  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests, confirm fail**

Run: `pytest tests/test_dialogs.py -v`
Expected: `ModuleNotFoundError: No module named 'container_tracker.ui.dialogs'`.

- [ ] **Step 3: Implement the SetupDialog skeleton**

Create `container_tracker/ui/dialogs.py`:

```python
"""SetupDialog — modal dialog for first-run (Welcome) and Settings.

Two modes share one class per spec §5.3. Live validation is wired in Task 8;
this skeleton just lays out the widgets and exposes them to tests.
"""
from __future__ import annotations

import logging
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


logger = logging.getLogger(__name__)


SetupDialogMode = Literal["welcome", "settings"]


class SetupDialog(QDialog):
    """Modal dialog for collecting company_name + ShipsGo API key + contact_email.

    mode="welcome"  — first-run. No Cancel button. Closing via × quits the app.
    mode="settings" — edit settings. Has Cancel. × just dismisses.
    """

    def __init__(
        self,
        mode: SetupDialogMode = "welcome",
        initial_company: str = "",
        initial_email: str = "",
        initial_api_key_set: bool = False,
        app_version: str = "",
        data_folder: str = "",
        github_repo_url: str = "https://github.com/m-mcohen/container-tracker",
    ) -> None:
        super().__init__()
        if mode not in ("welcome", "settings"):
            raise ValueError(f"mode must be 'welcome' or 'settings'; got {mode!r}")
        self._mode: SetupDialogMode = mode
        self._initial_api_key_set = initial_api_key_set

        if mode == "welcome":
            self.setWindowTitle("Welcome to Container Tracker")
        else:
            self.setWindowTitle("Container Tracker — Settings")
        self.setModal(True)
        self.setMinimumWidth(480)

        # Remove the × close button disappearance would be jarring; keep it.
        # In welcome mode, closeEvent quits the app. Settings mode dismisses.

        # ─── Fields ─────────────────────────────────────────────────
        self._company_input = QLineEdit(initial_company)
        self._company_input.setPlaceholderText("Your company or project name")
        self._company_error = self._make_error_label()

        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        if mode == "settings" and initial_api_key_set:
            self._api_key_input.setPlaceholderText("Leave empty to keep current key")
        else:
            self._api_key_input.setPlaceholderText(
                "ShipsGo API key (UUID from dashboard → Integrations → ShipsGo API)"
            )
        self._api_key_error = self._make_error_label()
        self._api_key_hint = QLabel(
            "Find your key at shipsgo.com → Dashboard → Integrations → ShipsGo API"
        )
        self._api_key_hint.setProperty("role", "hint")

        self._email_input = QLineEdit(initial_email)
        self._email_input.setPlaceholderText("contact@yourcompany.com")
        self._email_error = self._make_error_label()

        # ─── Save / Cancel buttons ──────────────────────────────────
        self._save_button = QPushButton("Save")
        self._save_button.setProperty("variant", "primary")
        self._save_button.setEnabled(False)
        self._save_button.clicked.connect(self.accept)

        self._cancel_button: QPushButton | None = None
        if mode == "settings":
            self._cancel_button = QPushButton("Cancel")
            self._cancel_button.setProperty("variant", "secondary")
            self._cancel_button.clicked.connect(self.reject)

        # ─── Settings-only read-only info ───────────────────────────
        self._version_label: QLabel | None = None
        self._data_folder_label: QLabel | None = None
        self._data_folder_path: str = data_folder  # stored for click handler
        self._repo_link_label: QLabel | None = None
        if mode == "settings":
            self._version_label = QLabel(f"Container Tracker v{app_version}")
            self._version_label.setProperty("role", "hint")

            # Clickable HTML link that opens the folder in Explorer.
            # Uses href="folder" as a sentinel; linkActivated fires the real open.
            self._data_folder_label = QLabel(
                f'Data folder: <a href="folder" style="color: inherit;">{data_folder}</a>'
            )
            self._data_folder_label.setProperty("role", "hint")
            self._data_folder_label.setTextFormat(Qt.TextFormat.RichText)
            self._data_folder_label.linkActivated.connect(self._on_data_folder_clicked)

            self._repo_link_label = QLabel(
                f'<a href="{github_repo_url}" style="color: inherit;">GitHub repo</a>'
            )
            self._repo_link_label.setOpenExternalLinks(True)
            self._repo_link_label.setProperty("role", "hint")

        # ─── Layout ─────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        if mode == "welcome":
            intro = QLabel(
                "Let's get you set up. You can change these later in Settings."
            )
            intro.setWordWrap(True)
            root.addWidget(intro)

        root.addWidget(self._field_block("Company name", self._company_input, self._company_error))
        root.addWidget(self._api_key_block())
        root.addWidget(self._field_block("Contact email", self._email_input, self._email_error))

        if mode == "settings":
            # Read-only info block above the buttons.
            root.addStretch(1)
            info = QVBoxLayout()
            assert self._version_label is not None
            assert self._data_folder_label is not None
            assert self._repo_link_label is not None
            info.addWidget(self._version_label)
            info.addWidget(self._data_folder_label)
            info.addWidget(self._repo_link_label)
            info_container = QWidget()
            info_container.setLayout(info)
            root.addWidget(info_container)

        # Button row
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        if self._cancel_button is not None:
            button_row.addWidget(self._cancel_button)
        button_row.addWidget(self._save_button)
        root.addLayout(button_row)

    # ─── Helpers ──────────────────────────────────────────────────────

    def _make_error_label(self) -> QLabel:
        label = QLabel("")
        label.setProperty("role", "hint")
        label.setProperty("statRole", "delayed")  # muted rust for error text
        label.hide()
        return label

    def _field_block(self, label_text: str, input_widget: QLineEdit, error_label: QLabel) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        # HTML <b> is rendered by QLabel's default AutoText textFormat.
        # Avoids adding a new QSS role just for field labels.
        label = QLabel(f"<b>{label_text}</b>")
        layout.addWidget(label)
        layout.addWidget(input_widget)
        layout.addWidget(error_label)
        return container

    def _api_key_block(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel("<b>ShipsGo API key</b>")
        layout.addWidget(label)
        layout.addWidget(self._api_key_input)
        layout.addWidget(self._api_key_hint)
        layout.addWidget(self._api_key_error)
        return container

    # ─── Qt lifecycle ─────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._mode == "welcome":
            # × on welcome mode quits the app (spec §5.3).
            from PySide6.QtWidgets import QApplication
            logger.info("Welcome dialog closed via × — quitting app")
            super().closeEvent(event)
            QApplication.instance().quit()  # type: ignore[union-attr]
        else:
            super().closeEvent(event)

    # ─── Data folder click handler (settings mode) ────────────────────

    def _on_data_folder_clicked(self, href: str) -> None:
        """Open the data folder in Windows Explorer (or platform equivalent)."""
        import os
        import subprocess
        import sys
        path = self._data_folder_path
        logger.info("Opening data folder: %s", path)
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            logger.info("Failed to open data folder: %s", exc)
```

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_dialogs.py -v`
Expected: 12 tests pass.

- [ ] **Step 5: Run full tests + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass; mypy clean on 18 files (was 17, +dialogs.py).

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/dialogs.py tests/test_dialogs.py
git commit -m "ui: add SetupDialog skeleton (welcome + settings modes)"
```

---

## Task 8: SetupDialog live validation

**Files:**
- Modify: `container_tracker/ui/dialogs.py`
- Modify: `tests/test_dialogs.py`

Wire `validate_setup_fields` (Task 6) into the dialog. Save button enables only when all fields are valid. Inline error labels show under each invalid field once the user has touched it.

Special rule: in settings mode, an **empty** API key field is valid IFF `initial_api_key_set` was True (meaning the keyring already has a value to preserve).

- [ ] **Step 1: Append failing tests to `tests/test_dialogs.py`**

```python
class TestSetupDialogValidation:
    def test_save_enables_when_all_valid(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        dlg._company_input.setText("Acme")
        dlg._api_key_input.setText("12345678-1234-1234-1234-123456789012")
        dlg._email_input.setText("ops@acme.test")
        # Simulate Qt text-changed firing.
        dlg._revalidate()
        assert dlg._save_button.isEnabled() is True

    def test_save_disabled_when_company_missing(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        dlg._api_key_input.setText("12345678-1234-1234-1234-123456789012")
        dlg._email_input.setText("ops@acme.test")
        dlg._revalidate()
        assert dlg._save_button.isEnabled() is False

    def test_error_label_hidden_until_touched(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        # Untouched — hidden.
        assert dlg._company_error.isHidden()
        # Touch + revalidate.
        dlg._mark_touched("company")
        dlg._revalidate()
        assert dlg._company_error.isVisible() is True

    def test_error_label_shows_message_for_invalid_api_key(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        dlg._api_key_input.setText("too-short")
        dlg._mark_touched("api_key")
        dlg._revalidate()
        assert "doesn't look right" in dlg._api_key_error.text().lower()

    def test_error_label_hides_when_field_corrected(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        dlg._api_key_input.setText("bad")
        dlg._mark_touched("api_key")
        dlg._revalidate()
        assert dlg._api_key_error.isVisible() is True
        dlg._api_key_input.setText("12345678-1234-1234-1234-123456789012")
        dlg._revalidate()
        assert dlg._api_key_error.isHidden()

    def test_settings_mode_empty_api_key_valid_when_key_already_set(self, qapp) -> None:
        dlg = SetupDialog(
            mode="settings",
            initial_company="Acme",
            initial_email="ops@acme.test",
            initial_api_key_set=True,
        )
        # All fields pre-populated (API key left empty since it's set).
        dlg._revalidate()
        assert dlg._save_button.isEnabled() is True

    def test_settings_mode_empty_api_key_invalid_when_key_not_set(self, qapp) -> None:
        dlg = SetupDialog(
            mode="settings",
            initial_company="Acme",
            initial_email="ops@acme.test",
            initial_api_key_set=False,
        )
        dlg._revalidate()
        assert dlg._save_button.isEnabled() is False

    def test_settings_mode_replacing_api_key_validates_new_value(self, qapp) -> None:
        dlg = SetupDialog(
            mode="settings",
            initial_company="Acme",
            initial_email="ops@acme.test",
            initial_api_key_set=True,
        )
        dlg._api_key_input.setText("too-short")
        dlg._mark_touched("api_key")
        dlg._revalidate()
        assert dlg._save_button.isEnabled() is False
        assert dlg._api_key_error.isVisible() is True
```

- [ ] **Step 2: Run tests, confirm fail**

Run: `pytest tests/test_dialogs.py::TestSetupDialogValidation -v`
Expected: `AttributeError` on `_revalidate` / `_mark_touched`.

- [ ] **Step 3: Add validation logic to `SetupDialog`**

At the top of `container_tracker/ui/dialogs.py`, add import:

```python
from container_tracker.ui.validation import validate_setup_fields
```

Inside `__init__`, after the fields are constructed and before the layout code, wire the `textChanged` signals and add a touched-set:

```python
        self._touched: set[str] = set()

        # Wire live validation.
        self._company_input.textChanged.connect(lambda: self._on_changed("company"))
        self._api_key_input.textChanged.connect(lambda: self._on_changed("api_key"))
        self._email_input.textChanged.connect(lambda: self._on_changed("email"))
```

Then add these methods to `SetupDialog`:

```python
    # ─── Validation ──────────────────────────────────────────────────

    def _on_changed(self, field: str) -> None:
        self._touched.add(field)
        self._revalidate()

    def _mark_touched(self, field: str) -> None:
        """Test helper: mark a field as touched without relying on textChanged."""
        self._touched.add(field)

    def _revalidate(self) -> None:
        company = self._company_input.text()
        email = self._email_input.text()
        api_key_text = self._api_key_input.text()

        # Settings-mode keep-current rule: empty api_key is valid iff
        # initial_api_key_set is True.
        effective_api_key = api_key_text
        if self._mode == "settings" and self._initial_api_key_set and not api_key_text.strip():
            effective_api_key = "PLACEHOLDER" + ("0" * 30)  # any 30+ char hex-only sentinel

        errors = validate_setup_fields(company=company, api_key=effective_api_key, email=email)
        # If we substituted the sentinel, clear any api_key error it might have caused
        # (it shouldn't since the sentinel is valid, but be defensive).

        self._apply_errors(errors)
        self._save_button.setEnabled(not errors)

    def _apply_errors(self, errors: dict[str, str]) -> None:
        for key, label in (
            ("company", self._company_error),
            ("api_key", self._api_key_error),
            ("email", self._email_error),
        ):
            message = errors.get(key, "")
            if message and key in self._touched:
                label.setText(message)
                label.show()
            else:
                label.clear()
                label.hide()
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `pytest tests/test_dialogs.py -v`
Expected: all dialog tests pass (12 from Task 7 + 8 new).

- [ ] **Step 5: Run full tests + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass, mypy clean.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/dialogs.py tests/test_dialogs.py
git commit -m "ui: wire SetupDialog live validation with inline error labels"
```

---

## Task 9: `SetupDialog.get_values()` — expose saved values to caller

**Files:**
- Modify: `container_tracker/ui/dialogs.py`
- Modify: `tests/test_dialogs.py`

The dialog doesn't write to config or keyring itself (keeps it testable and pure). It exposes a `get_values()` method that the caller (Phase 4 Checkpoint C wiring) uses to pull out validated strings. For settings mode with an unchanged (empty) API key, `get_values()` returns `None` for the key — meaning "keep current."

- [ ] **Step 1: Append failing tests**

```python
class TestSetupDialogValues:
    def test_get_values_returns_typed_dict(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        dlg._company_input.setText("Acme")
        dlg._api_key_input.setText("12345678-1234-1234-1234-123456789012")
        dlg._email_input.setText("ops@acme.test")
        values = dlg.get_values()
        assert values["company"] == "Acme"
        assert values["email"] == "ops@acme.test"
        assert values["api_key"] == "12345678-1234-1234-1234-123456789012"

    def test_get_values_strips_whitespace(self, qapp) -> None:
        dlg = SetupDialog(mode="welcome")
        dlg._company_input.setText("  Acme  ")
        dlg._api_key_input.setText("  12345678-1234-1234-1234-123456789012  ")
        dlg._email_input.setText("  ops@acme.test  ")
        values = dlg.get_values()
        assert values["company"] == "Acme"
        assert values["api_key"] == "12345678-1234-1234-1234-123456789012"
        assert values["email"] == "ops@acme.test"

    def test_settings_mode_returns_none_api_key_when_field_empty(self, qapp) -> None:
        """Empty api_key field in settings mode means 'keep current'."""
        dlg = SetupDialog(
            mode="settings",
            initial_company="Acme",
            initial_email="ops@acme.test",
            initial_api_key_set=True,
        )
        values = dlg.get_values()
        assert values["api_key"] is None

    def test_settings_mode_returns_new_api_key_when_field_set(self, qapp) -> None:
        dlg = SetupDialog(
            mode="settings",
            initial_company="Acme",
            initial_email="ops@acme.test",
            initial_api_key_set=True,
        )
        dlg._api_key_input.setText("12345678-1234-1234-1234-123456789012")
        values = dlg.get_values()
        assert values["api_key"] == "12345678-1234-1234-1234-123456789012"
```

- [ ] **Step 2: Run tests, confirm fail**

Run: `pytest tests/test_dialogs.py::TestSetupDialogValues -v`
Expected: `AttributeError: 'SetupDialog' object has no attribute 'get_values'`.

- [ ] **Step 3: Add `get_values` to SetupDialog**

Append to `SetupDialog` in `container_tracker/ui/dialogs.py`:

```python
    def get_values(self) -> dict[str, str | None]:
        """Return validated field values.

        Returns a dict with keys 'company', 'email' (both str), and 'api_key'
        (str OR None). api_key is None in settings mode when the user left the
        field empty — meaning "keep the currently-stored key unchanged." In
        welcome mode, or when the field has any value, api_key is the string.
        """
        company = self._company_input.text().strip()
        email = self._email_input.text().strip()
        api_key_text = self._api_key_input.text().strip()

        api_key: str | None
        if self._mode == "settings" and self._initial_api_key_set and not api_key_text:
            api_key = None
        else:
            api_key = api_key_text

        return {"company": company, "email": email, "api_key": api_key}
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `pytest tests/test_dialogs.py -v`
Expected: all dialog tests pass.

- [ ] **Step 5: Run full tests + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass, mypy clean.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/dialogs.py tests/test_dialogs.py
git commit -m "ui: SetupDialog.get_values() — typed result with None for keep-current api_key"
```

---

## Task 10: Welcome-mode × behavior smoke test

**Files:** none modified.

Programmatic test that closing a welcome-mode SetupDialog via the × button (simulated via `close()`) triggers `QApplication.quit()`. This is spec §5.3: "Welcome mode: no Cancel; `closeEvent` triggers `QApplication.quit()`."

- [ ] **Step 1: Run the verification**

```bash
python -c "
import sys
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from container_tracker.ui.dialogs import SetupDialog

app = QApplication.instance() or QApplication(sys.argv)

# Welcome mode: close() should trigger QApplication.quit()
dlg = SetupDialog(mode='welcome')
quit_called = []
with patch.object(app, 'quit', lambda: quit_called.append(True)):
    dlg.close()
assert quit_called == [True], f'welcome close did NOT call quit; quit_called={quit_called}'

# Settings mode: close() should NOT trigger quit()
dlg2 = SetupDialog(mode='settings')
quit_called2 = []
with patch.object(app, 'quit', lambda: quit_called2.append(True)):
    dlg2.close()
assert quit_called2 == [], f'settings close unexpectedly called quit; quit_called={quit_called2}'

print('PASS: welcome × quits, settings × dismisses')
"
```

Expected: `PASS: welcome × quits, settings × dismisses`.

- [ ] **Step 2: No commit** — verification only.

---

## CHECKPOINT B — STOP

**What's now true:**
- `container_tracker/ui/validation.py` holds `validate_setup_fields` with per-field error dict.
- `container_tracker/ui/dialogs.py` has `SetupDialog(QDialog)` with two modes, three validated fields, inline error labels, masked API key input, settings-mode version/data-folder/repo-link readonly info.
- Live validation: Save enables when all fields valid. Inline errors appear only when user has touched a field.
- Welcome-mode × closes app; settings-mode × dismisses.
- `get_values()` returns a typed dict with `api_key: str | None` (None = keep current in settings mode).
- `pytest` green on ~185 tests (155 after Checkpoint A + ~10 validation + ~20 dialog tests).
- `mypy --strict container_tracker` clean.

**Report format for this checkpoint:**
- Exact `pytest -v` pass count.
- Exact `mypy --strict container_tracker` output.
- Output of the Task 10 verification (welcome × quits, settings × dismisses).
- List of SetupDialog design decisions made (password echo mode, placeholder text for settings-mode existing key, error label styling) — flag any you'd push back on.
- `git log --oneline -15`.

---

## Task 11: First-run gate in `__main__.py`

**Files:**
- Modify: `container_tracker/__main__.py`

Before showing `MainWindow`, check `is_first_run(config)`. If true, run `SetupDialog(mode="welcome").exec()` modal. On Save (accept), write results to config + keyring and proceed to MainWindow. On × (reject via closeEvent → app.quit), the app exits before MainWindow.show.

- [ ] **Step 1: Modify `container_tracker/__main__.py`**

Replace the existing `main()` body with:

```python
def main() -> int:
    qt_handler = _configure_logging()
    logger = logging.getLogger(__name__)

    app = QApplication(sys.argv)
    app.setApplicationName("Container Tracker")
    app.setOrganizationName("Michael Cohen")

    logger.info("Container Tracker v%s starting", __version__)

    config = load_config()
    logger.info(
        "config loaded: company=%r, excel_path=%r, dark_mode=%s",
        config.get("company_name"),
        config.get("excel_path"),
        config.get("dark_mode"),
    )

    # Apply the theme BEFORE any widget is constructed so dialogs inherit it.
    from container_tracker.ui.theme import apply_theme
    apply_theme(is_dark=bool(config.get("dark_mode", False)))

    first_run = is_first_run(config)
    api_token_present = bool(get_api_token())
    logger.info("first-run=%s, api-token-present=%s", first_run, api_token_present)

    if first_run:
        logger.info("First run — showing Welcome dialog")
        from container_tracker.core.persistence import save_config, set_api_token
        from container_tracker.ui.dialogs import SetupDialog
        dialog = SetupDialog(mode="welcome")
        result = dialog.exec()
        if result != dialog.DialogCode.Accepted:
            # User closed via × (which triggered QApplication.quit via closeEvent)
            # or some other reject path. Either way, don't show the main window.
            logger.info("user cancelled first-run setup; exiting")
            return 0
        values = dialog.get_values()
        config["company_name"] = values["company"] or ""
        config["contact_email"] = values["email"] or ""
        save_config(config)
        if values["api_key"]:
            set_api_token(values["api_key"])
        logger.info(
            "Welcome-save complete: company=%r, email=%r, api-token-present=%s",
            values["company"], values["email"], bool(values["api_key"]),
        )

    from container_tracker.ui.main_window import MainWindow
    window = MainWindow(config)
    window.show()

    _ = qt_handler  # connected in Phase 5
    return app.exec()
```

- [ ] **Step 2: Programmatic first-run simulation**

We can't fully automate "click Save in the welcome dialog and check MainWindow appears" without a full GUI test framework. But we can verify the code path exists and imports cleanly:

```bash
python -c "
import sys
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication

# Fake first-run by patching is_first_run to return True,
# and patch SetupDialog.exec to return Accepted without actually showing a dialog.
from container_tracker.core import persistence
from container_tracker.ui import dialogs

app = QApplication.instance() or QApplication(sys.argv)

# Patch: first_run True, SetupDialog pretends Accept was clicked with fake values.
original_exec = dialogs.SetupDialog.exec
def fake_exec(self):
    # Populate values and mark accept.
    self._company_input.setText('TestCo')
    self._api_key_input.setText('12345678-1234-1234-1234-123456789012')
    self._email_input.setText('test@test.com')
    self._revalidate()
    return self.DialogCode.Accepted
dialogs.SetupDialog.exec = fake_exec

with patch.object(persistence, 'is_first_run', return_value=True):
    with patch.object(persistence, 'get_api_token', return_value=''):
        with patch.object(persistence, 'save_config') as save_mock:
            with patch.object(persistence, 'set_api_token') as set_tok_mock:
                # Import after patches. main() constructs QApplication, window, enters event loop.
                # We can't run the event loop, but we CAN verify the path executes up to app.exec.
                # Easiest check: just import the module and confirm _configure_logging is wired.
                from container_tracker.__main__ import _configure_logging
                print('import path clean')
print('PASS')
" 2>&1 | tail -5
```

Expected: `import path clean` and `PASS`. Full end-to-end is a manual smoke test (Task 14).

- [ ] **Step 3: Full test suite + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all tests pass; mypy clean.

- [ ] **Step 4: Commit**

```bash
git add container_tracker/__main__.py
git commit -m "main: gate MainWindow on is_first_run; show Welcome dialog and persist on save"
```

---

## Task 12: Settings gear → SetupDialog(settings) wiring

**Files:**
- Modify: `container_tracker/ui/main_window.py`

Replace the stub `_on_settings_clicked` log line with a real `SetupDialog(mode="settings")` opener. Pre-populate from config + keyring-presence. On Accept, write results back.

- [ ] **Step 1: Replace `_on_settings_clicked` in `container_tracker/ui/main_window.py`**

Find:

```python
    def _on_settings_clicked(self) -> None:
        # Settings dialog is Phase 4 territory. Log for now.
        logger.info("Settings gear clicked (Phase 4 will open SetupDialog)")
```

Replace with:

```python
    def _on_settings_clicked(self) -> None:
        """Open Settings dialog; on Save, persist to config + keyring and refresh."""
        from container_tracker.__version__ import __version__ as app_version
        from container_tracker.core.persistence import (
            data_dir,
            get_api_token,
            save_config,
            set_api_token,
        )
        from container_tracker.ui.dialogs import SetupDialog

        dialog = SetupDialog(
            mode="settings",
            initial_company=str(self._config.get("company_name", "") or ""),
            initial_email=str(self._config.get("contact_email", "") or ""),
            initial_api_key_set=bool(get_api_token()),
            app_version=app_version,
            data_folder=str(data_dir()),
        )
        result = dialog.exec()
        if result != dialog.DialogCode.Accepted:
            logger.info("Settings dialog cancelled")
            return
        values = dialog.get_values()
        self._config["company_name"] = values["company"] or ""
        self._config["contact_email"] = values["email"] or ""
        save_config(self._config)
        # api_key contract: None means "keep current keyring entry" (user left the
        # field empty in settings mode). It does NOT mean "clear the key." A real
        # empty-string from the dialog would only reach this branch if the user
        # is in welcome mode or typed and deleted content — both caught by the
        # dialog's validation before accept. Never call set_api_token("") here.
        if values["api_key"] is not None:
            set_api_token(values["api_key"])
        logger.info(
            "Settings saved: company=%r, email=%r, api-key-updated=%s",
            values["company"], values["email"], values["api_key"] is not None,
        )
        self.refresh_from_config()
```

- [ ] **Step 2: Run full tests + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass, mypy clean. (No new tests yet for `_on_settings_clicked` — behavior is covered by the Task 14 end-to-end smoke test.)

- [ ] **Step 3: Commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: wire settings gear to SetupDialog(settings); persist + refresh on save"
```

---

## Task 13: `MainWindow.refresh_from_config()` — update header + linked path after settings save

**Files:**
- Modify: `container_tracker/ui/main_window.py`

After settings save, `company_name` and `excel_path` may have changed. Update the HeaderRow subtitle and LinkedSpreadsheetCard path so the UI reflects new state without restart.

- [ ] **Step 1: Add `refresh_from_config` to `MainWindow`**

Append to the class, after `toggle_dark_mode`:

```python
    def refresh_from_config(self) -> None:
        """Re-read config and update header + linked-spreadsheet card.

        Called after the Settings dialog saves changes. Only updates the
        widgets whose values can change via Settings: company_name (header
        subtitle) and excel_path (linked-spreadsheet path display).
        """
        company = str(self._config.get("company_name", "") or "")
        self._header.set_subtitle(company or "Unconfigured — open Settings")
        excel_path = str(self._config.get("excel_path", "") or "")
        self._linked.set_path(excel_path)
        logger.info("refresh_from_config applied: company=%r, excel=%r", company, excel_path)
```

- [ ] **Step 2: Run full tests + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass, mypy clean.

- [ ] **Step 3: Commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: MainWindow.refresh_from_config() updates header subtitle + linked path"
```

---

## Task 14: End-to-end smoke test

**Files:** none modified.

- [ ] **Step 1: Clean-slate first-run path (manual)**

Rename the config file aside to simulate a fresh install (keyring stays — on this dev machine the v1.0.0 token was detected in earlier checkpoints). If you want a true first-run with no keyring entry either, the keyring entry must be cleared manually — do NOT script that, it's the user's real token.

Bash:

```bash
mv "$APPDATA/ContainerTracker/config.json" "$APPDATA/ContainerTracker/config.json.bak" 2>/dev/null || true
```

Then PowerShell smoke-test:

```powershell
# Use the standard smoke-test pattern from the top of the plan.
# MODULE = "container_tracker"
# Verify: Welcome dialog appears IF is_first_run was True.
# Since keyring has a token, is_first_run is likely False and no dialog appears.
# Expected: MainWindow launches directly.
```

Restore config:

```bash
mv "$APPDATA/ContainerTracker/config.json.bak" "$APPDATA/ContainerTracker/config.json" 2>/dev/null || true
```

- [ ] **Step 2: Settings-dialog launch-and-close (programmatic)**

```bash
python -c "
import sys
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from container_tracker.ui.main_window import MainWindow
from container_tracker.ui.dialogs import SetupDialog

app = QApplication.instance() or QApplication(sys.argv)
mw = MainWindow({
    'company_name': 'TestCorp',
    'contact_email': 'ops@testcorp.com',
    'excel_path': 'C:/tmp/test.xlsx',
    'dark_mode': False,
    'dismissed': [],
})

# Replace dialog.exec with a function that changes company_name and returns Accepted.
original_exec = SetupDialog.exec
def fake_exec(self):
    self._company_input.setText('UpdatedName')
    self._api_key_input.setText('')  # keep current
    self._email_input.setText('new@example.com')
    self._revalidate()
    return self.DialogCode.Accepted
SetupDialog.exec = fake_exec

# Patch persistence so we don't actually write to disk or keyring.
from container_tracker.core import persistence
with patch.object(persistence, 'get_api_token', return_value='existing-token'):
    with patch.object(persistence, 'save_config') as save_mock:
        with patch.object(persistence, 'set_api_token') as set_tok_mock:
            mw._on_settings_clicked()

# Verify config was updated and header/linked reflect the new state.
assert mw._config['company_name'] == 'UpdatedName'
assert mw._config['contact_email'] == 'new@example.com'
assert mw._header.subtitle_text() == 'UpdatedName'
# api_key was empty in fake dialog; set_api_token should NOT have been called.
# (this is the 'keep current' path)
print('PASS: settings save updated config and refreshed header')
"
```

Expected: `PASS: settings save updated config and refreshed header`.

- [ ] **Step 3: Window visibility smoke test**

Run the standard PowerShell pattern from the top of the plan with `MODULE = "container_tracker"`. Verify handle non-zero, title correct, exit 0.

- [ ] **Step 4: Data folder link opens Explorer (spec §5.3 requirement)**

Programmatic verification that clicking the data-folder link in settings mode invokes `os.startfile` with the correct path. We intercept the call rather than actually opening a window to keep the test deterministic:

```bash
python -c "
import sys, os
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from container_tracker.ui.dialogs import SetupDialog
from container_tracker.core.persistence import data_dir

app = QApplication.instance() or QApplication(sys.argv)
expected_path = str(data_dir())

dlg = SetupDialog(
    mode='settings',
    initial_company='TestCorp',
    initial_email='ops@testcorp.com',
    initial_api_key_set=True,
    app_version='1.1.0',
    data_folder=expected_path,
)

opened: list[str] = []
with patch.object(os, 'startfile', create=True, side_effect=lambda p: opened.append(p)):
    dlg._on_data_folder_clicked('folder')

assert opened == [expected_path], f'expected [{expected_path!r}], got {opened!r}'
print(f'PASS: clicking data folder link invokes os.startfile({expected_path!r})')
"
```

Expected: `PASS: clicking data folder link invokes os.startfile(...)`. On non-Windows dev machines, adapt the mock target (`subprocess.Popen`).

- [ ] **Step 5: Full test suite + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all pass, mypy clean.

- [ ] **Step 6: No commit** — pure verification.

---

## CHECKPOINT C — STOP — PHASE 4 COMPLETE

**What's now true:**
- First launch on a clean machine shows the Welcome dialog. Save persists company + email to config and API key to keyring, then opens MainWindow. × on Welcome quits the app before MainWindow appears.
- Settings gear in the header opens `SetupDialog(mode="settings")` pre-populated from config + keyring presence. Save persists changes and refreshes the header subtitle + linked-spreadsheet path. Cancel discards.
- All Phase 3 polish items resolved: dark-mode accent is saturated navy, table column headers fully visible, placeholder buttons grayed out with tooltips, footer renders correctly, stat-card / table data verified consistent.
- `pytest` green on ~185–190 tests. `mypy --strict container_tracker` clean on all source files.

**Ready for Phase 5** — backend wiring (Refresh, Add & Track, Remove Selected, Browse/Create/Open Excel, activity log signal connection).

**Report format for this checkpoint:**
- `pytest -v` pass count.
- `mypy --strict container_tracker` output.
- PowerShell smoke-test result for main app launch.
- Output of the Task 14 Step 2 programmatic settings-save test.
- UX decisions the orchestrator (user) may want to revisit: (i) API key echo mode, (ii) settings-mode "leave empty to keep current" placeholder text, (iii) inline error color using `statRole="delayed"`.
- `git log --oneline -20`.

---

## Self-Review

**1. Spec coverage** (§5.3):

- SetupDialog modal in both modes via `exec()` → Task 7 + Task 12.
- Three fields (Company, API key, Email) → Task 7.
- API key regex `^[0-9a-fA-F-]{30,40}$` → Task 6.
- Email `@` + `.` check → Task 6.
- Live validation, Save disabled until all pass → Task 8.
- Welcome mode: no Cancel, × quits app → Tasks 7 + 10 (closeEvent).
- Settings mode: Cancel discards → Task 7.
- Settings mode shows version, data folder (clickable), GitHub repo link → Task 7.
- API key stored in keyring, config.json never carries `api_key` → Task 11 (uses `persistence.set_api_token`) + Task 12 (same).
- First-run detection gates MainWindow.show → Task 11.
- Settings gear opens Settings dialog → Task 12.
- MainWindow refresh after settings save → Task 13.

**2. Polish coverage** (5 items from user feedback):

- Dark-mode accent washed-out → Task 1.
- Table column headers cut off → Task 2.
- Placeholder buttons look functional → Task 3.
- Footer `&&` rendering → Task 4.
- Stat-card / table data mismatch → Task 5.

**3. Placeholder scan:** grepped for "TBD", "TODO", "implement later", "Similar to Task", "fill in" — none.

**4. Type + signature consistency:**

- `SetupDialog(mode, initial_company, initial_email, initial_api_key_set, app_version, data_folder, github_repo_url)` → defined Task 7; used in Tasks 11 (welcome, no initial_*) and 12 (settings, populated).
- `SetupDialog.get_values() -> dict[str, str | None]` with keys `{"company", "email", "api_key"}` → defined Task 9; consumed Tasks 11, 12, 14.
- `validate_setup_fields(company, api_key, email) -> dict[str, str]` → defined Task 6; called by `SetupDialog._revalidate` in Task 8.
- `API_KEY_PATTERN` and `EMAIL_PATTERN` — defined Task 6, consumed by `validate_setup_fields` in the same task.
- `MainWindow.refresh_from_config()` — defined Task 13; called by Task 12.
- `HeaderRow.set_subtitle(str)` — already defined in Phase 3 Task 6; consumed by Task 13.
- `LinkedSpreadsheetCard.set_path(str)` — already defined in Phase 3 Task 5; consumed by Task 13.
- `persistence.set_api_token`, `persistence.save_config`, `persistence.get_api_token` — defined Phase 1 Task 6; consumed by Tasks 11, 12.

**5. Checkpoint B scope check:** dialogs live in their own module (`container_tracker/ui/dialogs.py`) — no need to touch `main_window.py` or other Phase 3 code during Checkpoint B. Checkpoint A polish items are also all isolated to `theme.py` and `main_window.py`. Checkpoint C is purely wiring — modifies `__main__.py` once and `main_window.py` twice (`_on_settings_clicked` + `refresh_from_config`).

**6. UX decisions flagged for orchestrator review** (user may want to override):

- (a) API key field uses `QLineEdit.EchoMode.Password` (masked) in both modes. Rationale: credentials shouldn't be visible. Alternative: show-toggle button to unmask on request. Default is mask.
- (b) Settings mode, existing key present: field is empty with placeholder "API key is set — leave empty to keep current, or type to replace". Rationale: user can preserve by not typing. Alternative: show masked dots (●●●●). Default is empty-with-placeholder.
- (c) Inline error labels colored with `statRole="delayed"` (muted rust). Rationale: consistent with the design system's status color for errors. Alternative: pure red or an "error" role. Default is reuse `status_delayed`.
- (d) API key "keep current" semantics: empty field in settings mode with an existing keyring entry returns `api_key: None` from `get_values()` — caller treats None as "skip set_api_token call." Rationale: makes "no change" an explicit sentinel rather than guessing. Alternative: always require typing. Default is sentinel.

Flag any of these for pushback during plan review.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-23-pyside6-phase4-dialogs-and-polish.md`.

**Cadence:** subagent-driven, one subagent per checkpoint, orchestrator reports back at each STOP marker. **User reviews between checkpoints for Phase 4 and Phase 5** (per updated cadence for product-judgment phases). Phases 6 and 7 return to autonomous dispatch.

Awaiting plan approval before dispatching Checkpoint A.
