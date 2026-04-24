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
from container_tracker.core.api import CARRIER_NAMES, ShipsGoAuthError, ShipsGoClient
from container_tracker.core.persistence import load_tracking_data
from container_tracker.core.status import bucket_counts
from container_tracker.core.updates import UpdateInfo
from container_tracker.ui.model import ContainerTableModel, StatusBucketSortProxy
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
        self._tracking_db: dict[str, dict[str, Any]] = {}
        self._client: ShipsGoClient | None = None

        self.setWindowTitle(f"Container Tracker v{__version__}")
        self.resize(QSize(1100, 720))

        self._build_layout()
        self._populate_data()
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
        self._banner.dismissed.connect(self._on_banner_dismissed)
        self._banner.open_url_requested.connect(self._on_banner_open_url)
        self._update_check_dispatched = False  # prevents re-dispatch on repeated showEvents
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
        self._linked.browse_requested.connect(self._on_browse)
        self._linked.create_requested.connect(self._on_create_template)
        self._linked.open_requested.connect(self._on_open_excel)
        # Phase 5: ensure Open button reflects current path state (was force-disabled in Phase 4).
        self._linked.set_path(str(self._config.get("excel_path", "") or ""))
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
        self._refresh_button.clicked.connect(self._on_refresh)

        self._remove_button = QPushButton("Remove Selected")
        self._remove_button.setProperty("variant", "destructive")
        self._remove_button.clicked.connect(self._on_remove_selected)
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
        self._add_button.clicked.connect(self._on_add_track)
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

    def _populate_data(self) -> None:
        """Load tracking data from disk and render into model + stat cards."""
        db = load_tracking_data()
        self._tracking_db = db
        self._model.set_records(list(db.values()))
        self._refresh_stat_cards(db)
        logger.info("Loaded tracking data: %d containers", len(db))

    def _refresh_stat_cards(self, db: dict[str, dict[str, Any]]) -> None:
        counts = bucket_counts(db)
        self._stat_tracked.set_number(counts["total"])
        self._stat_sailing.set_number(counts["sailing"])
        self._stat_arrived.set_number(counts["arrived"])
        self._stat_delayed.set_number(counts["delayed"])

    # ─── Helpers ──────────────────────────────────────────────────────

    def _show_error_modal(self, title: str, message: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _show_auth_error_modal(self) -> None:
        """401 from ShipsGo — prompt user to open Settings."""
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("API key invalid")
        box.setText(
            "Your ShipsGo API key is invalid. Open Settings to update it."
        )
        open_settings = box.addButton("Open Settings…", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_settings:
            self._on_settings_clicked()

    def _ensure_client(self) -> ShipsGoClient | None:
        """Lazy-construct a ShipsGoClient using the current keyring token.

        Returns None if no token is set (in which case the auth-error modal is shown).
        """
        from container_tracker.core.persistence import get_api_token
        token = get_api_token()
        if not token:
            self._show_auth_error_modal()
            return None
        if self._client is None or getattr(self._client, "_last_token", None) != token:
            self._client = ShipsGoClient(token)
            self._client._last_token = token  # type: ignore[attr-defined]
        return self._client

    # ─── Slots ────────────────────────────────────────────────────────

    def _on_browse(self) -> None:
        """Open file dialog, validate, persist."""
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        from container_tracker.core.excel import ExcelFormatError, read_container_list
        from container_tracker.core.persistence import save_config

        start_dir = str(self._config.get("excel_path") or Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select container spreadsheet",
            start_dir,
            "Excel files (*.xlsx *.xlsm)",
        )
        if not path:
            return  # user cancelled

        # Validate by reading the container column.
        try:
            containers = read_container_list(Path(path))
        except ExcelFormatError as exc:
            self._show_error_modal("Can't read spreadsheet", str(exc))
            return

        self._config["excel_path"] = path
        save_config(self._config)
        self._linked.set_path(path)
        logger.info("Linked spreadsheet: %s (%d containers detected)", path, len(containers))

    def _on_open_excel(self, path: str) -> None:
        """Open the linked spreadsheet in the system default handler (Excel on Windows)."""
        import os
        import subprocess
        import sys
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            logger.info("Opened %s in default handler", path)
        except Exception as exc:
            self._show_error_modal("Can't open spreadsheet", str(exc))

    def _on_create_template(self) -> None:
        """Pick save path, create template, persist."""
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        from container_tracker.core.excel import create_template
        from container_tracker.core.persistence import save_config

        start_path = str(Path.home() / "container_tracking.xlsx")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Create template spreadsheet",
            start_path,
            "Excel files (*.xlsx)",
        )
        if not path:
            return
        try:
            create_template(Path(path))
        except Exception as exc:
            self._show_error_modal("Can't create template", str(exc))
            return

        self._config["excel_path"] = path
        save_config(self._config)
        self._linked.set_path(path)
        logger.info("Created template at %s and linked it", path)

    def _on_remove_selected(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        from container_tracker.core.persistence import save_tracking_data

        selection = self._table.selectionModel().selectedRows()
        if not selection:
            self._show_error_modal("No selection", "Select one or more rows to remove.")
            return

        # Map proxy rows back to source rows, then to records.
        source_rows: list[int] = []
        container_numbers: list[str] = []
        for proxy_index in selection:
            source_index = self._proxy.mapToSource(proxy_index)
            record = self._model.record_at(source_index.row())
            if record is None:
                continue
            source_rows.append(source_index.row())
            container_numbers.append(str(record.get("container_number", "")))

        if not container_numbers:
            return

        confirm = QMessageBox.question(
            self,
            "Remove from tracking",
            f"Remove {len(container_numbers)} container(s) from tracking?\n\n"
            + ", ".join(container_numbers),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # Remove from tracking_db and model.
        for cn in container_numbers:
            self._tracking_db.pop(cn, None)
        save_tracking_data(self._tracking_db)
        self._model.remove_rows(source_rows)
        self._refresh_stat_cards(self._tracking_db)
        logger.info("Removed %d container(s): %s", len(container_numbers), container_numbers)

    def _on_add_track(self) -> None:
        from PySide6.QtCore import QThreadPool

        from container_tracker.core.api import resolve_scac
        from container_tracker.core.persistence import save_tracking_data
        from container_tracker.ui.runnables import AddTrackRunnable

        text = self._add_input.text().strip().upper()
        if len(text) < 10:
            self._show_error_modal(
                "Invalid container number",
                "Container numbers should be at least 10 characters.",
            )
            return
        carrier_name = self._carrier_combo.currentText()
        scac = resolve_scac(carrier_name)

        client = self._ensure_client()
        if client is None:
            return

        self._add_button.setEnabled(False)

        runnable = AddTrackRunnable(client, text, scac)

        def on_completed(record: dict[str, Any]) -> None:
            cn = record.get("container_number", "").upper()
            if cn:
                self._tracking_db[cn] = record
                save_tracking_data(self._tracking_db)
                self._model.set_records(list(self._tracking_db.values()))
                self._refresh_stat_cards(self._tracking_db)
                logger.info("Added %s to tracking", cn)
            self._add_input.clear()
            self._add_button.setEnabled(True)

        def on_already_tracked(cn: str) -> None:
            self._show_error_modal(
                "Already tracked",
                f"{cn} is already in your tracking list. Use Refresh to update it.",
            )
            self._add_button.setEnabled(True)

        def on_no_credits() -> None:
            self._show_error_modal(
                "Not enough credits",
                "ShipsGo reports you don't have enough credits to track a new container. Visit shipsgo.com to top up.",
            )
            self._add_button.setEnabled(True)

        def on_auth() -> None:
            self._show_auth_error_modal()
            self._add_button.setEnabled(True)

        def on_failed(msg: str) -> None:
            self._show_error_modal("Add failed", msg)
            self._add_button.setEnabled(True)

        runnable.signals.completed.connect(on_completed)
        runnable.signals.already_tracked.connect(on_already_tracked)
        runnable.signals.no_credits.connect(on_no_credits)
        runnable.signals.auth_error.connect(on_auth)
        runnable.signals.failed.connect(on_failed)
        QThreadPool.globalInstance().start(runnable)

    def _on_refresh(self) -> None:
        from pathlib import Path

        from PySide6.QtCore import QThreadPool

        from container_tracker.core.excel import ExcelFormatError, write_tracking_report
        from container_tracker.core.persistence import save_tracking_data
        from container_tracker.ui.runnables import RefreshRunnable

        client = self._ensure_client()
        if client is None:
            return

        self._refresh_button.setEnabled(False)

        runnable = RefreshRunnable(client, dict(self._tracking_db))

        def on_completed(new_db: dict[str, dict[str, Any]]) -> None:
            self._tracking_db = new_db
            save_tracking_data(new_db)
            self._model.set_records(list(new_db.values()))
            self._refresh_stat_cards(new_db)
            # Also write to linked Excel if a path is configured.
            excel_path = self._config.get("excel_path", "")
            if excel_path:
                try:
                    count = write_tracking_report(Path(excel_path), new_db)
                    logger.info("Excel updated: %d rows", count)
                except ExcelFormatError as exc:
                    self._show_error_modal("Can't update spreadsheet", str(exc))
                except Exception as exc:
                    logger.info("Excel update failed: %s", exc)
            self._refresh_button.setEnabled(True)

        def on_failed(msg: str) -> None:
            self._show_error_modal("Refresh failed", msg)
            self._refresh_button.setEnabled(True)

        def on_auth() -> None:
            self._show_auth_error_modal()
            self._refresh_button.setEnabled(True)

        runnable.signals.completed.connect(on_completed)
        runnable.signals.failed.connect(on_failed)
        runnable.signals.auth_error.connect(on_auth)
        QThreadPool.globalInstance().start(runnable)

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
        if not self._update_check_dispatched:
            self._update_check_dispatched = True
            self._dispatch_update_check()

    def closeEvent(self, event: QCloseEvent) -> None:
        logger.info("MainWindow closing")
        super().closeEvent(event)

    # ─── Update check ─────────────────────────────────────────────────

    def _dispatch_update_check(self) -> None:
        from PySide6.QtCore import QThreadPool

        from container_tracker.ui.runnables import UpdateCheckRunnable

        runnable = UpdateCheckRunnable(current_version=__version__)
        runnable.signals.update_available.connect(self._on_update_available)
        QThreadPool.globalInstance().start(runnable)

    def _on_update_available(self, info: UpdateInfo) -> None:
        logger.info("Update available: v%s at %s", info.version, info.html_url)
        self._banner.show_update(info.version, info.html_url)

    def _on_banner_dismissed(self) -> None:
        # Session-only dismissal — no config change.
        logger.info("Update banner dismissed for this session")

    def _on_banner_open_url(self, url: str) -> None:
        import webbrowser
        logger.info("Opening release URL: %s", url)
        webbrowser.open(url)
