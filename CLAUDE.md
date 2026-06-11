# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Windows desktop GUI app that tracks ocean shipping containers via the ShipsGo API v2 and writes ETA/status/voyage data back into a user-linked Excel workbook. Distributed as a PyInstaller-built `.exe` wrapped in an Inno Setup installer.

## Build & run

```bat
:: Build the standalone exe (deps + PyInstaller)
build.bat
:: → dist\ContainerTracker.exe

:: Build the installer (requires Inno Setup compiler `iscc` on PATH)
iscc installer.iss
:: → dist\installer\ContainerTracker_Setup_v<version>.exe

:: Run the app from source (pywebview desktop window -- the shipped product)
python -m container_tracker

:: Legacy tkinter GUI (reference only; not built, not shipped)
python container_tracker_gui.py

:: Legacy CLI variant (separate codepath, different storage layout -- see below)
python container_tracker.py --all              # register from containers.json + refresh + export
python container_tracker.py --add MSKU1234567 MAERSK
python container_tracker.py --refresh
python container_tracker.py --carriers
```

Tests: `python -m pytest` (configured via `pyproject.toml`; the suite lives in `tests/` with shared fixtures in `tests/conftest.py`).

## Releasing

One command does the whole release:

```powershell
.\tools\release.ps1 -Version X.Y.Z              # full release
.\tools\release.ps1 -Version X.Y.Z -BuildOnly   # bump + test + build only, no git/GitHub
```

It bumps the version, runs pytest (aborting on failure), builds the exe (`build.bat`) and installer (`iscc`), commits, tags `vX.Y.Z`, pushes, and creates the GitHub Release with the installer attached (`gh` CLI must be authenticated).

**The version has a single source of truth: `__version__` in [container_tracker/core/constants.py](container_tracker/core/constants.py:3).** Everything else derives from it:

- `installer.iss` `#include`s a generated `version.iss` (written by `build.bat`, gitignored)
- `pyproject.toml` is patched in lockstep by `release.ps1`
- the UI's About panel reads it at runtime via `get_settings()["app_version"]`

The in-app update banner (wired in `bridge.check_for_update()` → `app.js checkForUpdate()`, logic in [container_tracker/core/updates.py](container_tracker/core/updates.py)) polls `releases/latest` for `GITHUB_REPO` and shows a clickable banner when a release tag parses newer than `__version__` (`v` prefix stripped). **The repo/releases must be publicly reachable** — the check is unauthenticated.

## Architecture

**Three codepaths live in this repo; only one is shipped.** They are intentionally separate -- do not refactor one into another without checking all.

| | pywebview app (**shipped**) | `container_tracker_gui.py` (legacy) | `container_tracker.py` (legacy CLI) |
|---|---|---|---|
| Entry | `python -m container_tracker` -> `__main__.py` -> `app.py` | `python container_tracker_gui.py` | `python container_tracker.py ...` |
| UI | HTML/CSS/JS in `container_tracker/web/`, rendered in a pywebview window; `bridge.py` is the Python<->JS API | tkinter / CustomTkinter | argparse |
| Config / token | `keyring` (service = `ContainerTracker_shipsgo_api`) | same keyring service | `SHIPSGO_API_KEY` env var (or `.env`) |
| Data dir | `%APPDATA%\ContainerTracker\` (`core/config.py`) | `%APPDATA%\ContainerTracker\` | CWD (next to script) |
| Status | built + shipped (`build.bat` / `ContainerTracker.spec` bundle `__main__.py`) | reference only -- not built, not imported | reference only -- separate data layout |

The shipped app's logic lives in the **`container_tracker/` package** (not the top-level `.py` files):

- `app.py` -- creates the pywebview window (1280x820), runs startup migrations, wires the bridge
- `bridge.py` -- the `js_api` object exposed to JS as `window.pywebview.api`
- `web/` -- `index.html` (structure), `styles.css` (visual styling), `app.js` (UI behavior)
- `core/` -- `api.py` (ShipsGo HTTP client), `status.py` (response -> flat-record parser), `excel.py` (Excel read/write/template), `config.py` (data dir + config + migrations), `credentials.py` (keyring token storage), `constants.py` (version, `GITHUB_REPO`, carrier maps), `updates.py` (release-check banner), `util.py`

There is **no** `container_tracker/ui/` package, and `core/` is **not** empty. (An earlier version of this doc called `core/`/`ui/` "empty vestigial scaffolding" -- that predated the tkinter -> pywebview rewrite.)

**[`DEVNOTES.md`](DEVNOTES.md) is the authoritative reference for the shipped pywebview app** (startup sequence, spot-edit index, file-by-file breakdown). The four subsections immediately below (Data model, GUI <-> Excel sync, Migrations, First-run/window lifecycle) document the **legacy tkinter GUI**; the domain concepts (the ShipsGo parser, the Excel-sync rules) carry over to `core/`, but the specifics describe the old GUI.

### Data model

Both variants use the same in-memory shape: a flat dict keyed by container number, each value carrying `shipment_id`, extracted fields (`status`, `eta`, `pol`, `pod`, `vessel`, `transit_pct`, `original_eta`, `delay_days`), `last_refreshed` timestamp, and a `voyage_data` blob (CLI only) with the raw API payload. Persisted as pretty-printed JSON to `tracking_data.json`.

`extract_fields()` is the canonical "ShipsGo v2 response → flat record" parser. The v2 API wraps single-shipment GETs as `{"message": ..., "shipment": {...}}` and exposes route data under `route.port_of_loading` / `route.port_of_discharge` (with legacy `origin`/`destination` fallbacks). Vessel name comes from the most recent movement that has one, walked in reverse — don't take the first.

### GUI ↔ Excel sync

The GUI's value-add is two-way Excel sync, implemented in `read_containers_from_excel`, `find_or_create_tracking_columns`, and `update_excel_with_tracking`:

1. Find the user's container column by header keyword (`container`, `cntr`, etc. — see `CONTAINER_COL_KEYWORDS`).
2. For each known tracking field in `TRACKING_COL_MAP`, find the matching header or append a new column with the styled header bar.
3. Write tracking values back; conditional fills for status; red/green for `delay_days`.
4. Containers in the local DB but missing from the workbook get appended as new rows.
5. `read_containers_from_excel` also discovers *new* containers in the user's workbook so they can be offered for registration on the next refresh (`_prompt_register_unmatched`).

Registration costs ShipsGo credits; refreshes are free. The GUI confirms before any `create_shipment()` call and special-cases HTTP 402 (`NOT_ENOUGH_CREDITS`) and 409 (`already_exists`).

### Migrations (load-bearing — do not remove without thought)

The app shipped a previous brand identity ("Ken Gabbay Coffee" / `KenGabbayTracker`). Two migrations run unconditionally at startup and must keep working for existing installs:

- `_migrate_data_folder` (called twice in [container_tracker_gui.py:118-119](container_tracker_gui.py:118)): moves `config.json`/`tracking_data.json`/`tracker.log` from (a) the exe/script directory and (b) `%APPDATA%\Ken Gabbay Coffee\KenGabbayTracker\` into the current `DATA_DIR`. Cleans up empty parent dirs.
- `_migrate_keyring`: copies the API token from the legacy `KenGabbayTracker_shipsgo_api` service into the current one, then deletes the old entry.
- `migrate_token_from_config`: pulls a token out of `config.json` (if a very early build wrote it there) and into the keyring.

### First-run / window lifecycle (subtle)

`ContainerTrackerApp.__init__` deliberately:
1. Sets `wm_attributes('-alpha', 0.0)` so the root window is invisible while building.
2. Runs the modal `SetupDialog` (mode=`first_run`) before the main UI is built. The `×` button on first-run dialog calls `sys.exit(0)` to avoid leaving a half-initialized app behind.
3. Calls `deiconify()` *before* `geometry()` and `wm_attributes('-alpha', 1.0)` — geometry on a withdrawn CTk root is a silent no-op (see comment at [container_tracker_gui.py:694-697](container_tracker_gui.py:694)).

If you change the startup sequence, preserve this ordering.

### Storage: keyring, not config.json

The ShipsGo token must never be written to `config.json` or any plain-text file. `set_api_token`/`get_api_token` are the only correct accessors. `migrate_token_from_config` exists *because* an early build violated this; treat any reintroduction as a regression.

## Security: outstanding action (flagged 2026-05-20)

**Rotate `SHIPSGO_API_KEY`.** During a repo-sync security pass, a `.env` containing a
live `SHIPSGO_API_KEY` (used by the CLI variant `container_tracker.py`) was found in a
OneDrive-synced folder — unencrypted and cross-device-synced. It was relocated to
`C:\Users\emine\.secrets\container-tracker\.env`. Treat the old key as **exposed**.
(2026-06-11: owner confirmed rotation is deferred until the v1.2 development pass
is finished — do not delete this section until the rotation is actually done.)

Steps:
1. Generate a new key in the ShipsGo dashboard and revoke the old one.
2. Update the relocated `.env` (CLI path) with the new key.
3. Update the GUI keyring entry `ContainerTracker_shipsgo_api` (Windows Credential Manager).
4. Never store the key in any cloud-synced path again — the GUI's keyring storage is the
   correct pattern; the CLI's `.env` must live outside synced folders.
