# Legacy Excel I/O — reconnaissance for Step 6.5

## Context

Manual verification of Step 6 surfaced a regression: the new pywebview refresh
writes to `tracking_data.json` but does NOT write to the user's Excel file.
The user actively uses the Excel file as their delivered artifact. The legacy
tkinter app handled Excel I/O end-to-end; the new shell silently dropped it.
This document captures what the legacy code actually does — grounded against
the source, not the README or memory — to scope the Step 6.5 fix.

## Files inspected (read in full)

- `container_tracker_gui.py` — legacy CustomTkinter GUI (the shipped product)
- `container_tracker.py` — legacy CLI variant
- `container_tracker/core/excel.py` — extracted Excel helpers (Step 1)
- `container_tracker/core/constants.py` — `CONTAINER_COL_KEYWORDS`, `CARRIER_NAMES`

---

## 1. Every function that touches Excel

| File | Line | Signature | What it does | Called from | Location |
|---|---|---|---|---|---|
| `container_tracker_gui.py` | 644 | `browse_excel(self)` | File-picker dialog → saves chosen path to `config["excel_path"]` | GUI | Inline (GUI) |
| `container_tracker_gui.py` | 651 | `create_template(self)` | Save-as dialog → `create_template_excel(p)` → save path → open in Excel | GUI | Inline (GUI) — delegates to `core/excel.py` |
| `container_tracker_gui.py` | 662 | `open_excel(self)` | `os.startfile(path)` — opens the linked workbook in Excel (no I/O) | GUI | Inline (GUI) |
| `container_tracker_gui.py` | 763 | `_do_refresh(self)` | Orchestrates: read CNs from Excel → fetch from API → write back to Excel | GUI (background thread) | Inline (GUI) |
| `container_tracker.py` | 384 | `export_to_excel(db, output_path)` | Standalone export: builds a NEW workbook from the DB; does not touch a user file | CLI | Inline (CLI) |
| `container_tracker/core/excel.py` | 25 | `find_container_column(ws)` | Scans header row 1 for a `CONTAINER_COL_KEYWORDS` exact match, then substring fallback | GUI (via update/read) | Extracted |
| `container_tracker/core/excel.py` | 37 | `find_or_create_tracking_columns(ws)` | Locates each `TRACKING_COL_MAP` header in row 1 or appends it with header styling | GUI (via update) | Extracted |
| `container_tracker/core/excel.py` | 62 | `read_containers_from_excel(path)` | Opens workbook, finds container column, returns uppercased list of CNs from rows ≥ 2 | GUI (`_do_refresh`) | Extracted |
| `container_tracker/core/excel.py` | 80 | `update_excel_with_tracking(path, data)` | Opens workbook, finds/creates tracking columns, updates existing rows, appends new CNs, applies status + delay fills, autosizes, saves | GUI (`_do_refresh`) | Extracted |
| `container_tracker/core/excel.py` | 157 | `create_template_excel(path)` | Builds new workbook with sheet `Container Tracking`, 13 columns, 2 sample rows, Excel Table, frozen panes, fixed widths | GUI (`create_template`) | Extracted |

**Notes**

- The CLI (`container_tracker.py`) does NOT use `core/excel.py`. Its
  `export_to_excel` is a self-contained writer — different colors, different
  filename, no read-back. CLI and GUI Excel paths are siblings, not shared.
- All user-linked-workbook I/O goes through `core/excel.py`. The GUI itself
  contains no openpyxl calls except via the helpers above.

---

## 2. Excel file structure

### Sheet name

- Template creates and uses sheet `"Container Tracking"`
  (`core/excel.py:159`).
- Read/write helpers (`read_containers_from_excel`, `update_excel_with_tracking`)
  use `wb.active` — whatever sheet is active in the user's file. They do
  **not** look up by name, so a renamed sheet still works as long as it's the
  active one.

### Exact column headers

`CONTAINER_COL_KEYWORDS` (`core/constants.py:22-23`), used to find the
container column by exact-match (case-insensitive), then by substring
fallback for `"container"` / `"cntr"`:

```python
CONTAINER_COL_KEYWORDS = ["container", "cntr", "container #", "container number",
                          "container_number", "container no", "cntr #", "cntr no"]
```

`TRACKING_COL_MAP` (`core/excel.py:11-22`) — header label → DB field key:

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

Template's full column list (`create_template_excel`, `core/excel.py:161`):

```python
["Container #", "PO / Reference", "Notes", "Carrier", "Status", "ETA",
 "Original ETA", "Delay", "Port of Loading", "Port of Discharge",
 "Vessel", "Transit %", "Last Refreshed"]
```

### Written vs. user-owned

- **App-written:** the 10 columns in `TRACKING_COL_MAP`.
- **User-owned (never overwritten):** `Container #`, `PO / Reference`, `Notes`,
  plus any other columns the user has added between or after the tracked
  ones. The app only addresses cells by column index resolved from the header
  row, so unrelated columns are untouched.

### Missing-state behavior

- **Sheet missing / unusual:** falls back to `wb.active`. No explicit
  validation.
- **Container column missing:** `find_container_column` returns `None`;
  `update_excel_with_tracking` raises `ValueError("No Container column found.")`
  (`core/excel.py:86`); `read_containers_from_excel` returns an empty list.
- **Tracking columns missing:** `find_or_create_tracking_columns` appends
  them after `ws.max_column`, applying the dark-blue header bar and writing
  the header label.
- **Empty file (only headers):** read returns `[]`; update will append rows
  for every CN in the DB starting at `ws.max_row + 1`.

### Formatting applied

Header bar (template + auto-created tracking columns):

- Font: Calibri bold 11pt, white (`FFFFFF`)
- Fill: solid `1F4E79` (dark blue)
- Alignment: center / center

Status column conditional fills (`core/excel.py:88-104`); match is
case-insensitive on the lowercase status with spaces → underscores:

| Match | Fill |
|---|---|
| `sailing`, `en_route` | `D6EAF8` (light blue) |
| `arrived` | `D5F5E3` (light green) |
| `discharged` | `ABEBC6` (medium green) |
| `delivered`, `gate_out` | `82E0AA` (dark green) |
| `booked`, `new` | `FCF3CF` (light yellow) |
| `untracked` | `F2F3F4` (light gray) |

Delay column (`core/excel.py:116-126`):

- Value starts with `+` → fill `FADBD8`, font `C0392B` (red on light red)
- Value contains `early` → fill `D5F5E3`, font `27AE60`
- Value contains `On time` → font `27AE60` only

Other:

- `Transit %` values get a literal `%` appended at write time.
- `Last Refreshed` is overwritten with `now_est()` for every updated row.
- Column widths auto-sized: `min(max_content_len + 4, 30)` for tracking
  columns (`core/excel.py:148-151`).
- Template only: Excel Table named `ContainerTracking` with style
  `TableStyleMedium2` over `A1:M3`; freeze panes at `A2`; hardcoded widths
  `[18, 18, 25, 16, 14, 14, 14, 14, 20, 20, 20, 12, 22]`. The update path does
  not freeze panes or extend the Table — appended rows fall outside the
  Table range.

---

## 3. The refresh flow — exact sequence

**Single button.** `container_tracker_gui.py:519`:

```python
self.refresh_btn = self._btn(af, "  Refresh All ETAs & Update Excel  ",
                             self.refresh_data, role="btn_green")
```

There is no separate "Write to Excel" button anywhere in the GUI. The
button label embeds both actions.

Click handler `refresh_data` (line 758) disables the button and spawns a
daemon thread running `_do_refresh` (line 763). The full sequence:

1. **Fetch shipment list** — `client.list_shipments()` (line 768). If zero,
   show messagebox `"No Shipments"` / `"No shipments on ShipsGo.\n\nUse 'Add &
   Track' to register containers (1 credit each)."` and return.

2. **Build map** by `id` and uppercased `container_number` (lines 774-780).

3. **Read CNs from Excel if linked** (lines 781-793):

   ```python
   ep = self.config.get("excel_path", "")
   if ep and Path(ep).exists():
       try:
           ec = read_containers_from_excel(ep)
           self.log(f"Read {len(ec)} containers from Excel")
           ...
           dismissed = self.config.get("dismissed", [])
           for c in ec:
               if c not in self.db and c not in dismissed:
                   self.db[c] = {"container_number": c, "last_refreshed": None}
       except PermissionError:
           self.log("ERROR: Excel open - close it first")
           messagebox.showerror("File In Use", "Close Excel first, then Refresh.")
           return
   ```

   New CNs from Excel are silently merged into `self.db` with no shipment_id.
   **No `create_shipment` call here. No prompt at this stage.** A
   `PermissionError` aborts the entire refresh.

4. **Bootstrap from API** if `self.db` is empty (lines 794-801) — adds every
   API shipment that isn't dismissed.

5. **Per-CN detail fetch and field extraction** (lines 802-819):
   - For each DB record, look up the shipment by id or container number.
   - If matched: `client.get_shipment(fid)` → `extract_fields(sh)` → merge into
     record, set `last_refreshed = now_est()`, log line.
   - If not matched: set `last_refreshed = now_est()`, log
     `"  {cn}: not on ShipsGo yet"`, append to `unmatched_list`.

6. **Save tracking_data.json + reload table** (line 820):
   `save_json(TRACKING_DB_FILE, self.db); self.root.after(0, self.load_table_data)`.

7. **Write back to Excel** (lines 821-829) — automatic, no extra click:

   ```python
   eu = 0
   if ep and Path(ep).exists():
       try:
           self.set_status("Updating Excel...")
           eu = update_excel_with_tracking(ep, self.db)
           self.log(f"Updated {eu} rows in Excel")
       except PermissionError:
           self.log("Excel open - close it first")
           messagebox.showwarning("File In Use", "Close Excel, then Refresh.")
       except Exception as e:
           self.log(f"Excel error: {e}")
   ```

   Note this `PermissionError` is a warning, not an error, and execution
   continues to the summary log line.

8. **Final log + status** (lines 830-831):
   `--- DONE: {matched} matched, {unmatched} unmatched, {delayed_sailing} actively delayed, {eu} Excel rows updated ---`
   then `Refreshed {matched} containers — {timestamp} EST`.

9. **Post-refresh prompt for unmatched** (lines 833-846, prompt at 848-866):
   If `unmatched_list` is non-empty, schedules `_prompt_register_unmatched(ul)`
   on the main thread. Dialog text:

   > **{len(containers)} New Container(s) Found**
   >
   > The following containers are in your spreadsheet but not yet
   > tracked on ShipsGo:
   >
   >   • {first 15 CNs}
   >
   > Would you like to register them now?
   >
   > Cost: 1 credit per container (~$2 USD each)
   > Credits are one-time per shipment — all future
   > refreshes are free and unlimited.
   >
   > Total: {n} credit(s) will be used.

   - YES → `_register_unmatched` (line 868) calls `client.create_shipment` per
     CN, handles `NOT_ENOUGH_CREDITS`, then re-runs `_do_refresh()` (line 918)
     to pick up freshly-registered shipments.
   - NO → CNs stay in the local DB unmatched; same prompt fires next refresh.

### README contradiction — resolved

The README (`CLAUDE.md` excerpt) says: *"Registration costs ShipsGo credits;
refreshes are free. The GUI confirms before any `create_shipment()` call."*
That's accurate but easy to misread. To be precise:

- **Refresh is one button, performing both API fetch AND Excel write.**
- **Refresh never calls `create_shipment` directly.**
- `create_shipment` is only invoked from (a) the **Add & Track** flow
  (line 723, with up-front confirmation) and (b) the **post-refresh
  unmatched prompt** (line 880). The user is always confirmed before either.
- A CN added to the workbook by the user appears in the local DB after the
  next refresh, but is NOT registered with ShipsGo until the user accepts
  the post-refresh prompt.

---

## 4. Add and remove flows

### Add (`add_container`, lines 700-756)

1. User types CN, picks carrier from `CARRIER_NAMES` dropdown.
2. Confirmation dialog (lines 708-714):

   > **Register {cn} with ShipsGo?**
   >
   > This will use 1 tracking credit (~$2 USD).
   > Credits are one-time per shipment — all future
   > refreshes are free and unlimited.
   >
   > If the container is already tracked, no credit
   > will be charged.

3. On YES, background thread calls `client.create_shipment(container_number=cn, carrier=...)` (line 723).
4. Result handling:
   - `NOT_ENOUGH_CREDITS` → error messagebox, no DB write.
   - `already_exists` (HTTP 409) → still added to local DB (line 737),
     `tracking_data.json` saved.
   - Otherwise → added to DB with `shipment_id` (lines 742-744), saved.
5. Success messagebox confirms registration and notes:
   *"The container will be added to your Excel file on the next refresh."*
   (line 749).
6. Add does **not** write to Excel directly. The new CN appears in the
   workbook on the very next `_do_refresh` call — which the function
   automatically triggers at line 750.

### Remove (`remove_container`, lines 667-698)

Two branches based on the selected row's status:

- **Completed** (`DISCHARGED`, `DELIVERED`, `GATE_OUT`, `ARRIVED`):
  confirmation dialog explicitly states *"The row will remain in your Excel
  file."* On YES, CN is added to `config["dismissed"]` AND deleted from
  `self.db`. Both saved.
- **Active** (any other status): confirmation warns the row will reappear on
  the next refresh because the API still returns it. Removed only from
  `self.db`. Not added to dismissed list.

**Excel rows are never deleted by the app** in either branch.
`update_excel_with_tracking` only updates existing rows or appends new ones.

---

## 5. Template creation

`create_template_excel(path)` (`core/excel.py:157-185`), invoked by GUI
button **`Create Template`** at `container_tracker_gui.py:497`, handler at
line 651.

Generated template:

- Sheet name: `"Container Tracking"`
- 13 columns (see Section 2)
- 2 sample rows:
  - `MSKU1234567`, `PO-2024-001`, `Sample - replace`, …
  - `MSCU7654321`, `PO-2024-002`, `(blank notes)`, …
- Excel Table named `ContainerTracking`, range `A1:M3`, style `TableStyleMedium2`
- Header row formatted with the standard dark-blue bar
- Freeze panes at `A2`
- Hardcoded column widths `[18, 18, 25, 16, 14, 14, 14, 14, 20, 20, 20, 12, 22]`

Save location is interactive only:

```python
p = filedialog.asksaveasfilename(
    title="Save template", defaultextension=".xlsx",
    initialfile="Container_Tracking.xlsx",
    filetypes=[("Excel", "*.xlsx")])
```

After save, the path is written to `config["excel_path"]`, a confirmation
dialog is shown, and `os.startfile(p)` opens the file in Excel.

There is no "default location" or auto-creation — every template is
user-pathed.

---

## 6. File-link / file-path persistence

- The path lives at `config["excel_path"]` (string) inside
  `%APPDATA%\ContainerTracker\config.json`. Nothing else.
- No hardcoded path. No auto-discovery. If `excel_path` is missing or empty,
  refresh skips both the read-from-Excel block and the write-back block —
  it will still hit the API and update `tracking_data.json`, just without
  any workbook side effects.
- Three buttons sit on the Excel card (lines 488-499):
  - `"Browse..."` → `browse_excel` (line 644) — file-picker, saves path.
  - `"Create Template"` → `create_template` (line 651).
  - `"Open in Excel"` → `open_excel` (line 662) — `os.startfile`.
- Display: a green label shows the current `excel_path` or
  `"No file linked"`.

---

## 7. Error handling — file locked / open in Excel

`openpyxl` raises `PermissionError` when the workbook is locked by an open
Excel process. The GUI handles it in two places:

**During read** (`_do_refresh`, lines 790-792):

```python
except PermissionError:
    self.log("ERROR: Excel open - close it first")
    messagebox.showerror("File In Use", "Close Excel first, then Refresh.")
    return
```

- Title: `"File In Use"`
- Body: `"Close Excel first, then Refresh."`
- Severity: `showerror`
- Behavior: aborts the entire refresh — API is not called, write is not
  attempted, `tracking_data.json` is not saved.

**During write** (`_do_refresh`, lines 826-828):

```python
except PermissionError:
    self.log("Excel open - close it first")
    messagebox.showwarning("File In Use", "Close Excel, then Refresh.")
```

- Title: `"File In Use"`
- Body: `"Close Excel, then Refresh."` (note the comma — different string
  from the read-side error).
- Severity: `showwarning`
- Behavior: write is skipped, but the run continues — final `--- DONE ---`
  log line still prints, status bar still updates, post-refresh unmatched
  prompt may still fire. The DB is still saved at line 820 because that
  happens before the write attempt. **The user's tracking_data.json gets
  the new ETAs, but the workbook does not — and nothing on screen
  emphasizes that the next refresh will need to re-do the write.**

There is **no retry, no queue, no blocking, no save-to-temp**. A single
locked-file event during write loses that refresh's worth of Excel
updates. The next successful refresh writes fresh data over what would
have been written.

---

## 8. Interaction between tracking_data.json and Excel

**Source of truth: `tracking_data.json`.** The Excel workbook is a
projection of the DB plus user-owned columns.

Concretely:

- The DB is what gets re-written from API responses.
- The DB drives the Excel update: `update_excel_with_tracking(path, self.db)`
  iterates over `self.db.values()`, finds the matching row by container
  number, writes tracked fields, and appends any DB entries not present in
  the workbook (lines 130-147).

Reconciliation cases (during `_do_refresh`):

- **DB has a CN that's not in Excel:** appended as a new row at
  `ws.max_row + 1` during the write (lines 130-147 in `core/excel.py`). New
  rows do not extend the template's Excel Table.
- **Excel has a CN that's not in DB and not dismissed:** added to the DB
  with only `{container_number, last_refreshed: None}` (lines 787-789),
  then runs through the per-CN fetch loop. If it's missing on ShipsGo,
  it lands in `unmatched_list` and triggers the post-refresh prompt
  (`_prompt_register_unmatched`).
- **Excel has a dismissed CN:** ignored on read (line 788 filters
  `c not in dismissed`). The row stays in the workbook untouched, but the
  app stops tracking it.
- **DB has a CN that ShipsGo no longer returns:** the per-CN loop's
  `else` branch (line 817) sets `last_refreshed = now_est()` and counts it
  as unmatched. The row is still updated in Excel on write — every record
  in `self.db` is iterated regardless of match status (loop in
  `core/excel.py:107-128`).

The overall pattern is **forward propagation, never deletion.** The DB
and the workbook accumulate; pruning only happens via explicit user
remove (which doesn't touch Excel anyway).

---

## 9. Anything else worth knowing

- **Two parallel codepaths.** `container_tracker.py` (CLI) is a sibling, not
  a subset — its `export_to_excel` builds a fresh workbook from the CLI's
  own DB layout (which carries `voyage_data` blobs the GUI doesn't keep).
  Don't unify them in the Step 6.5 fix unless explicitly scoped.
- **Threading.** `_do_refresh` runs on a daemon thread; every UI update
  (messagebox, status, table reload) is dispatched via
  `self.root.after(0, …)`. Any new Excel-write code in the pywebview shell
  needs an equivalent main-thread bridge for popups, plus a way to signal
  completion to the JS side.
- **`extract_fields`** is the canonical API → flat-record parser
  (`container_tracker_gui.py`, also referenced in CLAUDE.md). It produces
  the field keys that `TRACKING_COL_MAP` maps onto.
- **Auto-sized column widths** are only applied to columns in
  `TRACKING_COL_MAP` (the loop at `core/excel.py:148-151` runs over
  `fm.values()`). User columns retain their existing widths.
- **Template Excel Table is fragile across refresh.** The Table is created
  with range `A1:M3`. Refresh appends rows at `ws.max_row + 1` without
  extending `tab.ref`. New CNs appear as plain rows below the Table, not
  as Table rows — so banded styling and Table filtering don't apply to them.
  This may already confuse users; flagging in case Step 6.5 wants to fix it.
- **`_migrate_data_folder` and `_migrate_keyring`** (CLAUDE.md callout)
  run unconditionally at startup and are unrelated to Excel — but a Step 6.5
  rewrite must not bypass them.
- **Status keyword normalization.** Both fill maps (status, delay) match
  on a lowercased status with `' '` → `'_'`. So API status `"En Route"`
  becomes `"en_route"` and matches the sailing fill. Anything that
  changes the source string format risks silently losing the color.
- **`Last Refreshed` is overwritten every cycle.** There's no "last
  successful Excel write" timestamp distinct from the API timestamp —
  the column reflects the API call, not the write.
- **Empty `excel_path` is not an error.** Refresh just skips both Excel
  blocks and runs API-only, completing normally with `0 Excel rows updated`.
  The current pywebview shell has effectively the same behavior — it just
  has no UI to set the path or to surface the omission.

---

## Verification

This document is read-only research. To verify it matches reality:

1. Open `container_tracker_gui.py` and step through `_do_refresh` (line 763)
   alongside the per-section code blocks above — every line number cited
   should match.
2. Open `container_tracker/core/excel.py` and confirm `TRACKING_COL_MAP`,
   header styling, status fills, and delay fills against Section 2.
3. Cross-check `CONTAINER_COL_KEYWORDS` in `container_tracker/core/constants.py:22-23`
   against Section 2's quoted block.
4. Run the legacy app once, link a workbook, hit Refresh with the file open
   in Excel, and confirm the warning message text matches Section 7
   verbatim.
