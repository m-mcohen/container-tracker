"""Theme preview harness.

Standalone dev tool. Run with:
    python -m container_tracker.ui.theme_preview

Shows every styled widget the design system covers — primary/secondary/
destructive buttons, inputs, combo boxes, outlined cards, stat card,
table with headers, activity log — with a top toggle between light and
dark mode. Visual verification of spec §5.1 end-to-end.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from container_tracker.ui.theme import apply_theme


def _card(title: str, body: QWidget) -> QFrame:
    frame = QFrame()
    frame.setProperty("role", "card")
    layout = QVBoxLayout(frame)
    heading = QLabel(title)
    heading.setProperty("role", "heading")
    layout.addWidget(heading)
    layout.addWidget(body)
    return frame


def _stat_card(label: str, number: str, color_role: str) -> QFrame:
    frame = QFrame()
    frame.setProperty("role", "stat-card")
    layout = QVBoxLayout(frame)
    caption = QLabel(label)
    caption.setProperty("role", "secondary")
    number_label = QLabel(number)
    number_label.setProperty("role", "display")
    if color_role:
        # Mark the number with a role so a future QSS rule could tint it.
        # For now we stay within the palette via direct property.
        number_label.setProperty("statRole", color_role)
    layout.addWidget(caption)
    layout.addWidget(number_label)
    return frame


def _buttons_row() -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)

    primary = QPushButton("Refresh All ETAs & Update Excel")
    primary.setProperty("variant", "primary")

    secondary = QPushButton("Browse…")
    secondary.setProperty("variant", "secondary")

    destructive = QPushButton("Remove Selected")
    destructive.setProperty("variant", "destructive")

    default = QPushButton("Default (no variant)")

    for btn in (primary, secondary, destructive, default):
        layout.addWidget(btn)
    return row


def _inputs_row() -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)

    line = QLineEdit()
    line.setPlaceholderText("Container number, e.g. MSKU1234567")

    disabled_line = QLineEdit("disabled value")
    disabled_line.setDisabled(True)

    combo = QComboBox()
    combo.addItems(["MAERSK LINE", "MSC", "CMA CGM", "HAPAG LLOYD", "EVERGREEN"])

    for w in (line, disabled_line, combo):
        layout.addWidget(w)
    return row


def _stats_row() -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    for label, number, role in [
        ("Tracked", "12", ""),
        ("Sailing", "7", "sailing"),
        ("Arrived", "4", "arrived"),
        ("Delayed", "1", "delayed"),
    ]:
        layout.addWidget(_stat_card(label, number, role))
    return row


def _table_sample() -> QTableWidget:
    table = QTableWidget(3, 7)
    table.setHorizontalHeaderLabels(
        ["Container #", "Carrier", "Status", "ETA", "Delay", "Route", "Vessel"]
    )
    data = [
        ("MSKU1234567", "MAERSK LINE", "SAILING", "2026-05-05", "+4 days", "Shanghai → LA", "MV SEA PIONEER"),
        ("CMAU7654321", "CMA CGM",     "ARRIVED", "2026-03-20", "On time", "Ningbo → Long Beach", "MV PACIFIC STAR"),
        ("MSCU1111222", "MSC",         "SAILING", "2026-04-30", "",        "Rotterdam → NY", "MV ATLANTIC"),
    ]
    for row_idx, row_values in enumerate(data):
        for col_idx, value in enumerate(row_values):
            table.setItem(row_idx, col_idx, QTableWidgetItem(value))
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.verticalHeader().setVisible(False)
    return table


def _activity_log() -> QPlainTextEdit:
    log = QPlainTextEdit()
    log.setReadOnly(True)
    log.setPlainText(
        "2026-04-23 11:33:04 [INFO] Refreshing...\n"
        "2026-04-23 11:33:05 [INFO] Found 12 shipments\n"
        "2026-04-23 11:33:06 [INFO]   MSKU1234567: SAILING, ETA 2026-05-05, Shanghai → LA\n"
        "2026-04-23 11:33:06 [INFO]   CMAU7654321: ARRIVED, ETA 2026-03-20, Ningbo → Long Beach\n"
        "2026-04-23 11:33:07 [INFO] --- DONE: 12 matched, 0 unmatched, 1 delayed\n"
    )
    return log


class PreviewWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Container Tracker — Theme Preview")
        self.resize(1100, 900)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Top row — dark mode toggle.
        top = QHBoxLayout()
        heading = QLabel("Theme preview")
        heading.setProperty("role", "heading")
        top.addWidget(heading)
        top.addStretch(1)
        self._toggle = QCheckBox("Dark mode")
        self._toggle.stateChanged.connect(self._on_toggle)
        top.addWidget(self._toggle)
        root.addLayout(top)

        # Scroll area in case the harness outgrows the window.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)

        content_layout.addWidget(_card("Buttons (primary / secondary / destructive / default)", _buttons_row()))
        content_layout.addWidget(_card("Inputs (QLineEdit + QComboBox + disabled)", _inputs_row()))
        content_layout.addWidget(_card("Stat cards", _stats_row()))
        content_layout.addWidget(_card("Table", _table_sample()))
        content_layout.addWidget(_card("Activity log (QPlainTextEdit, mono)", _activity_log()))

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _on_toggle(self, state: int) -> None:
        is_dark = state == Qt.CheckState.Checked.value
        apply_theme(is_dark=is_dark)


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(is_dark=False)
    window = PreviewWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
