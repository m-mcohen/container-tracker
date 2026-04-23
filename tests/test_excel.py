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
