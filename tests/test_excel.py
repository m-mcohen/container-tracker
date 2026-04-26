"""Unit tests for container_tracker.core.excel."""

from openpyxl import load_workbook

from container_tracker.core.excel import (
    find_container_column,
    read_containers_from_excel,
)


class TestReadContainersFromExcel:
    def test_returns_uppercased_normalized_list(self, sample_workbook):
        path = sample_workbook(rows=("mscu1111111", "  MAEU2222222  ", "EGLV3333333"))
        result = read_containers_from_excel(path)
        assert result == ["MSCU1111111", "MAEU2222222", "EGLV3333333"]

    def test_skips_short_values(self, sample_workbook):
        # Anything under 10 chars is treated as noise (e.g. notes / IDs).
        path = sample_workbook(rows=("MSCU1111111", "X", "AB", "EGLV3333333"))
        result = read_containers_from_excel(path)
        assert result == ["MSCU1111111", "EGLV3333333"]

    def test_alternative_header_cntr_no(self, sample_workbook):
        path = sample_workbook(headers=("cntr no",), rows=("MSCU9999999",))
        assert read_containers_from_excel(path) == ["MSCU9999999"]

    def test_returns_empty_when_no_container_column(self, sample_workbook):
        path = sample_workbook(headers=("UnrelatedHeader",), rows=("MSCU1111111",))
        assert read_containers_from_excel(path) == []


class TestFindContainerColumn:
    def test_canonical_header_index_1(self, sample_workbook):
        path = sample_workbook(headers=("Container #",))
        wb = load_workbook(str(path))
        assert find_container_column(wb.active) == 1
        wb.close()

    def test_substring_match_fallback(self, sample_workbook):
        # "Master container" doesn't match the keyword list literally, but the
        # substring 'container' triggers the second-pass fallback.
        path = sample_workbook(headers=("Master container",), rows=("MSCU1111111",))
        wb = load_workbook(str(path))
        assert find_container_column(wb.active) == 1
        wb.close()
