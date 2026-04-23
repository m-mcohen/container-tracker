"""Unit tests for ContainerTableModel and StatusBucketSortProxy."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from container_tracker.ui.model import ContainerTableModel


SAMPLE_RECORDS = [
    {
        "container_number": "MSKU1234567",
        "carrier": "MAERSK LINE",
        "status": "SAILING",
        "original_eta": "2026-05-01",
        "eta": "2026-05-05",
        "delay_days": "+4 days",
        "delay_days_int": 4,
        "pol": "Shanghai",
        "pod": "Los Angeles",
        "vessel": "MV SEA PIONEER",
        "transit_pct": 42,
    },
    {
        "container_number": "CMAU7654321",
        "carrier": "CMA CGM",
        "status": "ARRIVED",
        "original_eta": "2026-03-20",
        "eta": "2026-03-20",
        "delay_days": "On time",
        "delay_days_int": 0,
        "pol": "Ningbo",
        "pod": "Long Beach",
        "vessel": "MV PACIFIC STAR",
        "transit_pct": 100,
    },
]


class TestContainerTableModel:
    def test_rowcount_matches_records(self, qapp) -> None:
        model = ContainerTableModel()
        assert model.rowCount() == 0
        model.set_records(SAMPLE_RECORDS)
        assert model.rowCount() == 2

    def test_column_count(self, qapp) -> None:
        model = ContainerTableModel()
        # 9 columns: Container #, Carrier, Status, Original ETA, Current ETA, Delay, Route, Vessel, Transit %
        assert model.columnCount() == 9

    def test_header_labels(self, qapp) -> None:
        model = ContainerTableModel()
        headers = [
            model.headerData(c, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            for c in range(model.columnCount())
        ]
        assert headers == [
            "Container #", "Carrier", "Status", "Original ETA", "Current ETA",
            "Delay", "Route", "Vessel", "Transit %",
        ]

    def test_display_role_returns_formatted_strings(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)

        idx = model.index(0, 0)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "MSKU1234567"
        idx = model.index(0, 2)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "SAILING"
        idx = model.index(0, 5)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "+4 days"

    def test_route_is_pol_arrow_pod_single_cell(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(0, 6)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "Shanghai \u2192 Los Angeles"

    def test_transit_pct_formatted_with_percent(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(0, 8)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "42%"

    def test_transit_pct_empty_when_missing(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records([{"container_number": "X", "transit_pct": ""}])
        idx = model.index(0, 8)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == ""

    def test_foreground_role_on_status_sailing(self, qapp) -> None:
        from container_tracker.ui.theme import LIGHT_PALETTE
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(0, 2)  # Status column, SAILING row
        color = model.data(idx, Qt.ItemDataRole.ForegroundRole)
        assert color is not None
        # QColor stringifies to "#xxxxxx" in upper case via .name().
        assert color.name().upper() == LIGHT_PALETTE["status_sailing"].upper()

    def test_foreground_role_on_status_arrived(self, qapp) -> None:
        from container_tracker.ui.theme import LIGHT_PALETTE
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(1, 2)  # Status column, ARRIVED row
        color = model.data(idx, Qt.ItemDataRole.ForegroundRole)
        assert color is not None
        assert color.name().upper() == LIGHT_PALETTE["status_arrived"].upper()

    def test_foreground_role_on_non_status_column_is_none(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(0, 0)  # Container # column
        assert model.data(idx, Qt.ItemDataRole.ForegroundRole) is None

    def test_text_alignment_right_on_delay(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(0, 5)  # Delay
        alignment = model.data(idx, Qt.ItemDataRole.TextAlignmentRole)
        assert alignment is not None
        assert int(alignment) & int(Qt.AlignmentFlag.AlignRight)

    def test_text_alignment_right_on_transit_pct(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        idx = model.index(0, 8)  # Transit %
        alignment = model.data(idx, Qt.ItemDataRole.TextAlignmentRole)
        assert alignment is not None
        assert int(alignment) & int(Qt.AlignmentFlag.AlignRight)

    def test_set_records_resets_and_emits(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        assert model.rowCount() == 2
        model.set_records([])
        assert model.rowCount() == 0

    def test_remove_rows_by_index(self, qapp) -> None:
        model = ContainerTableModel()
        model.set_records(SAMPLE_RECORDS)
        model.remove_rows([0])
        assert model.rowCount() == 1
        remaining = model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole)
        assert remaining == "CMAU7654321"

    def test_remove_rows_multiple_preserves_order(self, qapp) -> None:
        records = [{"container_number": f"X{n:09d}", "status": ""} for n in range(5)]
        model = ContainerTableModel()
        model.set_records(records)
        model.remove_rows([1, 3])
        remaining = [
            model.data(model.index(r, 0), Qt.ItemDataRole.DisplayRole)
            for r in range(model.rowCount())
        ]
        assert remaining == ["X000000000", "X000000002", "X000000004"]
