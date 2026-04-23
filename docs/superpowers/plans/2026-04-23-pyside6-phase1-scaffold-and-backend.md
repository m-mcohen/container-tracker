# Phase 1 — Scaffold + Backend Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the real backend out of the 1,406-line `container_tracker_gui.py` monolith into a clean `container_tracker/core/` package with unit tests passing, wire up `__main__.py` to bootstrap `QApplication` + logging + config, and get a blank PySide6 `MainWindow` to render on launch. No feature functionality — the window is empty at the end of this phase.

**Architecture:** The existing CustomTkinter monolith mixes backend (ShipsGo API, Excel I/O, config, keyring, update check, status normalization) with UI. This phase copies that backend code — unchanged in semantics — into six focused modules inside `container_tracker/core/`, each covered by tests. A minimal `__main__.py` wires logging per spec §3.4 and constructs `QApplication`. A blank `QMainWindow` subclass proves the window shows.

**Tech Stack:** Python 3.11+, PySide6 ≥ 6.6, pytest, responses (HTTP mocking), mypy, openpyxl, keyring, packaging, requests.

**Spec:** [2026-04-23-pyside6-migration-design.md](../specs/2026-04-23-pyside6-migration-design.md)

---

## Checkpoint structure

Phase 1 has **three internal checkpoints**. Stop and wait for review between each.

- **Checkpoint A** (Tasks 1–9): Package layout + `core/` extracted + unit tests green + `mypy --strict` clean + obsolete CLI deleted.
- **Checkpoint B** (Tasks 10–12): `__main__.py` bootstraps `QApplication`, loads config, writes a formatted startup log line. No window yet.
- **Checkpoint C** (Tasks 13–15): Blank `MainWindow` renders on launch, closes cleanly, startup/shutdown logged.

Each "**CHECKPOINT X — STOP**" section is a hard pause for review before proceeding.

---

## File Structure

Files created by end of Phase 1:

```
container_tracker/
  __init__.py              # empty; marks package
  __version__.py           # __version__ = "1.1.0"
  __main__.py              # entry point, logging setup, QApplication bootstrap
  core/
    __init__.py            # re-exports common symbols for convenience
    api.py                 # ShipsGoClient, ShipsGoAuthError, extract_fields, resolve_scac, CARRIER_SCAC_MAP, CARRIER_NAMES
    excel.py               # read_container_list, write_tracking_report, create_template, ExcelFormatError
    persistence.py         # data_dir, config paths, load/save config + tracking_data, keyring wrappers, is_first_run
    status.py              # normalize_status, compute_delay_days, bucket_counts, StatusBucket
    updates.py             # UpdateInfo dataclass, check_for_update
  ui/
    __init__.py            # empty
    widgets.py             # QtLogHandler only (other widgets are later phases)
    main_window.py         # blank MainWindow subclass (Checkpoint C)

tests/
  __init__.py
  test_api.py
  test_excel.py
  test_persistence.py
  test_status.py
  test_updates.py
  fixtures/
    shipsgo_sailing.json          # sample v2 shipment payload, sailing
    shipsgo_arrived.json          # sample v2 shipment payload, arrived
    shipsgo_list.json             # sample v2 list response

pyproject.toml             # package metadata, pytest config, mypy config
```

Files deleted by end of Phase 1:

```
container_tracker.py       # obsolete CLI; dead code; nothing imports it
```

Files untouched by Phase 1 (modified in later phases):

```
container_tracker_gui.py   # monolith still exists — deleted at end of Phase 5 when functionality is fully ported
ContainerTracker.spec      # PyInstaller spec — updated in Phase 7
installer.iss              # Inno Setup — updated in Phase 7
build.bat                  # build script — updated in Phase 7
README_CLIENT.md
ATTRIBUTIONS.md
app.ico
```

**Working directory for all commands:** `C:/Users/emine/OneDrive/Documents/Claude/container_tracking_build`

---

## Task 1: Project skeleton and tooling

**Files:**
- Create: `pyproject.toml`
- Create: `container_tracker/__init__.py` (empty)
- Create: `container_tracker/__version__.py`
- Create: `container_tracker/core/__init__.py`
- Create: `container_tracker/ui/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `.gitignore` additions if needed

- [ ] **Step 1: Create the package directories**

```bash
mkdir -p container_tracker/core container_tracker/ui tests/fixtures
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "container_tracker"
version = "1.1.0"
description = "Container ETA tracker using ShipsGo API"
requires-python = ">=3.11"
dependencies = [
    "PySide6>=6.6",
    "requests>=2.31",
    "openpyxl>=3.1",
    "keyring>=24.0",
    "packaging>=23.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "responses>=0.24",
    "mypy>=1.7",
    "types-requests",
    "types-openpyxl",
]

[tool.setuptools.packages.find]
include = ["container_tracker*"]
exclude = ["tests*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-ra -q"

[tool.mypy]
python_version = "3.11"
strict = true
files = ["container_tracker/core"]

[[tool.mypy.overrides]]
module = ["keyring.*", "openpyxl.*", "packaging.*"]
ignore_missing_imports = true
```

- [ ] **Step 3: Write `container_tracker/__version__.py`**

```python
__version__ = "1.1.0"
```

- [ ] **Step 4: Write `container_tracker/__init__.py`**

```python
from container_tracker.__version__ import __version__

__all__ = ["__version__"]
```

- [ ] **Step 5: Write `container_tracker/core/__init__.py`**

Empty for now; re-exports come in later tasks as symbols are defined.

```python
"""Backend modules for Container Tracker. Pure logic, no Qt dependency."""
```

- [ ] **Step 6: Write `container_tracker/ui/__init__.py` and `tests/__init__.py`**

Both empty files:

```bash
: > container_tracker/ui/__init__.py
: > tests/__init__.py
```

- [ ] **Step 7: Install dev dependencies**

Run: `pip install -e ".[dev]"`
Expected: clean install; no errors.

- [ ] **Step 8: Verify pytest collects nothing**

Run: `pytest`
Expected output contains: `no tests ran in 0.XXs` (no tests exist yet).

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml container_tracker/ tests/__init__.py tests/fixtures/
git commit -m "scaffold: create container_tracker package layout and pyproject.toml"
```

---

## Task 2: `core/status.py` — normalize_status, compute_delay_days, bucket_counts

**Files:**
- Create: `tests/test_status.py`
- Create: `container_tracker/core/status.py`

Reference code in monolith:
- `_stat_counts` logic in `container_tracker_gui.py` around lines 1059–1066
- `delay_days` formatting in `extract_fields` at lines 595–604

- [ ] **Step 1: Write the failing test file `tests/test_status.py`**

```python
from container_tracker.core.status import (
    StatusBucket,
    bucket_counts,
    compute_delay_days,
    normalize_status,
)


class TestNormalizeStatus:
    def test_sailing_variants(self) -> None:
        assert normalize_status("SAILING") == StatusBucket.SAILING
        assert normalize_status("sailing") == StatusBucket.SAILING
        assert normalize_status("EN_ROUTE") == StatusBucket.SAILING
        assert normalize_status("en_route") == StatusBucket.SAILING

    def test_arrived_variants(self) -> None:
        assert normalize_status("ARRIVED") == StatusBucket.ARRIVED
        assert normalize_status("DISCHARGED") == StatusBucket.ARRIVED
        assert normalize_status("DELIVERED") == StatusBucket.ARRIVED
        assert normalize_status("GATE_OUT") == StatusBucket.ARRIVED
        assert normalize_status("gate_out") == StatusBucket.ARRIVED

    def test_pending_variants(self) -> None:
        assert normalize_status("BOOKED") == StatusBucket.PENDING
        assert normalize_status("NEW") == StatusBucket.PENDING
        assert normalize_status("") == StatusBucket.PENDING

    def test_unknown(self) -> None:
        assert normalize_status("GARBAGE") == StatusBucket.UNKNOWN
        assert normalize_status("loaded-on-vessel") == StatusBucket.UNKNOWN


class TestComputeDelayDays:
    def test_on_time(self) -> None:
        assert compute_delay_days("2026-05-01", "2026-05-01") == 0

    def test_delayed(self) -> None:
        assert compute_delay_days("2026-05-01", "2026-05-04") == 3

    def test_early(self) -> None:
        assert compute_delay_days("2026-05-10", "2026-05-07") == -3

    def test_tolerates_iso_with_time(self) -> None:
        # ShipsGo sometimes returns ISO timestamps. Only the date portion matters.
        assert compute_delay_days("2026-05-01T00:00:00Z", "2026-05-03T14:20:00Z") == 2

    def test_missing_original_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            compute_delay_days("", "2026-05-01")

    def test_missing_current_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            compute_delay_days("2026-05-01", "")

    def test_unparseable_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            compute_delay_days("not-a-date", "2026-05-01")


class TestBucketCounts:
    def test_empty_db(self) -> None:
        assert bucket_counts({}) == {"total": 0, "sailing": 0, "arrived": 0, "delayed": 0}

    def test_mixed_db(self) -> None:
        db = {
            "AAAA0000001": {"status": "SAILING", "delay_days_int": 0},
            "AAAA0000002": {"status": "SAILING", "delay_days_int": 3},   # counts as delayed
            "AAAA0000003": {"status": "ARRIVED", "delay_days_int": 5},   # not delayed (arrived)
            "AAAA0000004": {"status": "DELIVERED", "delay_days_int": 0},
            "AAAA0000005": {"status": "", "delay_days_int": None},
        }
        assert bucket_counts(db) == {"total": 5, "sailing": 2, "arrived": 2, "delayed": 1}

    def test_delayed_requires_sailing(self) -> None:
        # Per spec decision: delay-while-sailing only. Arrived-with-delay is not actionable.
        db = {"X": {"status": "ARRIVED", "delay_days_int": 7}}
        assert bucket_counts(db)["delayed"] == 0

    def test_missing_delay_field_does_not_count(self) -> None:
        db = {"X": {"status": "SAILING"}}
        assert bucket_counts(db)["delayed"] == 0
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `pytest tests/test_status.py -v`
Expected: `ModuleNotFoundError: No module named 'container_tracker.core.status'`

- [ ] **Step 3: Implement `container_tracker/core/status.py`**

```python
"""Status normalization, delay computation, and bucket counts.

Pure logic. No Qt, no I/O, no network.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class StatusBucket(str, Enum):
    SAILING = "SAILING"
    ARRIVED = "ARRIVED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"


_SAILING_TOKENS = {"SAILING", "EN_ROUTE"}
_ARRIVED_TOKENS = {"ARRIVED", "DISCHARGED", "DELIVERED", "GATE_OUT"}
_PENDING_TOKENS = {"BOOKED", "NEW", ""}


def normalize_status(raw: str) -> StatusBucket:
    """Map a raw ShipsGo status string to a StatusBucket.

    Matching is case-insensitive; whitespace is ignored.
    Unrecognized values return StatusBucket.UNKNOWN.
    """
    key = (raw or "").strip().upper()
    if key in _SAILING_TOKENS:
        return StatusBucket.SAILING
    if key in _ARRIVED_TOKENS:
        return StatusBucket.ARRIVED
    if key in _PENDING_TOKENS:
        return StatusBucket.PENDING
    return StatusBucket.UNKNOWN


def compute_delay_days(original_eta: str, current_eta: str) -> int:
    """Days of delay between original and current ETA. Positive = delayed.

    Accepts either plain `YYYY-MM-DD` or ISO timestamps; only the date portion
    is used. Raises ValueError if either input is missing or unparseable.
    """
    if not original_eta or not current_eta:
        raise ValueError("compute_delay_days requires both original and current ETA")
    original = _parse_date(original_eta)
    current = _parse_date(current_eta)
    return (current - original).days


def _parse_date(value: str) -> datetime:
    date_part = str(value).split("T", 1)[0]
    return datetime.strptime(date_part, "%Y-%m-%d")


def bucket_counts(db: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    """Return {"total", "sailing", "arrived", "delayed"} counts for the tracking DB.

    Delayed is defined as: status bucket == SAILING AND delay_days_int > 0.
    Records missing delay_days_int do not count as delayed.
    """
    total = len(db)
    sailing = 0
    arrived = 0
    delayed = 0
    for record in db.values():
        bucket = normalize_status(str(record.get("status", "")))
        if bucket == StatusBucket.SAILING:
            sailing += 1
            delay = record.get("delay_days_int")
            if isinstance(delay, int) and delay > 0:
                delayed += 1
        elif bucket == StatusBucket.ARRIVED:
            arrived += 1
    return {"total": total, "sailing": sailing, "arrived": arrived, "delayed": delayed}
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `pytest tests/test_status.py -v`
Expected: all 12 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_status.py container_tracker/core/status.py
git commit -m "core: extract status bucket / delay-days / counts to core.status"
```

---

## Task 3: `core/api.py` part 1 — SCAC map and resolve_scac

**Files:**
- Create: `tests/test_api.py`
- Create: `container_tracker/core/api.py`

Reference code in monolith:
- `CARRIER_SCAC_MAP`, `CARRIER_NAMES` at `container_tracker_gui.py:319–325`
- `resolve_scac` at `container_tracker_gui.py:329–331`

- [ ] **Step 1: Write the failing tests into `tests/test_api.py`**

```python
from container_tracker.core.api import CARRIER_NAMES, CARRIER_SCAC_MAP, resolve_scac


class TestResolveScac:
    def test_known_carrier_by_long_name(self) -> None:
        assert resolve_scac("MAERSK LINE") == "MAEU"
        assert resolve_scac("Hapag-Lloyd") == "HLCU"

    def test_case_and_whitespace_normalized(self) -> None:
        assert resolve_scac("  maersk  ") == "MAEU"

    def test_four_letter_code_passthrough(self) -> None:
        assert resolve_scac("MSCU") == "MSCU"

    def test_unknown_returns_upper_input(self) -> None:
        assert resolve_scac("NONSENSE") == "NONSENSE"


class TestCarrierMetadata:
    def test_scac_map_covers_named_carriers(self) -> None:
        # Every long name in CARRIER_NAMES (except "OTHER") resolves to a SCAC
        for name in CARRIER_NAMES:
            if name == "OTHER":
                continue
            assert resolve_scac(name) != "", f"{name} has no SCAC mapping"

    def test_all_scacs_are_four_letters(self) -> None:
        for scac in CARRIER_SCAC_MAP.values():
            assert len(scac) == 4 and scac.isalpha(), f"bad SCAC: {scac}"
```

- [ ] **Step 2: Run tests and confirm they fail**

Run: `pytest tests/test_api.py -v`
Expected: `ModuleNotFoundError: No module named 'container_tracker.core.api'`

- [ ] **Step 3: Implement the SCAC portion of `container_tracker/core/api.py`**

```python
"""ShipsGo API v2 client and response parsing.

Pure logic. Constructing a client does not make a network call.
"""
from __future__ import annotations


CARRIER_SCAC_MAP: dict[str, str] = {
    "MAERSK":       "MAEU",
    "MAERSK LINE":  "MAEU",
    "MSC":          "MSCU",
    "CMA CGM":      "CMDU",
    "HAPAG LLOYD":  "HLCU",
    "HAPAG-LLOYD":  "HLCU",
    "COSCO":        "COSU",
    "EVERGREEN":    "EGLV",
    "ONE":          "ONEY",
    "YANG MING":    "YMLU",
    "ZIM":          "ZIMU",
    "HMM":          "HDMU",
    "OOCL":         "OOLU",
    "PIL":          "PILU",
}

CARRIER_NAMES: list[str] = [
    "MAERSK LINE", "MSC", "CMA CGM", "HAPAG LLOYD", "COSCO",
    "EVERGREEN", "ONE", "YANG MING", "ZIM", "HMM", "OOCL", "PIL", "OTHER",
]


def resolve_scac(line: str) -> str:
    """Resolve a shipping-line name to a SCAC code.

    Known names map via CARRIER_SCAC_MAP. A four-letter input is assumed to
    already be a SCAC. Otherwise the uppercased input is returned unchanged.
    """
    upper = line.strip().upper()
    return CARRIER_SCAC_MAP.get(upper, upper)
```

- [ ] **Step 4: Run tests and confirm they pass**

Run: `pytest tests/test_api.py -v`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_api.py container_tracker/core/api.py
git commit -m "core: extract CARRIER_SCAC_MAP + resolve_scac to core.api"
```

---

## Task 4: `core/api.py` part 2 — extract_fields + JSON fixtures

**Files:**
- Create: `tests/fixtures/shipsgo_sailing.json`
- Create: `tests/fixtures/shipsgo_arrived.json`
- Modify: `tests/test_api.py` (add extract_fields tests)
- Modify: `container_tracker/core/api.py` (add extract_fields + compute_delay_days integration)

Reference code in monolith:
- `extract_fields` at `container_tracker_gui.py:576–613`

- [ ] **Step 1: Create `tests/fixtures/shipsgo_sailing.json`**

Realistic ShipsGo v2 shipment payload for a sailing container with delay.

```json
{
  "message": "ok",
  "shipment": {
    "id": "ship_abc123",
    "container_number": "MSKU1234567",
    "status": "SAILING",
    "carrier": {
      "scac": "MAEU",
      "name": "MAERSK LINE"
    },
    "route": {
      "transit_percentage": 42,
      "port_of_loading": {
        "location": { "name": "Shanghai, China" },
        "date_of_loading": "2026-04-01T10:00:00Z"
      },
      "port_of_discharge": {
        "location": { "name": "Los Angeles, USA" },
        "date_of_discharge": "2026-05-05T00:00:00Z",
        "date_of_discharge_initial": "2026-05-01T00:00:00Z"
      }
    },
    "containers": [
      {
        "number": "MSKU1234567",
        "movements": [
          { "vessel": null, "event": "GATE_IN" },
          { "vessel": { "name": "MV SEA PIONEER", "imo": "9876543" }, "event": "LOAD" },
          { "vessel": { "name": "MV SEA PIONEER", "imo": "9876543" }, "event": "DEPARTED" }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Create `tests/fixtures/shipsgo_arrived.json`**

```json
{
  "message": "ok",
  "shipment": {
    "id": "ship_def456",
    "container_number": "CMAU7654321",
    "status": "ARRIVED",
    "carrier": { "scac": "CMDU", "name": "CMA CGM" },
    "route": {
      "transit_percentage": 100,
      "port_of_loading": {
        "location": { "name": "Ningbo, China" },
        "date_of_loading": "2026-02-14"
      },
      "port_of_discharge": {
        "location": { "name": "Long Beach, USA" },
        "date_of_discharge": "2026-03-20",
        "date_of_discharge_initial": "2026-03-20"
      }
    },
    "containers": [
      {
        "number": "CMAU7654321",
        "movements": [
          { "vessel": { "name": "MV PACIFIC STAR" }, "event": "LOAD" },
          { "vessel": { "name": "MV PACIFIC STAR" }, "event": "DISCHARGED" }
        ]
      }
    ]
  }
}
```

- [ ] **Step 3: Add the failing `extract_fields` tests to `tests/test_api.py`**

Append to the existing `tests/test_api.py`:

```python
import json
from pathlib import Path

from container_tracker.core.api import extract_fields


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestExtractFields:
    def test_sailing_shipment_fields(self) -> None:
        result = extract_fields(_load("shipsgo_sailing.json"))
        assert result["status"] == "SAILING"
        assert result["carrier"] == "MAERSK LINE"
        assert result["pol"] == "Shanghai, China"
        assert result["pod"] == "Los Angeles, USA"
        assert result["etd"] == "2026-04-01"
        assert result["eta"] == "2026-05-05"
        assert result["original_eta"] == "2026-05-01"
        assert result["delay_days_int"] == 4
        assert result["delay_days"] == "+4 days"
        assert result["vessel"] == "MV SEA PIONEER"
        assert result["transit_pct"] == 42

    def test_arrived_shipment_fields(self) -> None:
        result = extract_fields(_load("shipsgo_arrived.json"))
        assert result["status"] == "ARRIVED"
        assert result["pol"] == "Ningbo, China"
        assert result["pod"] == "Long Beach, USA"
        assert result["eta"] == "2026-03-20"
        assert result["original_eta"] == "2026-03-20"
        assert result["delay_days_int"] == 0
        assert result["delay_days"] == "On time"
        assert result["vessel"] == "MV PACIFIC STAR"
        assert result["transit_pct"] == 100

    def test_unwrapped_payload_also_works(self) -> None:
        # If caller passes shipment dict directly (not wrapped in {"shipment": ...})
        raw = _load("shipsgo_sailing.json")["shipment"]
        result = extract_fields(raw)
        assert result["status"] == "SAILING"
        assert result["pol"] == "Shanghai, China"

    def test_missing_route_degrades_gracefully(self) -> None:
        result = extract_fields({"shipment": {"status": "BOOKED"}})
        assert result["status"] == "BOOKED"
        assert result["pol"] == ""
        assert result["pod"] == ""
        assert result["eta"] == ""
        assert result["original_eta"] == ""
        assert result["delay_days"] == ""
        assert result["delay_days_int"] is None

    def test_early_arrival_formats_negative(self) -> None:
        payload = {"shipment": {
            "status": "SAILING",
            "route": {
                "port_of_discharge": {
                    "date_of_discharge": "2026-05-01",
                    "date_of_discharge_initial": "2026-05-04",
                }
            }
        }}
        result = extract_fields(payload)
        assert result["delay_days_int"] == -3
        assert result["delay_days"] == "-3 days (early)"

    def test_vessel_from_last_movement_with_vessel(self) -> None:
        # Most recent movement with a vessel wins; earlier null-vessel movements ignored.
        payload = {"shipment": {
            "containers": [{"movements": [
                {"vessel": {"name": "MV A"}},
                {"vessel": None},
                {"vessel": {"name": "MV B"}},
            ]}]
        }}
        assert extract_fields(payload)["vessel"] == "MV B"
```

- [ ] **Step 4: Run tests and confirm extract_fields tests fail**

Run: `pytest tests/test_api.py -v`
Expected: `ImportError: cannot import name 'extract_fields' from 'container_tracker.core.api'`

- [ ] **Step 5: Add `extract_fields` to `container_tracker/core/api.py`**

Append these imports and functions to the existing file (below `resolve_scac`):

```python
from typing import Any

from container_tracker.core.status import compute_delay_days


def extract_fields(shipment: dict[str, Any]) -> dict[str, Any]:
    """Pull display-ready fields from a ShipsGo v2 shipment response.

    Accepts either `{"shipment": {...}}` (the GET-by-id shape) or the bare
    shipment dict. All missing fields degrade to empty strings; `delay_days_int`
    is None when original/current ETA can't be compared.
    """
    if "shipment" in shipment and isinstance(shipment["shipment"], dict):
        shipment = shipment["shipment"]

    fields: dict[str, Any] = {
        "status": shipment.get("status", ""),
        "vessel": "",
        "pol": "",
        "pod": "",
        "eta": "",
        "etd": "",
        "carrier": "",
        "transit_pct": "",
        "original_eta": "",
        "delay_days": "",
        "delay_days_int": None,
    }

    carrier = shipment.get("carrier") or {}
    if isinstance(carrier, dict):
        fields["carrier"] = carrier.get("name", carrier.get("scac", ""))

    route = shipment.get("route") or {}

    pol = route.get("port_of_loading") or route.get("origin") or {}
    pol_loc = pol.get("location") or {}
    fields["pol"] = pol_loc.get("name", "")
    fields["etd"] = pol.get("date_of_loading", pol.get("date_of_dep", ""))

    pod = route.get("port_of_discharge") or route.get("destination") or {}
    pod_loc = pod.get("location") or {}
    fields["pod"] = pod_loc.get("name", "")
    fields["eta"] = pod.get("date_of_discharge", pod.get("date_of_eta", ""))
    fields["original_eta"] = pod.get(
        "date_of_discharge_initial",
        pod.get("date_of_eta_initial", ""),
    )

    fields["transit_pct"] = route.get("transit_percentage", "")

    # Trim any ISO date strings down to YYYY-MM-DD.
    for key in ("eta", "etd", "original_eta"):
        value = fields[key]
        if value and "T" in str(value):
            fields[key] = str(value).split("T")[0]

    # Delay — numeric and formatted. Either may be absent.
    try:
        diff = compute_delay_days(fields["original_eta"], fields["eta"])
        fields["delay_days_int"] = diff
        if diff > 0:
            fields["delay_days"] = f"+{diff} days"
        elif diff < 0:
            fields["delay_days"] = f"{diff} days (early)"
        else:
            fields["delay_days"] = "On time"
    except ValueError:
        fields["delay_days_int"] = None
        fields["delay_days"] = ""

    # Vessel — most recent movement with a vessel dict wins.
    containers = shipment.get("containers") or []
    if containers and isinstance(containers[0], dict):
        movements = containers[0].get("movements") or []
        for movement in reversed(movements):
            if isinstance(movement, dict) and movement.get("vessel"):
                vessel = movement["vessel"]
                if isinstance(vessel, dict) and vessel.get("name"):
                    fields["vessel"] = vessel["name"]
                    break

    return fields
```

- [ ] **Step 6: Run tests and confirm all pass**

Run: `pytest tests/test_api.py -v`
Expected: all 12 tests pass (6 from Task 3 + 6 new).

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/ tests/test_api.py container_tracker/core/api.py
git commit -m "core: extract ShipsGo v2 response parsing (extract_fields)"
```

---

## Task 5: `core/api.py` part 3 — ShipsGoClient and ShipsGoAuthError

**Files:**
- Modify: `tests/test_api.py` (add client tests)
- Modify: `container_tracker/core/api.py` (add class + exception + constants)

Reference code in monolith:
- `ShipsGoClient` at `container_tracker_gui.py:552–574`
- `API_BASE` at `container_tracker_gui.py:113`

This task uses `responses` to mock HTTP. Ensure it's installed via `pip install responses`.

- [ ] **Step 1: Add failing client tests to `tests/test_api.py`**

Append to the existing file:

```python
import pytest
import responses

from container_tracker.core.api import API_BASE, ShipsGoAuthError, ShipsGoClient


class TestShipsGoClient:
    @responses.activate
    def test_create_shipment_success(self) -> None:
        responses.add(
            responses.POST,
            f"{API_BASE}/ocean/shipments",
            json={"id": "ship_new_001"},
            status=200,
        )
        client = ShipsGoClient("tok-valid")
        result = client.create_shipment(container_number="mSKu1234567", carrier_scac="maeu")
        assert result == {"id": "ship_new_001"}

        # Verify the request body upper-cased the container number and SCAC
        request = responses.calls[0].request
        import json as _json
        body = _json.loads(request.body)
        assert body["container_number"] == "MSKU1234567"
        assert body["carrier_scac"] == "MAEU"
        assert request.headers["X-Shipsgo-User-Token"] == "tok-valid"

    @responses.activate
    def test_create_shipment_already_tracked_409(self) -> None:
        responses.add(
            responses.POST,
            f"{API_BASE}/ocean/shipments",
            json={"error": "already exists"},
            status=409,
        )
        client = ShipsGoClient("tok")
        result = client.create_shipment(container_number="MSKU1234567")
        assert result == {"already_exists": True}

    @responses.activate
    def test_create_shipment_insufficient_credits_402(self) -> None:
        responses.add(
            responses.POST,
            f"{API_BASE}/ocean/shipments",
            json={"error": "no credits"},
            status=402,
        )
        client = ShipsGoClient("tok")
        result = client.create_shipment(container_number="MSKU1234567")
        assert result == {"error": "NOT_ENOUGH_CREDITS"}

    @responses.activate
    def test_create_shipment_401_raises_auth_error(self) -> None:
        responses.add(
            responses.POST,
            f"{API_BASE}/ocean/shipments",
            json={"error": "invalid token"},
            status=401,
        )
        client = ShipsGoClient("tok-bad")
        with pytest.raises(ShipsGoAuthError):
            client.create_shipment(container_number="MSKU1234567")

    @responses.activate
    def test_list_shipments_401_raises_auth_error(self) -> None:
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments",
            json={"error": "invalid token"},
            status=401,
        )
        client = ShipsGoClient("tok-bad")
        with pytest.raises(ShipsGoAuthError):
            client.list_shipments()

    @responses.activate
    def test_get_shipment_401_raises_auth_error(self) -> None:
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments/ship_x",
            json={"error": "invalid token"},
            status=401,
        )
        client = ShipsGoClient("tok-bad")
        with pytest.raises(ShipsGoAuthError):
            client.get_shipment("ship_x")

    @responses.activate
    def test_list_shipments_unwraps_shipments_key(self) -> None:
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments",
            json={"shipments": [{"id": "a"}, {"id": "b"}]},
            status=200,
        )
        client = ShipsGoClient("tok")
        assert client.list_shipments() == [{"id": "a"}, {"id": "b"}]

    @responses.activate
    def test_list_shipments_unwraps_data_key(self) -> None:
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments",
            json={"data": [{"id": "a"}]},
            status=200,
        )
        client = ShipsGoClient("tok")
        assert client.list_shipments() == [{"id": "a"}]

    @responses.activate
    def test_list_shipments_passes_list_through(self) -> None:
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments",
            json=[{"id": "a"}],
            status=200,
        )
        client = ShipsGoClient("tok")
        assert client.list_shipments() == [{"id": "a"}]

    @responses.activate
    def test_get_shipment_returns_json(self) -> None:
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments/ship_x",
            json={"shipment": {"id": "ship_x", "status": "SAILING"}},
            status=200,
        )
        client = ShipsGoClient("tok")
        result = client.get_shipment("ship_x")
        assert result["shipment"]["status"] == "SAILING"

    @responses.activate
    def test_500_raises_http_error(self) -> None:
        import requests
        responses.add(
            responses.GET,
            f"{API_BASE}/ocean/shipments",
            status=500,
        )
        client = ShipsGoClient("tok")
        with pytest.raises(requests.HTTPError):
            client.list_shipments()
```

- [ ] **Step 2: Run tests and confirm they fail**

Run: `pytest tests/test_api.py -v`
Expected: `ImportError: cannot import name 'ShipsGoClient'` (and friends).

- [ ] **Step 3: Add ShipsGoClient + ShipsGoAuthError to `container_tracker/core/api.py`**

Append to the existing file:

```python
import requests


API_BASE = "https://api.shipsgo.com/v2"


class ShipsGoAuthError(Exception):
    """Raised when ShipsGo rejects the API token (HTTP 401).

    The UI layer catches this specifically to surface a modal prompting the
    user to open Settings and update their key.
    """


class ShipsGoClient:
    """Synchronous client for the ShipsGo v2 ocean-shipments endpoints.

    Constructor is cheap — builds a requests.Session but makes no network
    calls. Thread-safety: reuse a single client across background QRunnables
    is fine, but each call is independent (no shared mutable state beyond the
    session's connection pool).
    """

    def __init__(self, token: str) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Shipsgo-User-Token": token,
        })

    def create_shipment(
        self,
        container_number: str = "",
        carrier_scac: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, str] = {}
        if container_number:
            payload["container_number"] = container_number.strip().upper()
        if carrier_scac:
            payload["carrier_scac"] = carrier_scac.strip().upper()
        response = self.session.post(
            f"{API_BASE}/ocean/shipments",
            json=payload,
            timeout=30,
        )
        if response.status_code == 401:
            raise ShipsGoAuthError("ShipsGo rejected the API token")
        if response.status_code == 409:
            return {"already_exists": True}
        if response.status_code == 402:
            return {"error": "NOT_ENOUGH_CREDITS"}
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def list_shipments(self, take: int = 100) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{API_BASE}/ocean/shipments",
            params={"take": take},
            timeout=30,
        )
        if response.status_code == 401:
            raise ShipsGoAuthError("ShipsGo rejected the API token")
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data.get("shipments", data.get("data", []))  # type: ignore[no-any-return]
        return data  # type: ignore[no-any-return]

    def get_shipment(self, shipment_id: str) -> dict[str, Any]:
        response = self.session.get(
            f"{API_BASE}/ocean/shipments/{shipment_id}",
            timeout=30,
        )
        if response.status_code == 401:
            raise ShipsGoAuthError("ShipsGo rejected the API token")
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]
```

- [ ] **Step 4: Run tests and confirm all pass**

Run: `pytest tests/test_api.py -v`
Expected: all 23 tests pass (12 from Tasks 3–4 + 11 new).

- [ ] **Step 5: Commit**

```bash
git add tests/test_api.py container_tracker/core/api.py
git commit -m "core: extract ShipsGoClient; add ShipsGoAuthError for 401 handling"
```

---

## Task 6: `core/persistence.py` — paths, config, keyring, tracking data

**Files:**
- Create: `tests/test_persistence.py`
- Create: `container_tracker/core/persistence.py`

Reference code in monolith:
- `get_data_dir`, `get_api_token`, `set_api_token`, `load_config`, `save_config`, `is_first_run` in `container_tracker_gui.py:127–362`
- Constants `APP_SHORT_NAME`, `KEYRING_SERVICE`, `KEYRING_USER` at `container_tracker_gui.py:46, 114`

All keyring behavior is tested via `monkeypatch`, so tests don't touch the real Credential Manager.

- [ ] **Step 1: Write the failing `tests/test_persistence.py`**

```python
from pathlib import Path

import pytest

from container_tracker.core import persistence


class TestDataDir:
    def test_data_dir_on_windows(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(persistence, "_PLATFORM", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        result = persistence.data_dir()
        assert result == tmp_path / "ContainerTracker"
        assert result.is_dir()

    def test_paths_derive_from_data_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(persistence, "_PLATFORM", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        d = persistence.data_dir()
        assert persistence.config_path() == d / "config.json"
        assert persistence.tracking_data_path() == d / "tracking_data.json"
        assert persistence.log_path() == d / "tracker.log"


class TestConfig:
    def _setup_tmp_appdata(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(persistence, "_PLATFORM", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path))

    def test_load_config_missing_returns_defaults(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._setup_tmp_appdata(monkeypatch, tmp_path)
        cfg = persistence.load_config()
        assert cfg == {
            "company_name": "",
            "contact_email": "",
            "excel_path": "",
            "dark_mode": False,
            "dismissed": [],
        }

    def test_save_then_load_roundtrip(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._setup_tmp_appdata(monkeypatch, tmp_path)
        original = {
            "company_name": "Acme Imports",
            "contact_email": "ops@acme.test",
            "excel_path": str(tmp_path / "containers.xlsx"),
            "dark_mode": True,
            "dismissed": ["MSKU1111111"],
        }
        persistence.save_config(original)
        loaded = persistence.load_config()
        assert loaded == original

    def test_save_strips_api_key_field(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Spec §3/§10.3: api_key must NEVER appear in config.json."""
        self._setup_tmp_appdata(monkeypatch, tmp_path)
        persistence.save_config({
            "company_name": "Acme",
            "contact_email": "a@b.c",
            "excel_path": "",
            "dark_mode": False,
            "dismissed": [],
            "api_key": "SHOULD-NEVER-APPEAR",
        })
        raw = persistence.config_path().read_text()
        assert "SHOULD-NEVER-APPEAR" not in raw
        assert "api_key" not in raw


class TestKeyring:
    def test_get_api_token_returns_stored_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        store: dict[tuple[str, str], str] = {
            (persistence.KEYRING_SERVICE, persistence.KEYRING_USER): "tok-123"
        }
        monkeypatch.setattr(persistence._keyring, "get_password", lambda s, u: store.get((s, u)))
        assert persistence.get_api_token() == "tok-123"

    def test_get_api_token_empty_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(persistence._keyring, "get_password", lambda s, u: None)
        assert persistence.get_api_token() == ""

    def test_set_api_token_stores_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        store: dict[tuple[str, str], str] = {}
        def set_password(s: str, u: str, v: str) -> None:
            store[(s, u)] = v
        monkeypatch.setattr(persistence._keyring, "set_password", set_password)
        persistence.set_api_token("tok-new")
        assert store[(persistence.KEYRING_SERVICE, persistence.KEYRING_USER)] == "tok-new"

    def test_get_api_token_swallows_backend_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def explode(s: str, u: str) -> None:
            raise RuntimeError("no backend")
        monkeypatch.setattr(persistence._keyring, "get_password", explode)
        assert persistence.get_api_token() == ""


class TestIsFirstRun:
    def test_empty_config_and_no_token_is_first_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(persistence, "get_api_token", lambda: "")
        assert persistence.is_first_run({"company_name": "", "contact_email": ""}) is True

    def test_company_present_is_not_first_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(persistence, "get_api_token", lambda: "")
        assert persistence.is_first_run({"company_name": "Acme", "contact_email": ""}) is False

    def test_token_present_is_not_first_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(persistence, "get_api_token", lambda: "tok")
        assert persistence.is_first_run({"company_name": "", "contact_email": ""}) is False


class TestTrackingData:
    def test_roundtrip_empty(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(persistence, "_PLATFORM", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        persistence.save_tracking_data({})
        assert persistence.load_tracking_data() == {}

    def test_roundtrip_records(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(persistence, "_PLATFORM", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        db = {
            "MSKU1234567": {"status": "SAILING", "delay_days_int": 3, "vessel": "MV TEST"},
            "CMAU7654321": {"status": "ARRIVED", "delay_days_int": 0},
        }
        persistence.save_tracking_data(db)
        assert persistence.load_tracking_data() == db
```

- [ ] **Step 2: Run tests and confirm they fail**

Run: `pytest tests/test_persistence.py -v`
Expected: `ModuleNotFoundError: No module named 'container_tracker.core.persistence'`

- [ ] **Step 3: Implement `container_tracker/core/persistence.py`**

```python
"""Config, keyring, and tracking-data persistence.

Platform: Windows in production. `_PLATFORM` is a module attribute (not a
direct `sys.platform` reference) so tests can monkeypatch it cleanly.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import keyring as _keyring


logger = logging.getLogger(__name__)

APP_SHORT_NAME = "ContainerTracker"
KEYRING_SERVICE = f"{APP_SHORT_NAME}_shipsgo_api"
KEYRING_USER = "default"

# Module-level so tests can monkeypatch.
_PLATFORM: str = sys.platform

_DEFAULT_CONFIG: dict[str, Any] = {
    "company_name": "",
    "contact_email": "",
    "excel_path": "",
    "dark_mode": False,
    "dismissed": [],
}


def data_dir() -> Path:
    """Return %APPDATA%\\ContainerTracker on Windows, ~/.config/ContainerTracker elsewhere.

    Creates the directory if missing.
    """
    if _PLATFORM == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path.home() / ".config"
    path = base / APP_SHORT_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return data_dir() / "config.json"


def tracking_data_path() -> Path:
    return data_dir() / "tracking_data.json"


def log_path() -> Path:
    return data_dir() / "tracker.log"


def load_config() -> dict[str, Any]:
    """Read config.json. Missing file → default dict. Missing keys → backfilled from defaults."""
    path = config_path()
    if not path.exists():
        return dict(_DEFAULT_CONFIG)
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    merged = dict(_DEFAULT_CONFIG)
    if isinstance(loaded, dict):
        merged.update({k: loaded[k] for k in loaded if k in _DEFAULT_CONFIG})
    return merged


def save_config(config: dict[str, Any]) -> None:
    """Write config.json atomically. Strips any forbidden keys (notably `api_key`)."""
    safe = {k: v for k, v in config.items() if k in _DEFAULT_CONFIG}
    path = config_path()
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(safe, handle, indent=2, default=str)
    tmp.replace(path)


def load_tracking_data() -> dict[str, Any]:
    path = tracking_data_path()
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def save_tracking_data(db: dict[str, Any]) -> None:
    path = tracking_data_path()
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(db, handle, indent=2, default=str)
    tmp.replace(path)


def get_api_token() -> str:
    """Read the ShipsGo token from the OS keyring. Returns "" on any failure."""
    try:
        value = _keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception as exc:  # pragma: no cover - defensive
        logger.info("keyring read failed: %s", exc)
        return ""
    return value or ""


def set_api_token(token: str) -> None:
    """Write the ShipsGo token to the OS keyring. Logs and swallows backend failures."""
    try:
        _keyring.set_password(KEYRING_SERVICE, KEYRING_USER, token)
    except Exception as exc:  # pragma: no cover - defensive
        logger.info("keyring write failed: %s", exc)


def is_first_run(config: dict[str, Any]) -> bool:
    """True iff `company_name` is missing/empty AND no keyring token exists."""
    has_company = bool(config.get("company_name"))
    has_token = bool(get_api_token())
    return not (has_company or has_token)
```

- [ ] **Step 4: Run tests and confirm they pass**

Run: `pytest tests/test_persistence.py -v`
Expected: all 14 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_persistence.py container_tracker/core/persistence.py
git commit -m "core: extract config + keyring + tracking-data persistence"
```

---

## Task 7: `core/excel.py` — read / write / template + ExcelFormatError

**Files:**
- Create: `tests/test_excel.py`
- Create: `container_tracker/core/excel.py`

Reference code in monolith:
- `read_containers_from_excel`, `update_excel_with_tracking`, `create_template_excel`, helpers `find_container_column`, `find_or_create_tracking_columns`, `TRACKING_COL_MAP`, `CONTAINER_COL_KEYWORDS` at `container_tracker_gui.py:615–735`

The new module exposes three public functions with cleaner names. The private helpers stay private.

- [ ] **Step 1: Write the failing `tests/test_excel.py`**

```python
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from container_tracker.core.excel import (
    ExcelFormatError,
    create_template,
    read_container_list,
    write_tracking_report,
)


def _make_workbook(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    wb = Workbook()
    ws = wb.active
    for col, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=header)
    for row_idx, row in enumerate(rows, start=2):
        for col, value in enumerate(row, start=1):
            ws.cell(row=row_idx, column=col, value=value)
    wb.save(str(path))
    wb.close()


class TestReadContainerList:
    def test_reads_container_numbers(self, tmp_path: Path) -> None:
        path = tmp_path / "c.xlsx"
        _make_workbook(path, ["Container #", "Notes"], [
            ["MSKU1234567", "sample"],
            ["CMAU7654321", "another"],
        ])
        assert read_container_list(path) == ["MSKU1234567", "CMAU7654321"]

    def test_upper_cases_and_strips(self, tmp_path: Path) -> None:
        path = tmp_path / "c.xlsx"
        _make_workbook(path, ["Container #"], [["  msku1234567  "], ["cmau7654321"]])
        assert read_container_list(path) == ["MSKU1234567", "CMAU7654321"]

    def test_ignores_unexpected_columns(self, tmp_path: Path) -> None:
        path = tmp_path / "c.xlsx"
        _make_workbook(path, ["Container #", "Random Column", "Another"], [
            ["MSKU1234567", "x", "y"],
        ])
        assert read_container_list(path) == ["MSKU1234567"]

    def test_accepts_alternate_header_cntr(self, tmp_path: Path) -> None:
        path = tmp_path / "c.xlsx"
        _make_workbook(path, ["Cntr No"], [["MSKU1234567"]])
        assert read_container_list(path) == ["MSKU1234567"]

    def test_missing_container_column_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "c.xlsx"
        _make_workbook(path, ["Carrier", "Vessel"], [["MAERSK", "MV TEST"]])
        with pytest.raises(ExcelFormatError) as exc_info:
            read_container_list(path)
        # The error message must be user-friendly and mention the path.
        assert "Container" in str(exc_info.value)
        assert str(path) in str(exc_info.value)

    def test_skips_empty_and_short_values(self, tmp_path: Path) -> None:
        path = tmp_path / "c.xlsx"
        _make_workbook(path, ["Container #"], [
            ["MSKU1234567"],
            [None],
            [""],
            ["SHORT"],           # under 10 chars — skip
            ["CMAU7654321"],
        ])
        assert read_container_list(path) == ["MSKU1234567", "CMAU7654321"]


class TestWriteTrackingReport:
    def test_writes_tracking_columns_for_known_container(self, tmp_path: Path) -> None:
        path = tmp_path / "c.xlsx"
        _make_workbook(path, ["Container #", "Reference"], [["MSKU1234567", "PO-1"]])
        db = {"MSKU1234567": {
            "carrier": "MAERSK LINE",
            "status": "SAILING",
            "eta": "2026-05-05",
            "original_eta": "2026-05-01",
            "delay_days": "+4 days",
            "pol": "Shanghai",
            "pod": "Los Angeles",
            "vessel": "MV TEST",
            "transit_pct": 42,
        }}
        count = write_tracking_report(path, db)
        assert count == 1

        wb = load_workbook(str(path))
        ws = wb.active
        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        assert "Status" in headers
        assert "ETA" in headers
        status_col = headers.index("Status") + 1
        eta_col = headers.index("ETA") + 1
        assert ws.cell(row=2, column=status_col).value == "SAILING"
        assert ws.cell(row=2, column=eta_col).value == "2026-05-05"
        wb.close()

    def test_appends_containers_not_in_spreadsheet(self, tmp_path: Path) -> None:
        path = tmp_path / "c.xlsx"
        _make_workbook(path, ["Container #"], [["MSKU1234567"]])
        db = {
            "MSKU1234567": {"status": "SAILING"},
            "NEW9999999A": {"status": "BOOKED"},  # not in sheet yet
        }
        write_tracking_report(path, db)

        wb = load_workbook(str(path))
        ws = wb.active
        container_col_values = [ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)]
        assert "MSKU1234567" in container_col_values
        assert "NEW9999999A" in container_col_values
        wb.close()

    def test_missing_container_column_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "c.xlsx"
        _make_workbook(path, ["Carrier"], [["MAERSK"]])
        with pytest.raises(ExcelFormatError):
            write_tracking_report(path, {"MSKU1234567": {"status": "SAILING"}})


class TestCreateTemplate:
    def test_creates_file_with_expected_headers(self, tmp_path: Path) -> None:
        path = tmp_path / "template.xlsx"
        create_template(path)
        assert path.exists()
        wb = load_workbook(str(path))
        ws = wb.active
        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        assert "Container #" in headers
        assert "Carrier" in headers
        assert "Status" in headers
        wb.close()

    def test_template_is_readable_by_read_container_list(self, tmp_path: Path) -> None:
        path = tmp_path / "template.xlsx"
        create_template(path)
        # The template ships with sample rows — should be readable without error.
        result = read_container_list(path)
        assert isinstance(result, list)
        assert len(result) >= 1
```

- [ ] **Step 2: Run tests and confirm they fail**

Run: `pytest tests/test_excel.py -v`
Expected: `ModuleNotFoundError: No module named 'container_tracker.core.excel'`

- [ ] **Step 3: Implement `container_tracker/core/excel.py`**

```python
"""Excel read/write against the user's linked .xlsx.

Posture: best-effort reads. Unexpected columns are ignored. A missing
container-number column raises `ExcelFormatError` with a message the UI
displays verbatim. Merged cells / named ranges / formulas are handled only
as far as openpyxl's `data_only=True` returns them natively.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo


class ExcelFormatError(ValueError):
    """Raised when the linked workbook can't be used (missing Container column, etc.).

    `str(exc)` is displayed verbatim by the UI, so messages should be
    user-facing and mention the affected file path.
    """


# Column name → tracking-record field key. These are the columns written
# into the user's linked workbook during `write_tracking_report`.
_TRACKING_COL_MAP: dict[str, str] = {
    "Carrier":            "carrier",
    "Status":             "status",
    "ETA":                "eta",
    "Original ETA":       "original_eta",
    "Delay":              "delay_days",
    "Port of Loading":    "pol",
    "Port of Discharge":  "pod",
    "Vessel":             "vessel",
    "Transit %":          "transit_pct",
    "Last Refreshed":     "last_refreshed",
}

_CONTAINER_COL_KEYWORDS = (
    "container", "cntr", "container #", "container number",
    "container_number", "container no", "cntr #", "cntr no",
)

_EST = timezone(timedelta(hours=-5))


def _now_est_str() -> str:
    return datetime.now(_EST).strftime("%Y-%m-%d %I:%M %p EST")


def _find_container_column(ws: Any) -> int | None:
    for col in range(1, ws.max_column + 1):
        header = str(ws.cell(row=1, column=col).value or "").strip().lower()
        if header in _CONTAINER_COL_KEYWORDS:
            return col
    for col in range(1, ws.max_column + 1):
        header = str(ws.cell(row=1, column=col).value or "").strip().lower()
        if "container" in header or "cntr" in header:
            return col
    return None


def _find_or_create_tracking_columns(ws: Any) -> dict[str, int]:
    existing: dict[str, int] = {}
    for col in range(1, ws.max_column + 1):
        header = str(ws.cell(row=1, column=col).value or "").strip()
        if header:
            existing[header.lower()] = col

    header_font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")

    column_for_field: dict[str, int] = {}
    next_col = ws.max_column + 1
    for header_name, field_key in _TRACKING_COL_MAP.items():
        if header_name.lower() in existing:
            column_for_field[field_key] = existing[header_name.lower()]
        else:
            cell = ws.cell(row=1, column=next_col, value=header_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            column_for_field[field_key] = next_col
            next_col += 1
    return column_for_field


def read_container_list(path: Path) -> list[str]:
    """Return the upper-cased container numbers from column 'Container #' (or similar).

    Values shorter than 10 characters are skipped (ShipsGo container numbers are
    always 11 chars; 10 is a generous floor). Raises `ExcelFormatError` if no
    recognizable container column is present.
    """
    wb = load_workbook(str(path), data_only=True)
    try:
        ws = wb.active
        col = _find_container_column(ws)
        if col is None:
            raise ExcelFormatError(
                f"Couldn't find a column named 'Container #' in {path}. "
                "Expected headers include: Container #, Container Number, Cntr No."
            )
        out: list[str] = []
        for row in range(2, ws.max_row + 1):
            value = ws.cell(row=row, column=col).value
            if value:
                container = str(value).strip().upper()
                if len(container) >= 10:
                    out.append(container)
        return out
    finally:
        wb.close()


def write_tracking_report(path: Path, db: dict[str, dict[str, Any]]) -> int:
    """Write tracking data back into the linked workbook. Returns the row count updated.

    Raises `ExcelFormatError` if no container column exists. Unknown tracking
    columns are created. Containers in `db` that don't appear in the sheet are
    appended.
    """
    wb = load_workbook(str(path))
    try:
        ws = wb.active
        col = _find_container_column(ws)
        if col is None:
            raise ExcelFormatError(
                f"Couldn't find a column named 'Container #' in {path}. "
                "Expected headers include: Container #, Container Number, Cntr No."
            )
        field_cols = _find_or_create_tracking_columns(ws)

        status_fill_by_keyword = {
            "sailing": "D6EAF8", "en_route": "D6EAF8",
            "arrived": "D5F5E3", "discharged": "ABEBC6",
            "delivered": "82E0AA", "booked": "FCF3CF",
            "new": "FCF3CF", "untracked": "F2F3F4",
        }
        timestamp = _now_est_str()
        count = 0

        existing_containers: set[str] = set()
        for row in range(2, ws.max_row + 1):
            container_value = ws.cell(row=row, column=col).value
            if not container_value:
                continue
            container = str(container_value).strip().upper()
            existing_containers.add(container)
            if container in db:
                _write_row(ws, row, field_cols, db[container], timestamp, status_fill_by_keyword)
                count += 1

        # Append containers tracked in DB but not yet in the sheet.
        for container, record in db.items():
            if container in existing_containers or not record.get("status"):
                continue
            new_row = ws.max_row + 1
            ws.cell(row=new_row, column=col, value=container)
            _write_row(ws, new_row, field_cols, record, timestamp, status_fill_by_keyword)
            count += 1

        # Auto-fit widths (capped).
        for field_col in field_cols.values():
            max_len = max(
                (len(str(ws.cell(row=r, column=field_col).value or "")) for r in range(1, ws.max_row + 1)),
                default=10,
            )
            ws.column_dimensions[get_column_letter(field_col)].width = min(max_len + 4, 30)

        wb.save(str(path))
        return count
    finally:
        wb.close()


def _write_row(
    ws: Any,
    row: int,
    field_cols: dict[str, int],
    record: dict[str, Any],
    timestamp: str,
    status_fill_by_keyword: dict[str, str],
) -> None:
    for field_key, field_col in field_cols.items():
        value: Any = record.get(field_key, "")
        if field_key == "transit_pct" and value != "":
            value = f"{value}%"
        if field_key == "last_refreshed":
            value = timestamp
        ws.cell(row=row, column=field_col, value=value)

    status_col = field_cols.get("status")
    if status_col:
        cell = ws.cell(row=row, column=status_col)
        status_lower = str(cell.value or "").lower().replace(" ", "_")
        for keyword, color in status_fill_by_keyword.items():
            if keyword in status_lower:
                cell.fill = PatternFill(start_color=color, fill_type="solid")
                break

    delay_col = field_cols.get("delay_days")
    if delay_col:
        cell = ws.cell(row=row, column=delay_col)
        text = str(cell.value or "")
        if text.startswith("+"):
            cell.fill = PatternFill(start_color="FADBD8", fill_type="solid")
            cell.font = Font(color="C0392B")
        elif "early" in text:
            cell.fill = PatternFill(start_color="D5F5E3", fill_type="solid")
            cell.font = Font(color="27AE60")
        elif "On time" in text:
            cell.font = Font(color="27AE60")


def create_template(path: Path) -> None:
    """Write a blank linked-spreadsheet template with expected headers and two sample rows."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Container Tracking"
    headers = [
        "Container #", "PO / Reference", "Notes", "Carrier", "Status", "ETA",
        "Original ETA", "Delay", "Port of Loading", "Port of Discharge", "Vessel",
        "Transit %", "Last Refreshed",
    ]
    for col, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=header)

    samples = [
        ("MSKU1234567", "PO-2026-001", "Sample — replace"),
        ("MSCU7654321", "PO-2026-002", ""),
    ]
    for row_idx, (container, reference, note) in enumerate(samples, start=2):
        ws.cell(row=row_idx, column=1, value=container)
        ws.cell(row=row_idx, column=2, value=reference)
        ws.cell(row=row_idx, column=3, value=note)

    last_col_letter = get_column_letter(len(headers))
    table = Table(displayName="ContainerTracking", ref=f"A1:{last_col_letter}3")
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    ws.add_table(table)

    widths = [18, 18, 25, 16, 14, 14, 14, 14, 20, 20, 20, 12, 22]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    wb.save(str(path))
    wb.close()
```

- [ ] **Step 4: Run tests and confirm all pass**

Run: `pytest tests/test_excel.py -v`
Expected: all 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_excel.py container_tracker/core/excel.py
git commit -m "core: extract Excel read/write/template with ExcelFormatError"
```

---

## Task 8: `core/updates.py` — UpdateInfo and check_for_update

**Files:**
- Create: `tests/test_updates.py`
- Create: `container_tracker/core/updates.py`

Reference code in monolith:
- `check_for_update_async` at `container_tracker_gui.py:241–261`
- `GITHUB_REPO` constant at `container_tracker_gui.py:47`

Note the new module's `check_for_update` is **synchronous** — the UI layer wraps it in a `QRunnable`. The monolith bundled threading into the function; we're separating concerns.

- [ ] **Step 1: Write the failing `tests/test_updates.py`**

```python
import responses

from container_tracker.core.updates import UpdateInfo, check_for_update


GITHUB_RELEASES_URL = "https://api.github.com/repos/m-mcohen/container-tracker/releases/latest"


class TestCheckForUpdate:
    @responses.activate
    def test_newer_release_returns_update_info(self) -> None:
        responses.add(
            responses.GET,
            GITHUB_RELEASES_URL,
            json={"tag_name": "v1.2.0", "html_url": "https://github.com/m-mcohen/container-tracker/releases/v1.2.0"},
            status=200,
        )
        result = check_for_update("1.1.0")
        assert result == UpdateInfo(
            version="1.2.0",
            html_url="https://github.com/m-mcohen/container-tracker/releases/v1.2.0",
        )

    @responses.activate
    def test_same_version_returns_none(self) -> None:
        responses.add(
            responses.GET,
            GITHUB_RELEASES_URL,
            json={"tag_name": "v1.1.0", "html_url": "https://..."},
            status=200,
        )
        assert check_for_update("1.1.0") is None

    @responses.activate
    def test_older_release_returns_none(self) -> None:
        responses.add(
            responses.GET,
            GITHUB_RELEASES_URL,
            json={"tag_name": "v1.0.0", "html_url": "https://..."},
            status=200,
        )
        assert check_for_update("1.1.0") is None

    @responses.activate
    def test_handles_tag_without_v_prefix(self) -> None:
        responses.add(
            responses.GET,
            GITHUB_RELEASES_URL,
            json={"tag_name": "1.2.0", "html_url": "https://..."},
            status=200,
        )
        assert check_for_update("1.1.0") is not None

    @responses.activate
    def test_404_returns_none(self) -> None:
        responses.add(responses.GET, GITHUB_RELEASES_URL, status=404)
        assert check_for_update("1.1.0") is None

    @responses.activate
    def test_403_rate_limit_returns_none(self) -> None:
        responses.add(responses.GET, GITHUB_RELEASES_URL, json={"message": "rate limit"}, status=403)
        assert check_for_update("1.1.0") is None

    @responses.activate
    def test_malformed_json_returns_none(self) -> None:
        responses.add(responses.GET, GITHUB_RELEASES_URL, body="not json", status=200)
        assert check_for_update("1.1.0") is None

    @responses.activate
    def test_missing_tag_returns_none(self) -> None:
        responses.add(responses.GET, GITHUB_RELEASES_URL, json={"html_url": "https://..."}, status=200)
        assert check_for_update("1.1.0") is None

    def test_offline_returns_none(self) -> None:
        # No responses.activate → requests will raise ConnectionError on any real call.
        # Check that the function swallows it.
        assert check_for_update("1.1.0") is None
```

- [ ] **Step 2: Run tests and confirm they fail**

Run: `pytest tests/test_updates.py -v`
Expected: `ModuleNotFoundError: No module named 'container_tracker.core.updates'`

- [ ] **Step 3: Implement `container_tracker/core/updates.py`**

```python
"""GitHub Releases update check.

Synchronous by design. The UI layer wraps this in a QRunnable for background
execution; the threading concern is kept out of the core module.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from packaging.version import InvalidVersion, parse


logger = logging.getLogger(__name__)

GITHUB_REPO = "m-mcohen/container-tracker"
_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    html_url: str


def check_for_update(current_version: str, timeout: float = 5.0) -> UpdateInfo | None:
    """Return UpdateInfo if GitHub has a newer release, else None.

    All failure modes — network error, HTTP non-200, malformed JSON, missing
    `tag_name`, unparseable version — return None and log a single info line.
    """
    try:
        response = requests.get(_RELEASES_URL, timeout=timeout)
    except requests.RequestException as exc:
        logger.info("update check: request failed: %s", exc)
        return None

    if response.status_code != 200:
        logger.info("update check: HTTP %s", response.status_code)
        return None

    try:
        data = response.json()
    except ValueError as exc:
        logger.info("update check: malformed JSON: %s", exc)
        return None

    tag = str(data.get("tag_name", "")).lstrip("v").strip()
    html_url = str(data.get("html_url", ""))
    if not tag:
        logger.info("update check: release response missing tag_name")
        return None

    try:
        if parse(tag) > parse(current_version):
            return UpdateInfo(version=tag, html_url=html_url)
    except InvalidVersion as exc:
        logger.info("update check: unparseable version %s: %s", tag, exc)
        return None
    return None
```

- [ ] **Step 4: Run tests and confirm all pass**

Run: `pytest tests/test_updates.py -v`
Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_updates.py container_tracker/core/updates.py
git commit -m "core: extract GitHub update check with UpdateInfo dataclass"
```

---

## Task 9: Run full test suite + mypy --strict + delete obsolete CLI

**Files:**
- Delete: `container_tracker.py`
- Modify: (none in `container_tracker/core/` unless mypy reveals issues)

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: all ~46 tests pass (12 status + 23 api + 14 persistence + 11 excel + 9 updates — small discrepancies possible depending on how I counted, the point is: everything green).

- [ ] **Step 2: Run mypy --strict on core/**

Run: `mypy`
Expected: `Success: no issues found in 5 source files`.

If mypy flags issues, fix them in-place (most likely: add explicit `-> None`, narrow `dict[str, Any]` where structure is known, add `# type: ignore[no-any-return]` only if the alternative is unsafe). Commit each fix with a short message before continuing.

- [ ] **Step 3: Confirm `container_tracker.py` has no importers**

Run: `grep -rn "^from container_tracker import\|^import container_tracker\b" --include="*.py" .`
Expected: no results (the new package `container_tracker/` is a directory, not the same as the standalone `container_tracker.py`). Also confirm the GUI monolith does not import from it.

Run: `grep -rn "container_tracker\.py\|from container_tracker[^_]" container_tracker_gui.py`
Expected: no references.

- [ ] **Step 4: Delete the obsolete CLI**

```bash
git rm container_tracker.py
```

- [ ] **Step 5: Re-run tests to confirm nothing broke**

Run: `pytest -v`
Expected: same count, all pass.

- [ ] **Step 6: Commit the deletion**

```bash
git commit -m "chore: delete obsolete container_tracker.py CLI (superseded by core/ package)"
```

---

## CHECKPOINT A — STOP

**What's now true:**
- `container_tracker/core/{api,excel,persistence,status,updates}.py` exist, all covered by unit/integration tests.
- `pytest` is green across ~46 tests.
- `mypy --strict` is clean on `core/`.
- Obsolete `container_tracker.py` is deleted.
- The PySide6 UI has not been touched; `container_tracker_gui.py` still works exactly as it did in v1.0.0.

**Review before proceeding to Checkpoint B:**
- Verify test count and `mypy` output manually.
- Skim `container_tracker/core/` for any leftover TODOs or Any types where a concrete type was obvious.
- Confirm commits are clean (one per task ideally).

---

## Task 10: `ui/widgets.py` — QtLogHandler only

**Files:**
- Create: `container_tracker/ui/widgets.py`

No tests for this — the Qt signal wiring is simple and is validated via the smoke test in Task 12 (we'll see the log line appear in the file, which confirms the handler is attached).

- [ ] **Step 1: Write `container_tracker/ui/widgets.py`**

```python
"""Reusable UI widgets and utilities. At the end of Phase 1, only QtLogHandler lives here.

Later phases add: StatCard, UpdateBanner, ActivityLog, LinkedSpreadsheetCard.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal


class QtLogHandler(QObject, logging.Handler):
    """A logging handler that emits each formatted record as a Qt signal.

    Connect the `log_emitted` signal to a slot on the UI thread (e.g. the
    activity-log widget's append method) using the default QueuedConnection.
    Worker threads call `logger.info(...)`, the record flows through this
    handler's `emit()`, and the signal delivers the text on the UI thread.
    """

    log_emitted = Signal(str)

    def __init__(self) -> None:
        QObject.__init__(self)
        logging.Handler.__init__(self)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            self.handleError(record)
            return
        self.log_emitted.emit(message)
```

- [ ] **Step 2: Confirm the module imports cleanly**

Run: `python -c "from container_tracker.ui.widgets import QtLogHandler; print('ok')"`
Expected: `ok` printed, no ImportError.

- [ ] **Step 3: Commit**

```bash
git add container_tracker/ui/widgets.py
git commit -m "ui: add QtLogHandler bridging stdlib logging to Qt signals"
```

---

## Task 11: `__main__.py` bootstrap — logging + QApplication + config load, no window yet

**Files:**
- Create: `container_tracker/__main__.py`

Reference: spec §3.4 (Logging), §6 (First-launch flow, step 1).

- [ ] **Step 1: Write `container_tracker/__main__.py`**

```python
"""Container Tracker entry point.

Run with: ``python -m container_tracker``. PyInstaller's `.spec` points at
this same module. Ownership of QApplication lifetime lives here.

At end of Phase 1 this does NOT construct a window — it bootstraps the
application, logs a startup line, and exits. Windows come in Checkpoint C.
"""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from container_tracker.__version__ import __version__
from container_tracker.core.persistence import (
    get_api_token,
    is_first_run,
    load_config,
    log_path,
)
from container_tracker.ui.widgets import QtLogHandler


_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def _configure_logging() -> QtLogHandler:
    """Attach FileHandler + QtLogHandler to the root logger. Returns the QtLogHandler.

    Third-party library noise (requests, urllib3) is suppressed at WARNING.
    This function is idempotent-safe to call once; do not call twice.
    """
    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = logging.FileHandler(log_path(), encoding="utf-8")
    file_handler.setFormatter(formatter)

    qt_handler = QtLogHandler()
    qt_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(qt_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    return qt_handler


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
    logger.info("first-run=%s, api-token-present=%s", is_first_run(config), bool(get_api_token()))

    # Phase 1 stops here — no window yet. Checkpoint C attaches MainWindow.
    logger.info("Container Tracker bootstrap complete; exiting (Phase 1 Checkpoint B)")
    _ = qt_handler  # keep reference; in Checkpoint C the main window will connect to it.
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify the module imports and the bootstrap path runs**

Run: `python -m container_tracker`
Expected:
- Process exits cleanly (exit code 0).
- No window appears.
- `%APPDATA%\ContainerTracker\tracker.log` (on Windows) contains four new lines matching the format:
  ```
  2026-04-23 XX:XX:XX,XXX [INFO] Container Tracker v1.1.0 starting
  2026-04-23 XX:XX:XX,XXX [INFO] config loaded: company=..., excel_path=..., dark_mode=...
  2026-04-23 XX:XX:XX,XXX [INFO] first-run=..., api-token-present=...
  2026-04-23 XX:XX:XX,XXX [INFO] Container Tracker bootstrap complete; exiting (Phase 1 Checkpoint B)
  ```

- [ ] **Step 3: Commit**

```bash
git add container_tracker/__main__.py
git commit -m "main: bootstrap QApplication, logging, and config load (no window)"
```

---

## Task 12: Smoke test — Checkpoint B verification

**Files:** none modified.

This is a manual verification step. No code changes.

- [ ] **Step 1: Run the module fresh**

Run: `python -m container_tracker`
Verify: process exits in under 1 second, no window, no error output.

- [ ] **Step 2: Inspect the log file**

Open `%APPDATA%\ContainerTracker\tracker.log` in a text editor.
Verify: last four lines match the expected format from Task 11 Step 2. Timestamps include milliseconds (comma separator).

- [ ] **Step 3: Confirm config was not corrupted**

Open `%APPDATA%\ContainerTracker\config.json` if it exists.
Verify: contents are the same as before bootstrap (load-only; no save happened). If the file didn't exist, it still shouldn't — `load_config` does not create it.

- [ ] **Step 4: Verify bootstrap against a machine with no config.json yet**

This is the clean-first-run path. Temporarily rename or delete the config file:

```bash
# Windows bash (Git Bash / WSL). In PowerShell use: Rename-Item ...
mv "$APPDATA/ContainerTracker/config.json" "$APPDATA/ContainerTracker/config.json.bak" 2>/dev/null || true
```

Run: `python -m container_tracker`
Expected:
- Process exits cleanly (exit code 0).
- No new `config.json` file is created on disk (load is read-only).
- `tracker.log` shows the four startup lines.
- The `first-run=...` log line reads `first-run=True` (because company_name is missing AND no keyring token is present on this clean state).
- The `config loaded: company=...` line shows the defaults (`company=''`, `excel_path=''`, `dark_mode=False`).

Restore the backup if you made one:

```bash
mv "$APPDATA/ContainerTracker/config.json.bak" "$APPDATA/ContainerTracker/config.json" 2>/dev/null || true
```

- [ ] **Step 5: Run pytest again to confirm nothing regressed**

Run: `pytest -v`
Expected: all tests still pass.

---

## CHECKPOINT B — STOP

**What's now true:**
- `python -m container_tracker` runs, loads config, logs startup, exits clean.
- Log file shows v1.0.0-matching format.
- `QtLogHandler` is attached (its signal has no receiver yet; that's OK — Qt signals are fine with zero connections).
- No window appears yet.

**Review before proceeding to Checkpoint C:**
- Confirm the log format matches v1.0.0 (`2026-04-23 XX:XX:XX,XXX [INFO] ...`).
- Confirm running twice doesn't duplicate or corrupt anything.
- Confirm tests still green.

---

## Task 13: `ui/main_window.py` — blank MainWindow

**Files:**
- Create: `container_tracker/ui/main_window.py`

- [ ] **Step 1: Write `container_tracker/ui/main_window.py`**

```python
"""Main application window.

At end of Phase 1 this is an empty QMainWindow with a title and an initial
size. Phase 3 adds header, stat cards, table, activity log, and footer.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QSize
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow

from container_tracker.__version__ import __version__


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Container Tracker v{__version__}")
        self.resize(QSize(1100, 720))
        logger.info("MainWindow constructed")

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        logger.info("MainWindow shown")
        super().showEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        logger.info("MainWindow closing")
        super().closeEvent(event)
```

- [ ] **Step 2: Verify the module imports cleanly**

Run: `python -c "from container_tracker.ui.main_window import MainWindow; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: add blank MainWindow (title + initial size) with lifecycle logging"
```

---

## Task 14: Wire MainWindow into `__main__.py` and run the event loop

**Files:**
- Modify: `container_tracker/__main__.py`

- [ ] **Step 1: Update `container_tracker/__main__.py`**

Replace the `main` function body with one that constructs and shows the window, then runs `app.exec()`:

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
    logger.info("first-run=%s, api-token-present=%s", is_first_run(config), bool(get_api_token()))

    # Construct and show the main window. The qt_handler signal has no
    # connected slot yet — ActivityLog wiring arrives in Phase 3.
    from container_tracker.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    return app.exec()
```

- [ ] **Step 2: Run the app and verify the window renders**

Run: `python -m container_tracker`
Expected:
- A blank window appears with title `Container Tracker v1.1.0`.
- Roughly 1100×720 px.
- Clicking the close button closes the window and the process exits cleanly (exit code 0).
- `tracker.log` now contains these additional lines (for a clean run):
  ```
  [INFO] MainWindow constructed
  [INFO] MainWindow shown
  [INFO] MainWindow closing
  ```

- [ ] **Step 3: Commit**

```bash
git add container_tracker/__main__.py
git commit -m "main: construct and show MainWindow; run app.exec()"
```

---

## Task 15: Smoke test — Checkpoint C verification

**Files:** none modified.

- [ ] **Step 1: Launch and close the app three times in a row**

Run: `python -m container_tracker` → close via × → repeat twice more.
Verify: no hangs, no exceptions in stderr, log file accumulates matching lines per run.

- [ ] **Step 2: Launch via the installed-style invocation and confirm it works too**

Run: `python container_tracker/__main__.py`
Expected: same behavior as `python -m container_tracker`.

- [ ] **Step 3: Run pytest + mypy one more time**

Run: `pytest -v`
Expected: all tests pass.

Run: `mypy`
Expected: `Success: no issues found in 5 source files`.

- [ ] **Step 4: Confirm git log is clean**

Run: `git log --oneline`
Expected: a sequence of small, focused commits — one per task ideally, with descriptive messages.

---

## CHECKPOINT C — PHASE 1 COMPLETE

**What's now true:**
- `python -m container_tracker` launches a blank window with the correct title and size.
- Window closes cleanly on ×.
- Logging flows through FileHandler (and through the yet-unconnected QtLogHandler signal) with v1.0.0-matching format.
- `core/` package has five modules, all unit-tested, `mypy --strict` clean.
- `container_tracker.py` (obsolete CLI) is deleted.
- `container_tracker_gui.py` is untouched — v1.0.0 still builds from it if needed (Phases 2–7 gradually replace it; it's deleted at end of Phase 5).

**Ready for Phase 2** (theme + QSS generator) once the user reviews and signs off.

---

## Self-Review

**1. Spec coverage check** (walking the spec §-by-§):

- §3.1 Package layout → Tasks 1, 2–8 (core/*), 10, 13.
- §3.2 Threading → not in Phase 1 (first real background op is in Phase 5).
- §3.3 State ownership → Task 11 (MainWindow owns state; child widgets get constructor args in later phases).
- §3.4 Logging → Task 11 (`_configure_logging`), Task 10 (QtLogHandler).
- §3.5 Testing strategy → Tasks 2–8 cover unit + integration; mypy in Task 9.
- §4.1 api.py → Tasks 3, 4, 5.
- §4.2 persistence.py → Task 6.
- §4.3 excel.py → Task 7. Robustness posture covered via `ExcelFormatError` tests.
- §4.4 updates.py → Task 8.
- §4.5 status.py → Task 2.
- §5.x UI → not in Phase 1 beyond QtLogHandler (Task 10) and blank MainWindow (Task 13).
- §6 First-launch flow → partial: logging + config load in Task 11; Welcome dialog is Phase 4.
- §7 Packaging → Phase 7, not here.
- §9 Gotchas: PySide6 `--collect-all`, AppId, icon → Phase 7.
- §10 Success criteria → items 1, 2, 3, 8, 11 are Phase 4–6 scope; Phase 1 doesn't directly satisfy any user-facing criteria (that's by design — it's scaffolding). Log file at expected path IS validated by Task 12 as a proxy.

All Phase 1 items that the spec assigns to Phase 1 are covered. Items marked "Phase N≥2" are out of scope here.

**2. Placeholder scan:** searched for "TBD", "TODO", "implement later", "similar to Task" — none found.

**3. Type / signature consistency:**
- `StatusBucket` defined in status.py (Task 2), not referenced in other core modules — that's fine; only bucket_counts needs it internally.
- `compute_delay_days` signature matches between Task 2 (definition) and Task 4 (import in api.py).
- `ShipsGoAuthError` raised in all four client methods that do HTTP (Task 5).
- `ExcelFormatError` raised in both `read_container_list` and `write_tracking_report` (Task 7).
- `UpdateInfo` dataclass matches between Task 8 (definition) and spec §4.4.
- `QtLogHandler.log_emitted` signal signature (str) matches intended receiver (Phase 3 ActivityLog.append(str)).
- `MainWindow` constructor takes no args in Task 13; Task 14 calls it as `MainWindow()`. Match.

Plan ready for execution.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-23-pyside6-phase1-scaffold-and-backend.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. Natural fit for the three hard checkpoints in this plan: the orchestrator pauses for review at each STOP marker.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batched with checkpoints for review.

User has requested the plan be pasted back for review before any execution begins. Awaiting approval.
