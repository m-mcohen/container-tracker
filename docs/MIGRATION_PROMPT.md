# Claude Code Prompt: Migrate Container Tracker from tkinter to pywebview

> **How to use:** Open Claude Code from the Claude desktop app, point it at this repo
> (`C:\Users\emine\OneDrive\Documents\Claude\container_tracking_build`), run `/init` so it
> writes a CLAUDE.md with full repo context, then paste everything between
> `--- BEGIN PROMPT ---` and `--- END PROMPT ---` as a single message.

--- BEGIN PROMPT ---

You're migrating this stable v1 tkinter/CustomTkinter desktop app to a pywebview-based
architecture. Python business logic stays; the UI is rewritten as HTML/CSS/JS rendered in an
embedded WebView2 window. Ship target stays the same: a single Windows .exe built with
PyInstaller, packaged with Inno Setup.

The new UI is **already designed**. See `docs/mockup.html` — a complete, interactive HTML
mockup. **This file IS the starting point for the real UI.** During migration you'll split its
inline `<style>` and `<script>` blocks into separate files. Open it in a browser and click
around before writing any code.

**Mockup design decisions to preserve (don't redesign these):**

- **No sidebar.** The dashboard and Settings are the only two views. Brand mark + company name
  live on the **left side of the topbar**; clicking the brand returns to the dashboard from
  any view. Settings opens via a **gear icon button on the right side of the topbar** — same
  mental model as v1's tkinter app.
- **Topbar action order (left→right):** brand · divider · page title · spacer · search ·
  theme switch · Settings gear · "Add container" (secondary) · "Refresh" (primary blue).
  Refresh is the daily action and gets primary weight; Add is occasional.
- **Single notifications stack.** Update banner and the unmatched-containers inline notice
  share one `<div class="notifications">` container at the top of `.content`.
- **Status chips in Title Case** ("Sailing", "Delayed", "Arrived") — not uppercase.
- **Activity log defaults collapsed.** Click the header to expand; `aria-expanded` flips.
- **Every interactive element is a real `<button>` or `<a>`** — filter chips, theme switch,
  activity-log header, Settings nav, brand. ARIA: `aria-pressed` on filter chips,
  `role="switch" aria-checked` on the theme toggle, `aria-expanded` on the log toggle.
- **Keyboard shortcuts:** `Ctrl+K` focuses the search field; `Esc` closes drawer/modals.
- **Color tokens preserve v1's accent** (`#2563eb`) so existing users see continuity. Light
  and dark themes both use `data-theme` on `<html>` driving CSS custom properties.

Before writing code:

1. Open `docs/mockup.html` in a browser; click brand, gear, filter chips, search, table rows
   (drawer), Add container (modal), settings view, theme switch.
2. Read `container_tracker_gui.py` end to end — this is the v1 monolith we're replacing.
   Pay attention to: `SetupDialog`, `ShipsGoClient`, `extract_fields`, `find_container_column`,
   `read_containers_from_excel`, `update_excel_with_tracking`, `create_template_excel`,
   `_migrate_data_folder`, `_migrate_keyring`, `validate_setup_fields`, `check_for_update_async`,
   `is_first_run`, `migrate_token_from_config`, `now_est`, `now_est_short`, `open_in_explorer`,
   `resolve_scac`, `CARRIER_NAMES`, `CARRIER_SCAC_MAP`, `API_KEY_PATTERN`, `EMAIL_PATTERN`,
   `KEYRING_SERVICE`, `LEGACY_KEYRING_SERVICE`, `DATA_DIR`, `CONFIG_FILE`, `TRACKING_DB_FILE`.
3. Read `container_tracker.py` (the CLI entry point — most of its logic duplicates the GUI;
   we'll dedupe in Step 1).
4. Confirm in **one paragraph** that you understand (a) the UI target and (b) which Python
   helpers will need to be exposed to JS via the bridge.

## Architecture and constraints

### Keep untouched (lift-and-shift into a `core/` package in Step 1)

The v1 monolith mixes UI and logic. Step 1 extracts the logic-only helpers from
`container_tracker_gui.py` into a new package without changing their behavior:

- ShipsGo client: the `ShipsGoClient` class.
- Data layer: `load_json`, `save_json`, `load_config`, `save_config`, `get_data_dir`,
  `migrate_token_from_config`, `is_first_run`, `_migrate_data_folder`.
- Credentials: `get_api_token`, `set_api_token`, `_migrate_keyring`, `KEYRING_SERVICE`,
  `LEGACY_KEYRING_SERVICE`.
- Status / fields: `extract_fields`, `resolve_scac`, `CARRIER_SCAC_MAP`, `CARRIER_NAMES`,
  `API_KEY_PATTERN`, `EMAIL_PATTERN`, `validate_setup_fields`.
- Excel: `find_container_column`, `find_or_create_tracking_columns`,
  `read_containers_from_excel`, `update_excel_with_tracking`, `create_template_excel`,
  `CONTAINER_COL_KEYWORDS`.
- Updates: `check_for_update_async`, `GITHUB_REPO`.
- OS helpers: `open_in_explorer`, `now_est`, `now_est_short`, `EST`.
- Constants: `APP_NAME`, `APP_SHORT_NAME`, `__version__`, `DATA_DIR`, `CONFIG_FILE`,
  `TRACKING_DB_FILE`, `LOG_FILE`, `ACCENT`.

### Archive (after migration is complete and verified — Step 9)

- `container_tracker_gui.py` → `legacy/container_tracker_gui.py`
- `container_tracker.py` (CLI) → `legacy/cli.py` and refactor it to import from `core/`.

### Add (new code)

- `container_tracker/__init__.py` — `__version__ = "1.1.0"` (bumped for the rewrite).
- `container_tracker/__main__.py` — calls `app.main()`.
- `container_tracker/app.py` — pywebview entry point.
- `container_tracker/bridge.py` — `Bridge` class, exposed to JS as `js_api`.
- `container_tracker/core/` — extracted modules:
    - `core/__init__.py`
    - `core/api.py` (ShipsGo client, SCAC resolution)
    - `core/config.py` (data dir, config load/save, keyring, all migrations)
    - `core/excel.py` (read/write/template)
    - `core/status.py` (`extract_fields`, status normalization, delay computation)
    - `core/updates.py` (GitHub release check)
    - `core/util.py` (`open_in_explorer`, EST helpers)
- `container_tracker/web/` — UI assets:
    - `web/index.html`
    - `web/styles.css`
    - `web/app.js`

### Dependencies in `pyproject.toml` (create one if missing)

- ADD: `pywebview>=5`
- KEEP: `requests`, `openpyxl`, `keyring`, `packaging`
- KEEP through Step 9, then REMOVE: `customtkinter`, `pillow`
- Update `build.bat` accordingly in Step 9.

## Global rules

1. **No tkinter or customtkinter imports in any new file.** They stay only in `legacy/`.
2. **All UI ↔ filesystem / network calls go through `bridge.py`.** No direct file or HTTP
   access from JS.
3. **Bridge methods are typed and documented.** Every method has a Python type-annotated
   signature, a docstring stating I/O types and error shape, and a unit test with `core`
   mocked.
4. **Mutating bridge calls return `{ok: bool, ...}`.** Never let an uncaught exception cross
   the bridge.
5. **`web/` is pure static assets** — no templating, no dev server, no CDN. The mockup uses
   no external resources today; keep it that way.
6. **Run `pytest` after every step. Launch the app and spot-check.**
7. **Show the diff and STOP between steps.** Wait for "continue". If you discover the plan
   is wrong, stop and flag it; don't quietly redesign.
8. **Preserve existing data.** `DATA_DIR` (`%APPDATA%\ContainerTracker\`) and the keyring
   entry don't change. Existing v1 users opening the new build must find their settings,
   tracking data, and API key intact.

## Step plan

Each step is one PR-sized unit. Acceptance criteria are listed; meet them before moving on.

### Step 1 — Carve `core/` out of `container_tracker_gui.py`

Pure refactor — no behavior change.

- Create the `container_tracker/core/` package and move the helpers listed above into the
  named modules.
- Update `container_tracker_gui.py` to import from `container_tracker.core.*` rather than
  defining helpers inline. The tkinter app still runs identically.
- Add minimal `tests/test_core_*.py`: `validate_setup_fields`, `resolve_scac`,
  `extract_fields` against a recorded ShipsGo response fixture, `read_containers_from_excel`
  against a small fixture xlsx in `tests/fixtures/`.
- Confirm `python container_tracker_gui.py` still launches and works end-to-end (welcome
  dialog, refresh, add, remove, dark mode toggle).

**Acceptance:** the v1 tkinter app still runs unchanged, but its logic lives in `core/`. New
tests pass. Commit message: `refactor: extract core/ package from monolith`.

### Step 2 — Minimal pywebview shell

- Create `container_tracker/app.py` and `__main__.py`.
- `app.py` resolves the `web/` asset path:

    ```python
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS) / "container_tracker" / "web"
    else:
        base = Path(__file__).parent / "web"
    ```

- Open a 1280×820 window (min 1024×720), title `f"Container Tracker v{__version__}"`,
  icon from `app.ico`.
- `webview.start(debug=True)` in dev; `debug=False` when `getattr(sys, "frozen", False)`.
- `web/index.html` is a stub for this step ("Container Tracker — loading…").
- `python -m container_tracker` opens a window with the stub.

**Acceptance:** window opens and closes cleanly; tests pass.

### Step 3 — Port the mockup into `web/`

- Split `docs/mockup.html` into:
    - `web/index.html` (HTML only; references `styles.css` and `app.js`)
    - `web/styles.css` (everything inside `<style>`)
    - `web/app.js` (everything inside `<script>`)
- Remove cosmetic placeholders that shouldn't ship: `Acme Logistics Co.` company name,
  `3 min ago` refresh string, the `Version 1.1.0 available` banner, the "2 new containers
  found" notice text. Keep their HTML structure — JS will populate them at runtime.
- Keep the sample `ROWS` array for now — Step 5 wires it to live data.
- Verify the window now renders the mockup exactly as it looks in a browser. Brand click,
  gear → Settings, search, filter chips, drawer (row click), add modal, theme switch all
  work.

**Acceptance:** the full mockup renders inside the pywebview window identically to the
browser. Dark mode works via the in-mockup theme switch.

### Step 4 — Bridge API (`bridge.py`)

Document each method in the module docstring before implementing. All methods accept and
return JSON-serializable types only. Mutating methods return `{ok, ...}` shapes; read methods
raise on internal failure (the bridge wrapper converts to JS errors).

```python
class Bridge:
    # ─── Config ───
    def get_config(self) -> dict:
        """→ {company_name, contact_email, excel_path, dark_mode,
              api_key_set: bool, dismissed: list[str], compact_rows: bool,
              show_activity_log: bool, auto_refresh_on_launch: bool}"""

    def save_config(self, patch: dict) -> dict:
        """Merges patch into config and persists. Returns full new config (without api_key)."""

    # ─── API key ───
    def save_api_key(self, key: str) -> dict:
        """Validates against API_KEY_PATTERN, writes to keyring. → {ok, valid_format, error?}"""

    def test_api_key(self) -> dict:
        """Pings ShipsGo /ocean/carriers. → {ok, message}"""

    # ─── Containers ───
    def list_containers(self) -> list[dict]:
        """All rows, normalized for the UI: container_number, carrier, scac, status,
        original_eta, eta, delay, delay_val, pol, pod, vessel, transit_pct, last_refreshed."""

    def add_container(self, container_number: str, carrier: str) -> dict:
        """→ {ok, record?, already_exists?, error?}"""

    def remove_container(self, container_number: str, permanent: bool) -> dict:
        """permanent=True adds to dismissed list (never re-fetched).
        permanent=False just hides until next refresh (matches v1's two-message flow)."""

    # ─── Refresh / Excel ───
    def refresh_all(self) -> dict:
        """→ {matched, unmatched, unmatched_list, delayed_sailing, excel_rows_updated}"""

    def get_credit_balance(self) -> int | None:
        """Placeholder — ShipsGo doesn't expose this directly. Return None for now."""

    # ─── Spreadsheet ───
    def browse_excel_file(self) -> str | None:
        """Uses webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, ...)"""

    def create_excel_template(self) -> str | None:
        """Save dialog + create_template_excel. → path or None if cancelled."""

    def open_excel_file(self) -> dict:
        """os.startfile on stored excel_path. → {ok, error?}"""

    def open_data_folder(self) -> dict:
        """os.startfile on DATA_DIR."""

    # ─── External ───
    def open_external(self, url: str) -> dict:
        """Validates http(s) scheme; webbrowser.open. → {ok, error?}"""

    def check_for_update(self) -> dict:
        """Sync wrapper around v1's threaded GitHub release check.
        → {available: bool, version?, url?}"""

    # ─── Welcome / first run ───
    def is_first_run(self) -> bool: ...

    def complete_welcome(self, company: str, email: str, api_key: str) -> dict:
        """Validates fields (validate_setup_fields), saves config + keyring.
        → {ok, errors?: dict[field, message]}"""
```

Tests in `tests/test_bridge.py` mock `core` modules and verify shapes.

**Acceptance:** all bridge methods exist with typed signatures, docstrings, and tests. The
pywebview app still opens.

### Step 5 — Wire live data

In `web/app.js`, add a `Bridge` proxy at the top so calls read clean:

```js
const Bridge = new Proxy({}, {
  get: (_, name) => (...args) =>
    window.pywebview && window.pywebview.api
      ? window.pywebview.api[name](...args)
      : Promise.reject(new Error("Bridge not ready"))
});
```

On `pywebviewready` event (pywebview fires this when `window.pywebview.api` is populated):

- `await Bridge.is_first_run()` — if true, show the welcome overlay (Step 6 builds it; for
  now log).
- `await Bridge.get_config()` → set company name in topbar brand-company, theme attribute on
  `<html>`, linked-spreadsheet path in Settings, appearance toggles in Settings, activity-log
  collapsed/expanded.
- `await Bridge.list_containers()` → render the table. Drop the inline `ROWS` constant.
- `await Bridge.check_for_update()` → if `available`, show the update banner with version
  and URL.

Wire interactions:

- **Filter chips + search input** filter the rendered list client-side (already in mockup).
- **Refresh button:** `await Bridge.refresh_all()`. Show inline spinner state on the button
  while running. On completion: update "Last refreshed" label, re-fetch list, then:
    - if `unmatched_list.length > 0`: render the inline yellow notice with count and credit
      cost, and a "Register N · N credits ($N×2)" button → loops `Bridge.add_container`
      with progress.
    - else if `delayed_sailing > 0`: a small toast.
- **Add modal submit:** validate (11-char regex matching v1's `len(cn) != 11` check), then
  `Bridge.add_container()`. On success close modal, refetch.
- **Drawer "Stop tracking":** `Bridge.remove_container({permanent: row.is_completed})`,
  where `is_completed` is true if status is in
  `{ARRIVED, DISCHARGED, DELIVERED, GATE_OUT}` (matches v1's `is_done` logic). Different
  modal copy for completed vs. active (also matches v1).
- **Drawer "Refresh now":** call `Bridge.refresh_all()` for now (granular per-row refresh
  is a follow-up).
- **Settings save:** `Bridge.save_config()` for company / email / appearance toggles;
  `Bridge.save_api_key()` only if the user typed something new.
- **Settings "Test API key":** `Bridge.test_api_key()`; show inline result next to the
  button.
- **Settings "Open in Excel" / "Change…" / "Create template":** call corresponding bridge
  methods.
- **Settings "Data folder" link:** `Bridge.open_data_folder()`.
- **Settings nav `<a>` links:** smooth-scroll to the matching `<section id>`.
- **Theme switch:** `Bridge.save_config({dark_mode: bool})` so it persists.
- **Bridge errors render as a small inline toast** (top-right). Never use `alert()`.

**Acceptance:** UI is fully live. Add/remove/refresh/settings persist across app restarts.
Linked-spreadsheet, dark mode, and update banner all work end-to-end. The unmatched-containers
inline notice replaces v1's modal-spam flow.

### Step 6 — First-run welcome flow

- Add a welcome overlay to `index.html` (a centered `<div class="welcome">` with the same
  three fields as v1's `SetupDialog`: company name, ShipsGo API key, contact email).
- Show it iff `Bridge.is_first_run()` returns true.
- Live validation (mirror `validate_setup_fields`): show inline errors per field; disable
  Save until all valid.
- On Save: `Bridge.complete_welcome(...)`; on `{ok: true}` hide overlay and boot normally.
- If the user closes the window with the overlay still visible, the bridge's window-close
  handler quits the app (matches v1's `_exit_app` behavior).

**Acceptance:** first launch shows the welcome; subsequent launches skip straight to the
dashboard. Closing during welcome quits.

### Step 7 — Native dialogs and external links

- `browse_excel_file` → `webview.windows[0].create_file_dialog(webview.OPEN_DIALOG,
  file_types=('Excel files (*.xlsx)',))`.
- `create_excel_template` → `webview.SAVE_DIALOG` with
  `save_filename="Container_Tracking.xlsx"`.
- All `<a href>` links in the UI are intercepted: route through `Bridge.open_external(url)`.
  Verify nothing opens inside the webview itself.
- Settings → About → "Data folder" calls `Bridge.open_data_folder()`.
- `Esc` closes drawer/modal (already wired in mockup); `Ctrl+K` focuses search (already
  wired).

**Acceptance:** native Windows file pickers appear. Links open in the system browser. No
links open in-webview.

### Step 8 — Update banner from real data

- `Bridge.check_for_update()` is a sync wrapper around v1's `check_for_update_async`. Call
  it on a background thread internally; cache the result for the session.
- `app.js` calls it once on launch and shows the banner only if `available`.
- "Download update" → `Bridge.open_external(url)`. Dismiss hides the banner for the session
  only (no persistence — same as v1).

**Acceptance:** banner appears iff a newer GitHub release exists.

### Step 9 — Cut over to pywebview, package as .exe

- Move `container_tracker_gui.py` → `legacy/container_tracker_gui.py`.
- Move `container_tracker.py` → `legacy/cli.py` and update its imports to use the new
  `core/` modules (it should still work as a CLI for headless runs).
- Update `build.bat`:
    - Change PyInstaller target from `container_tracker_gui.py` to
      `container_tracker/__main__.py`.
    - Replace `--collect-all customtkinter` with `--collect-all webview` (and
      `--collect-all webview.platforms.winforms` if needed).
    - Add `--add-data "container_tracker/web;container_tracker/web"` so HTML/CSS/JS ship
      inside the .exe.
    - Drop `pillow` from the `pip install` line (no longer needed).
    - Keep `--name "ContainerTracker"`, `--icon app.ico`, `--add-data "app.ico;."`.
- Update `installer.iss` only if the file manifest changed (it shouldn't — the installer
  ships `dist\ContainerTracker.exe` and `README_CLIENT.md`).
- Bump `__version__` to `"1.1.0"`.
- Update `installer.iss` `AppVersion` and `OutputBaseFilename` to match.
- Document WebView2 dependency in `README_CLIENT.md`: preinstalled on Windows 11 and Windows
  10 1809+. For older Windows 10, bundle the Evergreen Bootstrapper
  (`MicrosoftEdgeWebview2Setup.exe`) in the Inno Setup `[Files]` section and run it via
  `[Run]` if the runtime is missing.
- Build the .exe and test it on a clean Windows VM with no Python installed. Test the
  upgrade path from v1.0.0: install v1.0.0 first, add some containers, then install v1.1.0
  over it and confirm settings + tracking data + API key carry over.

**Acceptance:** `dist\ContainerTracker.exe` runs end-to-end on a clean VM. Welcome flow
works. Refresh, add, remove, settings, theme, update banner, Excel integration all work.
Installer produces `dist\installer\ContainerTracker_Setup_v1.1.0.exe`. Existing v1.0.0 users
keep their data.

### Step 10 — Final cleanup

- Remove `customtkinter`, `pillow` from `pyproject.toml`.
- Delete `legacy/` (separate commit, after a few days of soak time).
- Final `pytest` and full manual run-through.

**Acceptance:** tkinter is gone. The repo is leaner. The app ships.

## Practical notes

- **Bridge access in JS:** `pywebview` exposes `js_api` as `window.pywebview.api`. The
  `Bridge` proxy shorthand shown in Step 5 turns `Bridge.foo(...)` into
  `await window.pywebview.api.foo(...)`. Always `await`.
- **Bridge methods run on a worker thread.** Don't try to mutate UI state from Python;
  return data and let JS re-render.
- **Long operations (`refresh_all`)** can take 30+ seconds. Show a spinner state on the
  Refresh button. For finer feedback, expose `Bridge.get_refresh_progress()` and poll every
  500ms while a refresh is running.
- **Path resolution for bundled assets:**

    ```python
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS) / "container_tracker" / "web"
    else:
        base = Path(__file__).parent / "web"
    ```

- **WebView2 runtime:** if missing, pywebview surfaces a clear error. Bundle the Evergreen
  Bootstrapper (~2 MB, link in `README_CLIENT.md`).
- **Dev DevTools:** keep `webview.start(debug=True)` in dev so right-click → Inspect Element
  works. Production builds set `debug=False`.
- **CSP:** pywebview doesn't enforce CSP by default. Since all assets are local, fine.
- **Single-instance behavior:** v1 isn't single-instance and we won't add it now.

## Review discipline

After each step:

1. `pytest` clean.
2. Launch `python -m container_tracker` and exercise the changed area in both light and dark
   mode.
3. Post a short summary: files touched, methods added, tests added, deviations from this
   plan (if any).
4. **Stop. Wait for "continue".**

Begin by reading `docs/mockup.html` and `container_tracker_gui.py`, then post your
one-paragraph confirmation. Then start Step 1.

--- END PROMPT ---
