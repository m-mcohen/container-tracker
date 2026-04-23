"""Qt models for the container table.

ContainerTableModel holds tracking records in a list[dict] and exposes them
via QAbstractTableModel. StatusBucketSortProxy (Task 8) adds bucket-priority
sort on the Status column. MainWindow (Task 10) wires it together.
"""
from __future__ import annotations

from typing import Any, Final

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QColor

from container_tracker.core.status import StatusBucket, normalize_status
from container_tracker.ui.theme import LIGHT_PALETTE


# Column definition: (header_label, field_key)
# field_key is used by _format_display; None means a computed / synthetic column.
_COLUMNS: Final[tuple[tuple[str, str | None], ...]] = (
    ("Container #",  "container_number"),
    ("Carrier",      "carrier"),
    ("Status",       "status"),
    ("Original ETA", "original_eta"),
    ("Current ETA",  "eta"),
    ("Delay",        "delay_days"),
    ("Route",        None),               # computed from pol + pod
    ("Vessel",       "vessel"),
    ("Transit %",    "transit_pct"),
)

_STATUS_COLUMN: Final[int] = 2
_DELAY_COLUMN: Final[int] = 5
_ROUTE_COLUMN: Final[int] = 6
_TRANSIT_PCT_COLUMN: Final[int] = 8


_BUCKET_TO_PALETTE_KEY: Final[dict[StatusBucket, str]] = {
    StatusBucket.SAILING: "status_sailing",
    StatusBucket.ARRIVED: "status_arrived",
    # DELAYED bucket doesn't exist as a raw ShipsGo status — it's derived.
    # For now we color only SAILING/ARRIVED; Delayed rows show with SAILING
    # foreground (they're SAILING with a delay).
}


class ContainerTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._records: list[dict[str, Any]] = []

    # ─── Qt API ───────────────────────────────────────────────────────

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._records)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(_COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == int(Qt.ItemDataRole.DisplayRole)
            and 0 <= section < len(_COLUMNS)
        ):
            return _COLUMNS[section][0]
        return None

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._records)):
            return None
        record = self._records[index.row()]
        col = index.column()

        if role == int(Qt.ItemDataRole.DisplayRole):
            return self._format_display(record, col)

        if role == int(Qt.ItemDataRole.ForegroundRole) and col == _STATUS_COLUMN:
            bucket = normalize_status(str(record.get("status", "")))
            palette_key = _BUCKET_TO_PALETTE_KEY.get(bucket)
            if palette_key is None:
                return None
            return QColor(LIGHT_PALETTE[palette_key])

        if role == int(Qt.ItemDataRole.TextAlignmentRole) and col in (_DELAY_COLUMN, _TRANSIT_PCT_COLUMN):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        return None

    # ─── Mutation API ─────────────────────────────────────────────────

    def set_records(self, records: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._records = list(records)
        self.endResetModel()

    def remove_rows(self, row_indexes: list[int]) -> None:
        """Remove rows by index. Indexes may be in any order; they're deduplicated and sorted."""
        if not row_indexes:
            return
        to_remove = sorted(set(row_indexes), reverse=True)
        self.beginResetModel()
        for row in to_remove:
            if 0 <= row < len(self._records):
                del self._records[row]
        self.endResetModel()

    def record_at(self, row: int) -> dict[str, Any] | None:
        """Return the raw record dict at the given row (useful for main window logic)."""
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    # ─── Helpers ──────────────────────────────────────────────────────

    def _format_display(self, record: dict[str, Any], col: int) -> str:
        if col == _ROUTE_COLUMN:
            pol = str(record.get("pol", "") or "")
            pod = str(record.get("pod", "") or "")
            if pol and pod:
                return f"{pol} \u2192 {pod}"
            return pol or pod

        field_key = _COLUMNS[col][1]
        if field_key is None:
            return ""
        value: Any = record.get(field_key, "")

        if col == _TRANSIT_PCT_COLUMN:
            if value == "" or value is None:
                return ""
            return f"{value}%"

        return "" if value is None else str(value)


# ─────────────────────────────────────────────────────────────────────────
# Custom sort proxy — bucket priority on Status column
# ─────────────────────────────────────────────────────────────────────────

# Rank: lower = sorts first in ascending order.
_BUCKET_RANK: Final[dict[str, int]] = {
    "DELAYED": 0,
    "SAILING": 1,
    "ARRIVED": 2,
    "PENDING": 3,
    "UNKNOWN": 4,
}


class StatusBucketSortProxy(QSortFilterProxyModel):
    """Sort proxy that orders the Status column by bucket priority.

    Priority (ascending): DELAYED < SAILING < ARRIVED < PENDING < UNKNOWN.
    Shipping operators care about what's late; alphabetical would hide that.
    Other columns use default comparison.
    """

    def lessThan(
        self,
        source_left: QModelIndex | QPersistentModelIndex,
        source_right: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        if source_left.column() != _STATUS_COLUMN or source_right.column() != _STATUS_COLUMN:
            return super().lessThan(source_left, source_right)

        source = self.sourceModel()
        if not isinstance(source, ContainerTableModel):
            return super().lessThan(source_left, source_right)

        left_rank = self._rank_for_row(source, source_left.row())
        right_rank = self._rank_for_row(source, source_right.row())
        return left_rank < right_rank

    @staticmethod
    def _rank_for_row(source: ContainerTableModel, row: int) -> int:
        record = source.record_at(row) or {}
        bucket = normalize_status(str(record.get("status", "")))
        delay = record.get("delay_days_int")
        if bucket == StatusBucket.SAILING and isinstance(delay, int) and delay > 0:
            return _BUCKET_RANK["DELAYED"]
        return _BUCKET_RANK[bucket.value]
