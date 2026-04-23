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


# Column name -> tracking-record field key. These are the columns written
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
        assert ws is not None  # openpyxl always returns a sheet for a loaded workbook
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
        assert ws is not None  # openpyxl always returns a sheet for a loaded workbook
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
    assert ws is not None  # new Workbook always has an active sheet
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
