# Developer Notes — Container Tracker

Quick reference for making targeted changes. If you know what you want to change, jump straight to the **Spot-edit index** below. If you want to understand why something works a certain way, read the relevant section.

---

## How the app runs (startup sequence)

```
python -m container_tracker
  └─ container_tracker/__main__.py       calls app.main()
       └─ container_tracker/app.py       runs migrations, creates pywebview window
            ├─ core/config.py  boot()    logging → folder migrations → keyring migration
            ├─ bridge.py  Bridge()        Python API exposed to JS as window.pywebview.api
            └─ web/index.html            loads styles.css and app.js
                 └─ app.js               fires pywebviewready → calls Bridge methods → renders
```

The window is 1280×820, minimum 1024×720. In dev (`python -m container_tracker`) DevTools are enabled — right-click → Inspect works. In the built `.exe` DevTools are off.

---

## Spot-edit index

| I want to change… | Edit this file | Where |
|---|---|---|
| Any visible text, button labels, page structure | `container_tracker/web/index.html` | Find the element by its text or `id` |
| Colors, fonts, spacing, layout | `container_tracker/web/styles.css` | CSS custom properties at `:root` for global tokens |
| Table row content or layout | `container_tracker/web/app.js` | `render()` function — the template literal in `TBODY.innerHTML = filtered.map(...)` |
| Status badge colors/labels | `app.js` | `statusClass()` and `statusLabel()` functions |
| Filter chip behavior | `app.js` | The `.toolbar .chip` click listener |
| KPI card numbers | `app.js` | `renderStats()` function |
| Refresh behavior / what happens after Refresh | `app.js` | `handleRefresh()` function |
| Add container behavior | `app.js` | `handleAddSubmit()` function |
| Archive / restore behavior | `app.js` | TBODY click listener, `data-action="restore"` branch |
| Settings save logic | `app.js` | `handleSaveSettings()` function |
| Theme switch | `app.js` | `setTheme()` function |
| What data gets sent to JS from Python | `container_tracker/bridge.py` | `_to_row()` for container rows, `get_settings()` for settings |
| How containers are refreshed from ShipsGo | `bridge.py` | `refresh_all()` and `refresh_one()` |
| How a container is added | `bridge.py` | `add_container()` |
| How archive/restore work | `bridge.py` | `archive_container()` and `restore_container()` |
| Which fields get written to Excel | `container_tracker/core/excel.py` | `TRACKING_COL_MAP` dict at the top of the file |
| Excel cell colors (status, delay) | `core/excel.py` | `update_excel_with_tracking()` — the `sc` dict and the delay block |
| Excel column header names | `core/excel.py` | Keys of `TRACKING_COL_MAP` |
| How the app finds the Container column in Excel | `core/excel.py` | `find_container_column()` |
| The carrier list in dropdowns | `container_tracker/core/constants.py` | `CARRIER_NAMES` list |
| Carrier → SCAC code mapping | `core/constants.py` | `CARRIER_SCAC_MAP` dict |
| ShipsGo API base URL | `core/constants.py` | `API_BASE` |
| App version (shown in title bar + update check) | `core/constants.py` | `__version__` (also update `installer.iss AppVersion`) |
| App name | `core/constants.py` | `APP_NAME` and `APP_SHORT_NAME` |
| How ShipsGo API calls are made | `container_tracker/core/api.py` | `ShipsGoClient` class |
| How the ShipsGo response is parsed into fields | `container_tracker/core/status.py` | `extract_fields()` function |
| Where user data is stored | `container_tracker/core/config.py` | `DATA_DIR`, `CONFIG_FILE`, `TRACKING_DB_FILE` |
| API key storage | `container_tracker/core/credentials.py` | `get_api_token()` / `set_api_token()` |
| Window size / title | `container_tracker/app.py` | `webview.create_window(...)` call |

---

## File-by-file breakdown

### `container_tracker/app.py` — Window and startup

Single responsibility: run migrations, create the window, start the event loop.

Key things to know:
- `_web_root()` resolves the `web/` folder path. In dev it's `Path(__file__).parent / "web"`. In the built `.exe` PyInstaller unpacks assets into `sys._MEIPASS`, so it becomes `Path(sys._MEIPASS) / "container_tracker" / "web"`. If you add new asset files to `web/`, they will be bundled automatically because `build.bat` uses `--add-data "container_tracker/web;container_tracker/web"`.
- `debug=True` in dev (DevTools on). `debug=False` in the frozen `.exe`.
- `js_api=bridge` is how `window.pywebview.api` becomes available in JS. Every public method on the `Bridge` class becomes callable from JS.

---

### `container_tracker/web/index.html` — All HTML structure

Every visible element lives here. There are two main views (sections with class `view`) and a set of modals:

| Element | `id` | Purpose |
|---|---|---|
| Dashboard view | `view-dashboard` | Main shipments table; is-active on load |
| Settings view | `view-settings` | Settings cards; shown when gear icon clicked |
| Add container modal | `modal-add` | Opened by adding `.modal-add-open` to `#app` |
| Archive modal | `modal-archive` | Single-container archive confirm |
| Bulk archive modal | `modal-bulk-archive` | Multi-container archive confirm |
| Register unmatched modal | `modal-register-unmatched` | Batch-register Excel-discovered CNs |
| Update banner | `update-banner` | `hidden` by default; JS unhides when new version found |
| Unmatched notice | `notice-unmatched` | `hidden` by default; JS unhides after refresh |
| Excel write failed notice | `notice-excel-write-failed` | `hidden` by default |
| Excel missing notice | `notice-excel-missing` | `hidden` by default |

**View routing** — any element with `data-view="X"` navigates to view X when clicked. The gear button uses `data-view="settings"`. The brand logo uses `data-view="dashboard"`. This is wired in `app.js`'s `showView()` with a `querySelectorAll("[data-view]")` listener.

**Modal state** — modals are toggled by adding/removing CSS classes on `#app` (e.g. `app.classList.add("modal-add-open")`). The CSS then uses `.modal-add-open #modal-add { display: flex }` to show the correct overlay.

**Two-input password pattern** — the API key field has two parallel inputs:
- `#settings-token` (type=`password`) — visible by default
- `#settings-token-visible` (type=`text`) — hidden by default via `style="display:none"`

WebView2 blocks dynamic `.type` changes on password inputs, so swapping `display` is the workaround. Both inputs are kept in sync via JS event listeners so `save_settings` can read whichever is currently shown.

**The `[hidden]` rule is load-bearing.** `styles.css` contains `[hidden] { display: none !important; }`. All JS that hides elements should set `.hidden = true` rather than `.style.display = "none"`. The notices and banners all use the `hidden` attribute.

---

### `container_tracker/web/styles.css` — All visual styling

CSS custom properties on `:root` (and `[data-theme="dark"]`) are the single source of truth for colors. Change one variable and it propagates everywhere.

Key variables:
- `--accent` — blue primary color (`#2563eb`)
- `--bg`, `--bg-2`, `--bg-3` — background layers (lightest to darkest panel)
- `--ink-1`, `--ink-2`, `--ink-3` — text (primary, secondary, muted)
- `--border` — border color
- `--danger` — red for destructive actions

Status chip colors are defined on `.chip-status.sailing`, `.chip-status.delayed`, etc. The dot and border are both set there.

Dark mode is activated by `[data-theme="dark"]` on `<html>`. The theme switch button (`#theme-switch`) toggles this via `setTheme()` in `app.js`.

---

### `container_tracker/web/app.js` — All UI behavior

Single large script that runs on page load inside a top-level IIFE. Key sections in order:

**Bridge shim** (top of file) — thin wrappers around `window.pywebview.api.*`. Every Python bridge method has a one-liner here. If you add a new bridge method in Python, add a matching line here. Never call `window.pywebview.api.X()` directly elsewhere in the file — typos there fail silently.

**Toast helpers** — `showError(msg)` and `showInfo(msg)` show dismissible top-right toasts. Auto-dismiss after 8 seconds.

**Banner helpers** — `showUnmatchedBanner(cns)`, `showExcelWriteFailedBanner()`, `showExcelMissingBanner()` and their hide equivalents. Toggle the `hidden` attribute on the banner elements in the notifications stack.

**`ROWS`** — the in-memory container array. Populated by `Bridge.list_containers()` on startup and after every refresh. `render()` reads it. It's a plain `let` — reassignment (e.g. `ROWS = await Bridge.list_containers()`) is how data updates propagate; there's no subscriber system.

**`statusClass(row)`** — maps a row's status string + delayVal to a CSS class name. One special rule: a SAILING row with `delayVal > 0` returns `"delayed"` so it shows up red even though its status is SAILING. If you add a new status, add it here and in `statusLabel()`.

**`render()`** — the only function that writes to the DOM. Calls `renderStats()` then rebuilds `TBODY.innerHTML` from scratch. Filtering (by active chip + search query) and sorting both happen here. The table row template is a template literal inside `TBODY.innerHTML = filtered.map(r => ...)`.

**`renderStats()`** — recomputes all KPI card numbers, chip counts, and the header container count. Called at the top of every `render()`. Archived rows are excluded from all counts except the Archived chip's count.

**`loadInitialData()`** — fires on `pywebviewready` (the pywebview event that signals `window.pywebview.api` is ready). Calls `Bridge.list_containers()`, `Bridge.get_settings()`, and `Bridge.list_carriers()` in sequence.

**`handleRefresh()`** — calls `Bridge.refresh_all()`, then re-fetches `ROWS`, re-renders, and handles all the post-refresh banners (unmatched CNs, Excel write failure, Excel missing).

**`handleAddSubmit()`** — calls `Bridge.add_container(cn, carrier)`. Handles three distinct error cases: out of credits (global toast, close modal), already tracked locally (inline error, keep modal open), any other error (inline error, keep modal open).

**`showView(name)`** — the view router. Removes `is-active` from all `.view` elements, then adds it to `#view-<name>`. Adding a new view requires: (1) a `<section class="view" id="view-X">` in HTML, (2) a `data-view="X"` trigger somewhere.

**TBODY click delegation** — a single listener on `#shipments-tbody` handles all row action buttons via `e.target.closest('[data-action="X"]')`. Actions: `refresh` (per-row refresh), `more` (context menu), `restore` (unarchive).

**Row context menu** (`#row-menu`) — a hidden `div` that's positioned absolutely when the "more" button is clicked. Contains "Copy container number", "Refresh this container", and "Archive…".

---

### `container_tracker/bridge.py` — Python ↔ JS API

The `Bridge` class is instantiated once in `app.py` and passed to pywebview as `js_api`. Every public method becomes callable from JS as `await window.pywebview.api.methodName(args)`.

**`_to_row(cn, rec)`** — translates one flat `tracking_data.json` record into the JS ROWS shape. This is the mapping between Python field names and JS field names:

| JS key | Python source |
|---|---|
| `cn` | dict key (container number) |
| `carrier` | `rec["carrier"]` or `rec["shipping_line"]` (legacy fallback) |
| `scac` | `rec["scac"]` or resolved from carrier name |
| `status` | `rec["status"].upper()` |
| `eta` | `rec["eta"]` |
| `orig` | `rec["original_eta"]` |
| `delay` | `rec["delay_days"]` (formatted string, e.g. "+7 days") |
| `delayVal` | integer parsed from delay string; positive=late, negative=early, 0=on-time, None=unknown |
| `pol` | `rec["pol"]` |
| `pod` | `rec["pod"]` |
| `vessel` | `rec["vessel"]` |
| `pct` | `rec["transit_pct"]` as int 0–100, or `None` |
| `archived` | `bool(rec.get("archived"))` |

**`refresh_all()`** — three-phase refresh:
1. Read CNs from linked Excel workbook → merge new CNs into DB as stubs, drop CNs removed from Excel (skips archived rows)
2. `list_shipments()` to build a CN → shipment ID map
3. Per-container `get_shipment(sid)` loop → `extract_fields()` → update DB record
Then writes `tracking_data.json` and writes back to Excel. Returns a dict with `updated`, `failed`, `unmatched`, `excel_rows_updated`, `excel_read_failed`, `excel_write_failed`, `excel_missing`.

**`add_container(cn, carrier)`** — registers with ShipsGo (`create_shipment`), writes to local DB, appends the row to the linked workbook. Returns `ok`, `was_existing` (HTTP 409 = already on account, not a failure), `container` (the new row), `excel_write_failed`.

**`archive_container(cn)`** — sets `rec["archived"] = True` in the DB, deletes the row from the linked workbook via `remove_container_row()`. The row stays in `tracking_data.json` so the Archived view can show it. `refresh_all()`'s Excel diff skips archived rows so they don't get re-added.

**`restore_container(cn)`** — sets `rec["archived"] = False`, re-appends the row to the workbook with all existing tracking data (via `append_container_row(record=rec)`).

**Error contract** — mutating methods never raise. They return `{ok: bool, error: str|None, ...}`. JS checks `result.ok` and routes to toast or inline error accordingly.

---

### `container_tracker/core/api.py` — ShipsGo HTTP client

`ShipsGoClient` wraps three ShipsGo v2 endpoints:

| Method | Endpoint | Used for |
|---|---|---|
| `create_shipment(cn, scac)` | `POST /v2/ocean/shipments` | Adding a container (costs a credit) |
| `list_shipments(take=100)` | `GET /v2/ocean/shipments` | Building the CN→shipment-ID map during refresh |
| `get_shipment(sid)` | `GET /v2/ocean/shipments/{sid}` | Fetching updated data for one container |
| `delete_shipment(sid)` | `DELETE /v2/ocean/shipments/{sid}` | Not currently called from the UI |

HTTP 409 from `create_shipment` = "already on your account" → treated as success, returns `{"already_exists": True}`. HTTP 402 = out of credits → returns `{"error": "NOT_ENOUGH_CREDITS"}`. Any other non-2xx → `raise_for_status()` propagates.

The token is sent as `X-Shipsgo-User-Token` header.

---

### `container_tracker/core/status.py` — API response parsing

**`extract_fields(shipment)`** — the canonical ShipsGo v2 → flat dict parser. Takes a raw `get_shipment()` response (which may be wrapped as `{"message":…, "shipment":{…}}` — the function unwraps it). Produces:

```
status, vessel, pol, pod, eta, etd, carrier, scac,
transit_pct, original_eta, delay_days
```

Key behaviors:
- **Vessel name** — walks `containers[0].movements` in *reverse* and takes the first movement that has a non-empty vessel name. Reverse walk ensures you get the most recent vessel, not the first one in history.
- **Delay** — computed from `(eta - original_eta).days`. Positive = late (`"+N days"`), negative = early (`"N days (early)"`), zero = `"On time"`, either date missing = `""`.
- **Route** — `route.port_of_loading` / `route.port_of_discharge`. Legacy fallbacks: `route.origin` / `route.destination`.
- **Dates** — all dates are stripped to `YYYY-MM-DD` (the `T` and time-of-day are dropped).

If you see a field showing blank when it should have data, `extract_fields()` is the first place to check.

---

### `container_tracker/core/excel.py` — Excel read/write/template

**`TRACKING_COL_MAP`** (top of file) — defines which Python field names map to which Excel column headers. If you add a new tracked field, add it here. The key is the exact column header that will appear in (or be searched for in) the workbook; the value is the key on the `tracking_data.json` record.

```python
TRACKING_COL_MAP = {
    "Carrier": "carrier",
    "Status": "status",
    "ETA": "eta",
    "Original ETA": "original_eta",
    "Delay": "delay_days",
    "Port of Loading": "pol",
    "Port of Discharge": "pod",
    "Vessel": "vessel",
    "Transit %": "transit_pct",
    "Last Refreshed": "last_refreshed",
}
```

**`find_container_column(ws)`** — searches row 1 for a header that matches `CONTAINER_COL_KEYWORDS` (exact match first, then substring). Returns the column index. Returns `None` if not found, which causes the update to raise `ValueError("No Container column found.")`.

**`update_excel_with_tracking(path, data)`** — the main write function. Opens the workbook, finds/creates all tracking columns, updates existing rows, appends any DB rows missing from the workbook, autosizes columns, saves. The `sc` dict inside this function controls status cell background colors:

```python
sc = {
    "sailing": "D6EAF8",    # light blue
    "en_route": "D6EAF8",   # same
    "arrived": "D5F5E3",    # light green
    "discharged": "ABEBC6", # medium green
    "delivered": "82E0AA",  # dark green
    "booked": "FCF3CF",     # light yellow
    "new": "FCF3CF",        # same
    "untracked": "F2F3F4",  # light gray
}
```

Delay colors: positive delay → red fill `FADBD8`, font `C0392B`. Early → green fill `D5F5E3`, font `27AE60`. On time → green font only.

**`append_container_row(path, cn, carrier, status, record)`** — adds one new row. Called by `add_container` (record=None, just writes carrier + "NEW" status) and `restore_container` (record=rec, writes all tracked fields).

**`remove_container_row(path, cn)`** — deletes the row(s) where the container column matches `cn`. Called by `archive_container`. Walks top-to-bottom to find rows, deletes bottom-to-top so indices don't shift.

**`create_template_excel(path)`** — creates a fresh workbook with the standard 13-column header row, 2 sample rows, an Excel Table (`ContainerTracking`), frozen panes at A2, and preset column widths.

---

### `container_tracker/core/config.py` — Data directory, config, migrations

**Data directory** — `%APPDATA%\ContainerTracker\` on Windows. Three files live there:
- `config.json` — company name, Excel path, dark_mode flag, dismissed CN list
- `tracking_data.json` — the container database (flat dict keyed by CN)
- `tracker.log` — all app log output

`DATA_DIR`, `CONFIG_FILE`, `TRACKING_DB_FILE`, `LOG_FILE` are module-level constants computed once on import.

**`load_config()` / `save_config(cfg)`** — read/write `config.json`. `load_config()` returns defaults if the file doesn't exist (fresh install).

**`load_tracking_db()`** — reads `tracking_data.json`. Returns `{}` if the file doesn't exist.

**`boot()`** — must be called once at startup before anything touches config or keyring. Runs in this order: logging setup → folder migrations → token migration from config → keyring migration. All steps are idempotent (safe to re-run).

**`run_folder_migrations()`** — moves data files from two legacy locations into `DATA_DIR`:
1. The directory next to the `.exe` (v0 layout)
2. `%APPDATA%\Ken Gabbay Coffee\KenGabbayTracker\` (v1 brand)

These must stay in place as long as any user could have the old version installed.

---

### `container_tracker/core/credentials.py` — API key storage

The API token is stored in Windows Credential Manager (via the `keyring` library), never in any file. Service name: `ContainerTracker_shipsgo_api`.

- `get_api_token()` — reads the token. Returns `""` if not set or if `keyring` is unavailable.
- `set_api_token(token)` — writes the token.
- `migrate_keyring()` — one-time migration from the legacy service name (`KenGabbayTracker_shipsgo_api`). No-op after the first run.

**Rule:** the token value never crosses the bridge to JS. `get_settings()` returns only `api_token_present: bool`. The JS placeholder shows `"••••••••••••••••"` when a token is set.

---

### `container_tracker/core/constants.py` — Shared constants

Anything you'd otherwise have to change in multiple places:

- `__version__` — shown in the window title. Must also be updated in `installer.iss` (`AppVersion`) for the installer and GitHub release tag to trigger the update banner.
- `GITHUB_REPO` — `"m-mcohen/container-tracker"`. The update check hits `api.github.com/repos/{GITHUB_REPO}/releases/latest`.
- `API_BASE` — `"https://api.shipsgo.com/v2"`. Change here to point at a staging API.
- `CARRIER_NAMES` — the displayed list in all carrier dropdowns. Add a carrier here to make it appear in the Add Container and Register Unmatched modals.
- `CARRIER_SCAC_MAP` — maps display name (uppercased) to SCAC code. Add an entry here if you add a carrier to `CARRIER_NAMES`.
- `CONTAINER_COL_KEYWORDS` — header keywords the app looks for when scanning an Excel workbook to find the container number column.

---

## Data model

Each record in `tracking_data.json` is a flat dict keyed by container number (uppercased). All these fields may be present:

```
container_number   str   — the CN ("MSCU1234567")
shipment_id        str   — ShipsGo internal ID; used for get_shipment calls
carrier            str   — display name ("MAERSK LINE")
scac               str   — 4-letter code ("MAEU")
status             str   — "SAILING", "ARRIVED", "DISCHARGED", "DELIVERED", "GATE_OUT", "BOOKED", or ""
vessel             str
pol                str   — Port of Loading name
pod                str   — Port of Discharge name
eta                str   — "YYYY-MM-DD" or ""
etd                str   — "YYYY-MM-DD" or ""
original_eta       str   — "YYYY-MM-DD" or ""
delay_days         str   — formatted string: "+7 days", "On time", "-2 days (early)", or ""
transit_pct        int|str — 0–100 or ""
last_refreshed     str   — ISO 8601 UTC timestamp or ""
archived           bool  — True if archived; absent = False (legacy records)
```

Records are written by `extract_fields()` (via `refresh_all`/`refresh_one`) and read by `_to_row()` (bridge → JS). Pre-refresh stub records (Excel-discovered, not yet registered) have only `container_number` and `last_refreshed: null`.

---

## Excel sync rules

- **Source of truth is `tracking_data.json`.** Excel is a projection of that DB.
- **Two-way sync during refresh:** CNs in Excel but not in DB → added as stubs. CNs in DB but not in Excel → removed from DB (unless archived).
- **App-written columns** (the 10 in `TRACKING_COL_MAP`) are overwritten on every refresh.
- **User-owned columns** (`Container #`, `PO / Reference`, `Notes`, any others) are never touched.
- **Archived rows** are removed from Excel when archived and re-added when restored. `refresh_all`'s two-way sync skips archived records so they don't get re-deleted.
- **Excel locked by another process** — `bridge.py` catches the `PermissionError` and sets `excel_write_failed=True` in the return dict. JS shows the "Excel write skipped" banner. The tracking DB is still saved; the next successful refresh will write the missed updates.

---

## Build and release

Three things must move together for a release:

1. `__version__` in `container_tracker/core/constants.py`
2. `AppVersion` in `installer.iss`
3. A GitHub release whose tag matches the version (e.g. `v1.1.1`) — the update banner compares `releases/latest` tag against `__version__`

```bat
build.bat                  :: builds dist\ContainerTracker.exe
iscc installer.iss         :: builds dist\installer\ContainerTracker_Setup_v<version>.exe
```

`build.bat` creates a `.venv-build/` virtual environment with only the declared dependencies before running PyInstaller, so the bundle doesn't pick up unrelated packages from system Python.

---

## Files that are NOT part of the running app

| File | Purpose |
|---|---|
| `container_tracker_gui.py` | Old tkinter UI — kept as reference. Not imported by anything. |
| `container_tracker.py` | Old CLI variant — separate data layout, separate Excel writer. Not used by the GUI. |
| `docs/EXCEL_IO_LEGACY.md` | Deep-dive research notes on the legacy tkinter Excel I/O flow. |
| `docs/MIGRATION_PROMPT.md` | The original build plan for the tkinter → pywebview rewrite. Historical only. |
| `README_CLIENT.md` | End-user manual. |
| `tests/` | Test directory exists but is currently empty (only `tests/fixtures/`). |
