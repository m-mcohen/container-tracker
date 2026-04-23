# Container Tracker — PySide6 Migration Design

**Date:** 2026-04-23
**Status:** Approved — ready for implementation plan
**Target version:** v1.1.0
**Repository:** `https://github.com/m-mcohen/container-tracker`

## 1. Context

Container Tracker is a Windows desktop app that tracks ocean shipping container
ETAs via the ShipsGo v2 API and writes results into a linked Excel spreadsheet.
v1.0.0 is shipping (CustomTkinter, single PyInstaller `.exe`, Inno Setup installer).
One test install in the field; first real client is Ken Gabbay Coffee.

The migration exists to escape CustomTkinter's visual ceiling. The current UI
reads as "themed tkinter"; the goal is "professional desktop app." Backend
behavior is correct and shipping — only the UI layer is being rewritten.

**Hard constraint:** no new features, no external behavior changes. Same feature
set as v1.0.0, same config on disk, same keyring entries, same installer AppId,
same update-check URL. The migration is internal.

## 2. Scope

### In scope

- Replace CustomTkinter UI with PySide6.
- Extract the real backend (currently embedded in `container_tracker_gui.py`)
  into a clean `core/` package with testable modules.
- Rebuild the design system from the palette, typography, spacing, and radius
  constants already decided in the brief — applied as a single generated QSS
  stylesheet, live-switchable between light and dark modes.
- Preserve config.json layout, keyring service/user names, data directory,
  update-check URL, installer AppId, and build-output filename.
- Bump version to **v1.1.0**.

### Out of scope

- Changes to ShipsGo API handling (same endpoints, same auth header, same
  response shapes).
- Changes to the linked-Excel I/O format.
- Legacy migrations. Installed base is one test install; pre-pivot migrations
  (`KenGabbayTracker` keyring entry, `Ken Gabbay Coffee\KenGabbayTracker` APPDATA
  folder, legacy `api_key` field in config.json) are all being dropped.
- `container_tracker.py`, the obsolete standalone CLI. Dead code; no imports
  reference it; deleted at end of Phase 1. Git history preserves it.
- QML. Qt Designer `.ui` files. QSS preprocessors. All rejected — pure-Python
  widget construction is more readable and easier to edit in-context.
- Any bump past v1.x. This stays v1.1.0; a future "v2.0" decision is separate.

## 3. Architecture

### 3.1 Package layout

```
container_tracker/
  __version__.py           # single source of truth: __version__ = "1.1.0"
  __main__.py              # entry point; QApplication bootstrap; first-run wiring; logging setup
  core/
    __init__.py
    api.py                 # ShipsGoClient, extract_fields, SCAC map
    excel.py               # read/write linked .xlsx (config.excel_path)
    persistence.py         # data dir, config.json, keyring, tracking_data.json
    updates.py             # GitHub releases check
    status.py              # status normalization, delay calc, sailing/arrived/delayed buckets
  ui/
    __init__.py
    theme.py               # palette, typography, spacing, radius; QSS generator
    main_window.py         # App main window
    dialogs.py             # SetupDialog (welcome + settings modes)
    widgets.py             # StatCard, UpdateBanner, ActivityLog, LinkedSpreadsheetCard
    model.py               # ContainerTableModel (QAbstractTableModel)
```

Rationale: splits the 1,406-line monolith into ~10 focused files. Each module
has a single responsibility and is testable in isolation. Strict `mypy` on
`core/` where Qt types are absent; relaxed on `ui/`.

### 3.2 Threading model

- UI thread owns all widgets and all `QAbstractItemModel` mutations.
- `QThreadPool.globalInstance()` executes `QRunnable`-wrapped background work
  (Refresh All, Add & Track, update check).
- Runnables communicate back to the UI via `QObject` signals with
  `Qt.ConnectionType.QueuedConnection` (the default when sender and receiver
  live on different threads).
- No `QThread` subclasses. `QRunnable` + pool is simpler for the "fan out N
  HTTP calls, stream results back" pattern we have.
- No Python `threading.Thread` + `root.after()` marshaling; that's the
  CustomTkinter approach we're leaving behind.

### 3.3 State ownership

- `MainWindow` owns application state: the config dict, the tracking-data dict,
  the current theme, the `ShipsGoClient` instance.
- Child widgets receive what they need via constructor arguments or connect to
  `MainWindow` signals. No module-level globals, no singletons, no app-wide
  event bus.
- `QApplication` is constructed once in `container_tracker/__main__.py` and
  passed nothing application-specific. Running `python -m container_tracker`
  launches the app in development; PyInstaller points at the same module.

### 3.4 Logging

- No `logging.basicConfig` at import time in any module. Logging is configured
  exactly once, in `container_tracker/__main__.py`, before `MainWindow` is
  constructed. Every other module does `logger = logging.getLogger(__name__)`
  and assumes the root logger is already wired.
- Format: `%(asctime)s [%(levelname)s] %(message)s`, preserving the v1.0.0
  output shape (e.g. `2026-04-23 04:05:33,524 [INFO] ...`). Default
  `asctime` already uses the comma-millisecond form we want.
- Two handlers attached at the root:
  1. `FileHandler(log_path())` — writes to `%APPDATA%\ContainerTracker\tracker.log`.
  2. `QtLogHandler(logging.Handler)` — a custom subclass defined in
     `ui/widgets.py`. Its `emit()` method marshals the formatted record to the
     UI thread via a `Signal(str)` owned by the handler. `ActivityLog`
     connects to that signal and appends to its `QPlainTextEdit`.
- This means the activity log widget is a **log sink**, not a separate
  message bus. Any module that calls `logger.info("...")` appears in the log
  pane automatically, which matches v1.0.0 behavior (startup messages,
  migration results, update-check outcomes, and per-container refresh lines
  all flow through the same path).
- Third-party library noise is suppressed by setting `urllib3` and `requests`
  loggers to `WARNING`.

### 3.5 Testing strategy

- **Unit tests** (pytest) for pure modules:
  - `core/api.py` — use `responses` (or `httpx.MockTransport`-equivalent) to
    mock ShipsGo v2 endpoints. Cover 200, 409, 402, 404, 401, timeout, and
    malformed JSON.
  - `core/status.py` — pure logic; table-driven tests for `normalize_status`,
    `compute_delay_days`, `bucket_counts`.
  - `core/updates.py` — mock `requests.get` to `api.github.com`; cover
    newer/older/equal/malformed/offline cases.
- **Integration tests** using `tmp_path`:
  - `core/excel.py` — round-trip read/write against a generated `.xlsx`;
    verify missing-column error, unexpected-column tolerance.
  - `core/persistence.py` — round-trip config + tracking data; verify
    `api_key` never appears in config.json even if passed in.
- **Static checks:** `mypy --strict` passes on `core/`. Relaxed on `ui/`
  where Qt stubs are thin.
- **UI testing:** manual smoke tests against the §10 success-criteria list.
  No automated UI test harness in v1.1.0 — the check list is the contract.
- **CI out of scope** for this migration. Tests run locally via `pytest`
  and `mypy` invocations; a GitHub Actions pipeline can follow in a later
  version if wanted.

## 4. Core modules

### 4.1 `core/api.py`

- `ShipsGoClient(token: str)` — same interface as the class in the current GUI
  file (create_shipment, list_shipments, get_shipment, get_carriers). Preserves
  v2 base URL `https://api.shipsgo.com/v2`, auth header `X-Shipsgo-User-Token`,
  409/402/404 handling.
- `extract_fields(shipment: dict) -> dict` — pulls status, vessel, POL, POD,
  ETA, ETD, carrier, transit_pct, original_eta, delay_days from the v2
  response. Handles the `{"shipment": {...}}` wrapper and the
  `containers → movements → vessel` nesting.
- `CARRIER_SCAC_MAP` constant and `resolve_scac(shipping_line: str) -> str`.
- **Exceptions:**
  - `ShipsGoAuthError(Exception)` — raised on HTTP **401**. Distinct from
    `requests.HTTPError` so the UI layer can catch it specifically, show a
    "Your ShipsGo API key is invalid — open Settings to update it" modal,
    and offer a button that opens the Settings dialog. No silent failure.
  - Other non-ok statuses still raise `requests.HTTPError` as today. 409 is
    treated as "already tracked" (returned as a structured result, not an
    exception), matching current behavior.

No module-level side effects. No `load_dotenv`. No `logging.basicConfig`. The
module only defines classes and functions; the caller wires up logging and
passes in the token.

### 4.2 `core/persistence.py`

- `data_dir() -> Path` — `%APPDATA%\ContainerTracker\` on Windows; equivalent
  on other platforms (for dev; prod is Windows-only).
- `config_path() -> Path`, `tracking_data_path() -> Path`, `log_path() -> Path`.
- `load_config() -> dict`, `save_config(config: dict) -> None` — manual JSON
  with keys `company_name`, `contact_email`, `excel_path`, `dark_mode`,
  `dismissed`. `api_key` is never written here.
- `get_api_token() -> str`, `set_api_token(token: str) -> None` — wrap
  `keyring.get_password` / `keyring.set_password` for service
  `ContainerTracker_shipsgo_api`, user `default`. Catch and log failures;
  return empty string on read failure.
- `is_first_run(config: dict) -> bool` — true iff `company_name` missing AND
  no keyring token.
- `load_tracking_data() -> dict`, `save_tracking_data(db: dict) -> None`.

No legacy migrations. Installed base is one test install; we ship v1.1.0 over
a config that already has the new layout.

### 4.3 `core/excel.py`

- `read_container_list(path: Path) -> list[dict]` — reads the user's linked
  `.xlsx`, returns rows with `container_number`, `shipping_line`, `reference`.
- `write_tracking_report(path: Path, db: dict) -> None` — writes tracking data
  **directly into the user's linked `.xlsx`** (single-file model, same as
  v1.0.0). Excel export keeps POL and POD as separate columns.
- `create_template(path: Path) -> None` — writes a blank `.xlsx` with the
  required headers and links it (caller sets `config.excel_path`).

**Robustness posture:** best-effort reads. Unexpected columns are ignored.
A missing container-number column raises a clear `ExcelFormatError` whose
`str()` is displayed verbatim by the UI (e.g. "Couldn't find a column named
'Container #' in `<path>`. Expected headers: Container #, Carrier, Reference.").
The module does not attempt to reinterpret merged cells, named ranges, or
formula values beyond what `openpyxl` returns natively; if a user's workbook
is shaped weirdly enough that openpyxl can't parse it, the error surfaces to
the UI rather than being papered over.

### 4.4 `core/updates.py`

- `UpdateInfo` frozen dataclass: `version: str`, `html_url: str`.
- `check_for_update(current_version: str, timeout: float = 5.0) -> UpdateInfo | None`
  — GETs `https://api.github.com/repos/m-mcohen/container-tracker/releases/latest`,
  strips leading `v` from `tag_name`, compares with `packaging.version.parse`.
  Returns `UpdateInfo` if remote is newer, else `None`. All failures —
  offline, 403, malformed, 404, timeout — log one line and return `None`.

### 4.5 `core/status.py`

- `normalize_status(raw: str) -> Literal["SAILING", "ARRIVED", "DELAYED", "PENDING", "UNKNOWN"]`
  — maps ShipsGo's status strings to our buckets.
  - `SAILING` for anything matching `sailing` or `en_route`.
  - `ARRIVED` for `arrived`, `discharged`, `delivered`, `gate_out`.
  - `PENDING` for `booked`, `new`, `""`.
  - `UNKNOWN` otherwise.
- `compute_delay_days(original_eta: str, current_eta: str) -> int` — diff in
  days; positive = delayed.
- `bucket_counts(db: dict) -> dict[str, int]` — returns
  `{"total", "sailing", "arrived", "delayed"}`.
  - `delayed = count where normalize_status == SAILING AND delay > 0`
    (**decision: delay-while-sailing only; arrived-with-delay is not
    actionable**).

## 5. UI layer

### 5.1 Theme

`ui/theme.py`:

- `LIGHT_PALETTE` and `DARK_PALETTE` as `dict[str, str]` keyed exactly as the
  brief specifies. Status delayed is **muted rust** (`#B05A4D` light / `#D48276`
  dark); the pure-red `#D32F2F` in the current code is treated as a bug that
  this migration fixes.
- `TYPOGRAPHY`, `SPACING`, `RADIUS` dicts per the brief.
- `build_stylesheet(palette: dict) -> str` — returns a QSS string covering
  `QWidget`, `QPushButton` (three variants: primary CTA pill, secondary ghost,
  destructive), `QLineEdit`, `QComboBox`, `QTableView`, `QHeaderView`,
  `QFrame[role="card"]`, `QFrame[role="stat-card"]`, etc. Uses property
  selectors (`QPushButton[variant="primary"]`) so variants live as widget
  properties, not subclasses.
- **Theme toggle mechanism (decision):** regenerate the full stylesheet from
  the opposite palette and apply it via
  `QApplication.instance().setStyleSheet(...)`. Rejected alternative: a
  `setProperty("theme", "dark")` dynamic-property approach with QSS attribute
  selectors. Rationale: a theme swap changes every color value, not a handful
  of discrete variants. The property-selector approach would double every
  color rule in QSS and require a `style().unpolish()/polish()` pass on every
  widget to re-evaluate styles. Regeneration costs microseconds and keeps the
  stylesheet readable — one palette dict in, one string out. The
  `[variant="primary"]` pattern stays for button variants, where the discrete
  set is natural; theme is orthogonal and handled by rebuild.
- No per-widget `setStyleSheet` calls. All styling flows through the
  application-level stylesheet.
- Primary family **Segoe UI Variable** with fallback **Segoe UI**; mono
  **Cascadia Code** with fallback **Consolas**.

### 5.2 Main window

Widgets, top to bottom:

1. **Update banner** (hidden by default). Slot managed by `MainWindow`.
   Shows when `core/updates.check_for_update` returns a result. Click area
   opens `html_url` in default browser via `webbrowser.open`. × dismisses for
   the session only.
2. **Header row:** app title "Container Tracker" (18pt bold), subtitle
   `company_name` below. Right side: settings gear button, dark-mode toggle.
3. **Linked spreadsheet card** (outlined, `surface_card`): label, current path
   (or "No file linked" in `text_tertiary`), three buttons (Browse…, Create
   Template, Open in Excel). Ghost-button styling.
4. **Stat cards row:** four outlined cards in a `QHBoxLayout`. Label above,
   28pt bold number below. Label color `text_secondary`; number color by
   bucket (Tracked = `text_primary`, Sailing = `status_sailing`, Arrived =
   `status_arrived`, Delayed = `status_delayed`).
5. **Action row:** "Refresh All ETAs & Update Excel" primary-CTA pill (left,
   widens or wraps to two lines rather than truncating — the "Update Excel"
   signal is non-negotiable for non-technical users), "Remove Selected"
   destructive button, then Add field (container number `QLineEdit`), Carrier
   `QComboBox`, "Add & Track" primary-CTA pill.
6. **Container table:** `QTableView` + `ContainerTableModel` (`QAbstractTableModel`).
   Columns: Container #, Carrier, Status, Original ETA, Current ETA, Delay,
   Route (single cell, format `POL → POD`), Vessel, Transit %. Sortable via
   `QSortFilterProxyModel`. Multi-select rows. Row status color comes from the
   model's `Qt.ForegroundRole` for the Status column only — no whole-row
   fills, no zebra striping.
7. **Activity log pane:** `QPlainTextEdit` (read-only, `surface_subtle`
   background, Cascadia Code 11pt). Receives `str` messages via a
   `Signal(str)`-connected slot wired up in §3.4. Worker threads
   (`QRunnable`s) never call widget methods directly; they emit signals that
   the Qt event loop delivers on the UI thread via `QueuedConnection`.
8. **Footer:** left "Powered by ShipsGo API"; right "Refreshes are free &
   unlimited • All times EST".

### 5.3 Dialogs

`SetupDialog(QDialog)` serves both Welcome (first-run) and Settings modes:

- Constructor takes `mode: Literal["welcome", "settings"]` and current values.
- Fields: Company name, ShipsGo API key (UUID regex `^[0-9a-fA-F-]{30,40}$`),
  Contact email (`@` and `.` check).
- Live validation: Save disabled until all three pass.
- Welcome mode: no Cancel; `closeEvent` triggers `QApplication.quit()`.
- Settings mode: Cancel discards; shows read-only version, data-folder link
  (opens Explorer via `os.startfile`), and GitHub repo link.
- Modal via `dialog.exec()`, never `dialog.show()`.

### 5.4 Table model details

`ContainerTableModel(QAbstractTableModel)`:

- Internal storage: `list[dict]` of tracking records.
- `data(index, role)`:
  - `Qt.DisplayRole` returns formatted strings (dates as `YYYY-MM-DD`, delay
    with `+` prefix, transit as `NN%`).
  - `Qt.ForegroundRole` on Status column returns the palette color for
    normalized bucket.
  - `Qt.TextAlignmentRole` right-aligns Delay and Transit %.
- `headerData` returns column names.
- `sort()` delegates to `QSortFilterProxyModel` wrapping the model. The
  proxy's `lessThan` is overridden so sorting the **Status** column uses
  bucket priority, not alphabetical: `DELAYED < SAILING < ARRIVED < PENDING
  < UNKNOWN` (ascending puts what's late first). Shipping operators care
  about what's slipping; alphabetical sort would hide that. All other
  columns use default comparison. Initial sort on launch: Status ascending.
- Mutation API: `set_records(records)`, `remove_rows(indexes)`. Both fire
  `beginResetModel` / `endResetModel` (simple; table size is tiny).

## 6. First-launch flow

1. `container_tracker/__main__.py` configures logging (§3.4) and constructs
   `QApplication`.
2. Loads config (empty dict if missing).
3. `is_first_run(config)` check. If true:
   - `MainWindow` is constructed but not shown.
   - `SetupDialog(mode="welcome")` runs modal. On Save, writes config + keyring.
     On × close, `QApplication.quit()`.
4. `MainWindow.show()`.
5. Background: update check runs in `QThreadPool`. On result, banner slot
   populates.

## 7. Packaging

### 7.1 PyInstaller

- `--onefile --windowed --icon app.ico --add-data "app.ico;." --name ContainerTracker`
- `--collect-all PySide6` — PySide6's plugins (platforms, imageformats, styles)
  must ship or the app fails at launch on machines without Qt installed.
- `--collect-all keyring` — same reason as v1.0.0; PyInstaller otherwise
  misses `keyring.backends.Windows`.
- Output: `dist/ContainerTracker.exe`, single file, expected ~40–60 MB
  (PySide6 is heavier than CustomTkinter; that's the cost of Qt).

### 7.2 Inno Setup installer

- `installer.iss` updated:
  - `AppVersion` → `1.1.0`.
  - `AppId` **unchanged** (`{{867023ab-b5bc-48d0-8093-961789d93187}}`) — this
    is what Windows uses to identify upgrades. Changing it would make v1.1.0
    install as a new product alongside v1.0.0.
  - `[Files]` section adds `ATTRIBUTIONS.md` alongside the existing
    `README_CLIENT.md` (with `isreadme` flag on README).
  - `OutputBaseFilename` continues to template from `AppVersion`, producing
    `ContainerTracker_Setup_v1.1.0.exe`.
- Install path (`{localappdata}\Programs\ContainerTracker`) unchanged.
- Privileges (`lowest`) unchanged — no admin prompt.

### 7.3 Attribution

Icon attribution preserved in both `README_CLIENT.md` and `ATTRIBUTIONS.md`:

> Container icons created by Iconjam - Flaticon
> (https://www.flaticon.com/free-icons/container)

## 8. Phased delivery

| # | Phase | Effort | Deliverable |
|---|-------|--------|-------------|
| 1 | Scaffold + backend extraction | 6–10h | Package layout exists; `core/` modules extracted and unit-testable; blank PySide6 window launches, reads config, writes log line; `container_tracker.py` deleted. |
| 2 | Design system (theme + QSS) | 3–5h | `theme.py` + QSS generator; light/dark toggle; test harness showing every styled widget. |
| 3 | Main window layout (no functionality) | 5–8h | Full window structure rendered with sample data; dark mode works; no backend wiring. |
| 4 | Welcome + Settings dialogs | 3–5h | First-run flow end-to-end on clean machine; Settings opens, edits, saves. |
| 5 | Wire functionality | 6–10h | Refresh, Add & Track, Remove, Browse/Create/Open Excel, stats, table population, log output — all real via `QThreadPool`. |
| 6 | Update check + banner | 1–2h | GitHub releases check runs at launch; banner shows and dismisses correctly. |
| 7 | Packaging + installer | 3–6h | `ContainerTracker_Setup_v1.1.0.exe` produced; clean-install smoke test passes. |
| 8 | Release | — | User-owned. |

**Total: 27–46 hours** single developer.

## 9. Known edge cases and gotchas

- **First-run dialog must be modal.** Use `dialog.exec()`, not `dialog.show()`.
  Verified on clean machine (empty `%APPDATA%\ContainerTracker\`, empty keyring)
  in Phase 4.
- **PyInstaller + keyring.** v1.0.0 uses `--collect-all keyring`. Keep it.
- **PyInstaller + PySide6.** Must use `--collect-all PySide6` or the app crashes
  at launch on machines without Qt. This is the standard idiom per PyInstaller
  docs; confirm once during Phase 7 before shipping.
- **AppId GUID is load-bearing.** Do not regenerate. If changed, v1.0.0
  installs won't be upgraded — v1.1.0 will install alongside them.
- **The app.ico file.** Preserve the existing multi-resolution `.ico` at repo
  root (16/32/48/64/128/256). Referenced by PyInstaller (`--icon` + `--add-data`)
  and Inno Setup (`SetupIconFile`, `UninstallDisplayIcon`).
- **CustomTkinter window-lifecycle bug** (withdrawn unmapped root) is
  tkinter-specific. PySide6 should not reproduce it; no preemptive fix needed.
  Be alert to any "first launch, window invisible" reports during Phase 4
  testing.

## 10. Success criteria

A build is ready to ship when all of the following hold on a clean Windows
machine with no prior install:

1. `ContainerTracker_Setup_v1.1.0.exe` installs without admin prompt.
2. First launch shows the Welcome dialog; app quits cleanly if user closes it.
3. Saving the Welcome dialog writes `company_name` + `contact_email` to
   `%APPDATA%\ContainerTracker\config.json` and the API key to Windows
   Credential Manager under service `ContainerTracker_shipsgo_api`, user
   `default`. **`api_key` does not appear in config.json.**
4. Main window renders with the design system applied; dark-mode toggle
   switches palette live.
5. Browse → pick an `.xlsx` with container numbers → Refresh All →
   spreadsheet updated with tracking data, stat cards populated, activity log
   shows per-container status lines.
6. Add & Track registers a new container (or reports 409 / 402 / 404
   gracefully), then refresh pulls its data.
7. Remove Selected removes rows from tracking.
8. Settings dialog opens, shows current values, saves changes, reflects in
   main window.
9. Update check runs silently at launch; banner appears if a newer release is
   faked in GitHub Releases; × dismisses for the session; click opens release
   page in browser.
10. Close and relaunch preserves all config and tracking data.
11. With a deliberately wrong API key in keyring, Refresh/Add surfaces a
    **modal dialog** ("Your ShipsGo API key is invalid — open Settings to
    update it") with an "Open Settings…" button, not a silent log line or a
    raw traceback. `ShipsGoAuthError` is what drives this path.

## 11. Open questions

None. All eight blocker questions from the review were answered by the user on
2026-04-23 and folded into this spec. Any new questions that surface during
implementation will be raised in the implementation plan, not here.
