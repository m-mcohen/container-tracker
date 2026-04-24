"""Main application window — full layout (Phase 3).

Composes header, update banner, linked-spreadsheet card, stat cards, action
row, container table, activity log, and footer. Populated with sample data.
Backend functionality arrives in Phase 5.
"""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from container_tracker.__version__ import __version__
from container_tracker.core.api import CARRIER_NAMES
from container_tracker.core.status import bucket_counts
from container_tracker.ui.model import ContainerTableModel, StatusBucketSortProxy
from container_tracker.ui.sample_data import sample_tracking_db
from container_tracker.ui.theme import apply_theme
from container_tracker.ui.widgets import (
    HeaderRow,
    LinkedSpreadsheetCard,
    QtLogHandler,
    StatCard,
    UpdateBanner,
)


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main window. Owns config, is_dark, table model, and sub-widgets per spec §3.3."""

    def __init__(self, config: dict[str, Any], qt_handler: QtLogHandler) -> None:
        super().__init__()
        self._config = config
        self._qt_handler = qt_handler
        self._is_dark: bool = bool(config.get("dark_mode", False))

        self.setWindowTitle(f"Container Tracker v{__version__}")
        self.resize(QSize(1100, 720))

        self._build_layout()
        self._populate_sample_data()
        self._table.resizeColumnsToContents()

        logger.info("MainWindow constructed (is_dark=%s)", self._is_dark)

    # ─── Public API ───────────────────────────────────────────────────

    @property
    def is_dark(self) -> bool:
        return self._is_dark

    def toggle_dark_mode(self) -> None:
        """Flip the theme, regenerate the app-level stylesheet, persist to config."""
        self._is_dark = not self._is_dark
        apply_theme(is_dark=self._is_dark)
        self._config["dark_mode"] = self._is_dark
        logger.info("dark mode toggled → %s", self._is_dark)

    def refresh_from_config(self) -> None:
        """Re-read config and update header + linked-spreadsheet card.

        Called after the Settings dialog saves changes. Only updates the
        widgets whose values can change via Settings: company_name (header
        subtitle) and excel_path (linked-spreadsheet path display).
        """
        company = str(self._config.get("company_name", "") or "")
        self._header.set_subtitle(company or "Unconfigured — open Settings")
        excel_path = str(self._config.get("excel_path", "") or "")
        self._linked.set_path(excel_path)
        logger.info("refresh_from_config applied: company=%r, excel=%r", company, excel_path)

    # ─── Layout composition ───────────────────────────────────────────

    def _build_layout(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(16)

        self._banner = UpdateBanner()
        root.addWidget(self._banner)

        self._header = HeaderRow(
            title="Container Tracker",
            subtitle=str(self._config.get("company_name", "") or "Unconfigured — open Settings"),
            is_dark=self._is_dark,
        )
        self._header.dark_mode_toggled.connect(self._on_dark_mode_toggled)
        self._header.settings_clicked.connect(self._on_settings_clicked)
        root.addWidget(self._header)

        self._linked = LinkedSpreadsheetCard(str(self._config.get("excel_path", "") or ""))
        # Phase 4: buttons are placeholders until Phase 5 wires them.
        self._linked._browse_button.setEnabled(False)
        self._linked._create_button.setEnabled(False)
        # _open_button already disabled when path is empty; force disable regardless
        # until Phase 5 restores the dynamic enable/disable behavior.
        self._linked._open_button.setEnabled(False)
        root.addWidget(self._linked)

        # Stat cards ---------------------------------------------------
        self._stat_tracked = StatCard("Tracked", 0)
        self._stat_sailing = StatCard("Sailing", 0, color_role="sailing")
        self._stat_arrived = StatCard("Arrived", 0, color_role="arrived")
        self._stat_delayed = StatCard("Delayed", 0, color_role="delayed")
        stat_row = QWidget()
        stat_layout = QHBoxLayout(stat_row)
        stat_layout.setContentsMargins(0, 0, 0, 0)
        stat_layout.setSpacing(12)
        for card in (self._stat_tracked, self._stat_sailing, self._stat_arrived, self._stat_delayed):
            stat_layout.addWidget(card, stretch=1)
        root.addWidget(stat_row)

        # Action row ---------------------------------------------------
        action_row = QWidget()
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self._refresh_button = QPushButton("Refresh All ETAs && Update Excel")  # && escapes for button mnemonic
        self._refresh_button.setProperty("variant", "primary")
        self._refresh_button.setEnabled(False)

        self._remove_button = QPushButton("Remove Selected")
        self._remove_button.setProperty("variant", "destructive")
        self._remove_button.setEnabled(False)
        action_layout.addWidget(self._refresh_button)
        action_layout.addWidget(self._remove_button)
        action_layout.addStretch(1)

        self._add_input = QLineEdit()
        self._add_input.setPlaceholderText("Container number, e.g. MSKU1234567")
        self._add_input.setMinimumWidth(260)
        self._carrier_combo = QComboBox()
        self._carrier_combo.addItems(CARRIER_NAMES)
        self._add_button = QPushButton("Add && Track")
        self._add_button.setProperty("variant", "primary")
        self._add_button.setEnabled(False)
        action_layout.addWidget(self._add_input)
        action_layout.addWidget(self._carrier_combo)
        action_layout.addWidget(self._add_button)

        root.addWidget(action_row)

        # Table --------------------------------------------------------
        self._model = ContainerTableModel()
        self._proxy = StatusBucketSortProxy()
        self._proxy.setSourceModel(self._model)
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(2, Qt.SortOrder.AscendingOrder)  # Status column, bucket-priority
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        # Keep user-resizable after the initial sizing so the user can still adjust.
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # Prevent any column from collapsing below a readable width even if the content is empty.
        header.setMinimumSectionSize(60)
        root.addWidget(self._table, stretch=1)

        # Activity log -------------------------------------------------
        self._activity_log = QPlainTextEdit()
        self._activity_log.setReadOnly(True)
        self._activity_log.setMaximumHeight(140)
        self._activity_log.setPlaceholderText("Activity log (refresh, add, remove will print here)…")
        self._qt_handler.log_emitted.connect(self._activity_log.appendPlainText)
        root.addWidget(self._activity_log)

        # Footer -------------------------------------------------------
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        left = QLabel("Powered by ShipsGo API")
        left.setProperty("role", "hint")
        right = QLabel("Refreshes are free & unlimited • All times EST")
        right.setProperty("role", "hint")
        footer_layout.addWidget(left)
        footer_layout.addStretch(1)
        footer_layout.addWidget(right)
        root.addWidget(footer)

        self.setCentralWidget(central)

    def _populate_sample_data(self) -> None:
        """Phase 3: load hardcoded sample data. Phase 5 replaces with real data."""
        db = sample_tracking_db()
        self._model.set_records(list(db.values()))
        self._refresh_stat_cards(db)
        logger.info("Loaded sample data: %d containers", len(db))

    def _refresh_stat_cards(self, db: dict[str, dict[str, Any]]) -> None:
        counts = bucket_counts(db)
        self._stat_tracked.set_number(counts["total"])
        self._stat_sailing.set_number(counts["sailing"])
        self._stat_arrived.set_number(counts["arrived"])
        self._stat_delayed.set_number(counts["delayed"])

    # ─── Slots ────────────────────────────────────────────────────────

    def _on_dark_mode_toggled(self, is_dark: bool) -> None:
        if is_dark != self._is_dark:
            self.toggle_dark_mode()

    def _on_settings_clicked(self) -> None:
        """Open Settings dialog; on Save, persist to config + keyring and refresh."""
        from container_tracker.__version__ import __version__ as app_version
        from container_tracker.core.persistence import (
            data_dir,
            get_api_token,
            save_config,
            set_api_token,
        )
        from container_tracker.ui.dialogs import SetupDialog

        dialog = SetupDialog(
            mode="settings",
            initial_company=str(self._config.get("company_name", "") or ""),
            initial_email=str(self._config.get("contact_email", "") or ""),
            initial_api_key_set=bool(get_api_token()),
            app_version=app_version,
            data_folder=str(data_dir()),
        )
        result = dialog.exec()
        if result != dialog.DialogCode.Accepted:
            logger.info("Settings dialog cancelled")
            return
        values = dialog.get_values()
        self._config["company_name"] = values["company"] or ""
        self._config["contact_email"] = values["email"] or ""
        save_config(self._config)
        # api_key contract: None means "keep current keyring entry" (user left the
        # field empty in settings mode). It does NOT mean "clear the key." A real
        # empty-string from the dialog would only reach this branch if the user
        # is in welcome mode or typed and deleted content — both caught by the
        # dialog's validation before accept. Never call set_api_token("") here.
        if values["api_key"] is not None:
            set_api_token(values["api_key"])
        logger.info(
            "Settings saved: company=%r, email=%r, api-key-updated=%s",
            values["company"], values["email"], values["api_key"] is not None,
        )
        self.refresh_from_config()

    # ─── Qt lifecycle ─────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        logger.info("MainWindow shown")
        super().showEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        logger.info("MainWindow closing")
        super().closeEvent(event)
