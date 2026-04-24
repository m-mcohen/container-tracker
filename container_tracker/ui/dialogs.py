"""SetupDialog — modal dialog for first-run (Welcome) and Settings.

Two modes share one class per spec §5.3. Live validation is wired in Task 8;
this skeleton just lays out the widgets and exposes them to tests.
"""
from __future__ import annotations

import logging
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


logger = logging.getLogger(__name__)


SetupDialogMode = Literal["welcome", "settings"]


class SetupDialog(QDialog):
    """Modal dialog for collecting company_name + ShipsGo API key + contact_email.

    mode="welcome"  — first-run. No Cancel button. Closing via × quits the app.
    mode="settings" — edit settings. Has Cancel. × just dismisses.
    """

    def __init__(
        self,
        mode: SetupDialogMode = "welcome",
        initial_company: str = "",
        initial_email: str = "",
        initial_api_key_set: bool = False,
        app_version: str = "",
        data_folder: str = "",
        github_repo_url: str = "https://github.com/m-mcohen/container-tracker",
    ) -> None:
        super().__init__()
        if mode not in ("welcome", "settings"):
            raise ValueError(f"mode must be 'welcome' or 'settings'; got {mode!r}")
        self._mode: SetupDialogMode = mode
        self._initial_api_key_set = initial_api_key_set

        if mode == "welcome":
            self.setWindowTitle("Welcome to Container Tracker")
        else:
            self.setWindowTitle("Container Tracker — Settings")
        self.setModal(True)
        self.setMinimumWidth(480)

        # Remove the × close button disappearance would be jarring; keep it.
        # In welcome mode, closeEvent quits the app. Settings mode dismisses.

        # ─── Fields ─────────────────────────────────────────────────
        self._company_input = QLineEdit(initial_company)
        self._company_input.setPlaceholderText("Your company or project name")
        self._company_error = self._make_error_label()

        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        if mode == "settings" and initial_api_key_set:
            self._api_key_input.setPlaceholderText("Leave empty to keep current key")
        else:
            self._api_key_input.setPlaceholderText(
                "ShipsGo API key (UUID from dashboard → Integrations → ShipsGo API)"
            )
        self._api_key_error = self._make_error_label()
        self._api_key_hint = QLabel(
            "Find your key at shipsgo.com → Dashboard → Integrations → ShipsGo API"
        )
        self._api_key_hint.setProperty("role", "hint")

        self._email_input = QLineEdit(initial_email)
        self._email_input.setPlaceholderText("contact@yourcompany.com")
        self._email_error = self._make_error_label()

        # ─── Save / Cancel buttons ──────────────────────────────────
        self._save_button = QPushButton("Save")
        self._save_button.setProperty("variant", "primary")
        self._save_button.setEnabled(False)
        self._save_button.clicked.connect(self.accept)

        self._cancel_button: QPushButton | None = None
        if mode == "settings":
            self._cancel_button = QPushButton("Cancel")
            self._cancel_button.setProperty("variant", "secondary")
            self._cancel_button.clicked.connect(self.reject)

        # ─── Settings-only read-only info ───────────────────────────
        self._version_label: QLabel | None = None
        self._data_folder_label: QLabel | None = None
        self._data_folder_path: str = data_folder  # stored for click handler
        self._repo_link_label: QLabel | None = None
        if mode == "settings":
            self._version_label = QLabel(f"Container Tracker v{app_version}")
            self._version_label.setProperty("role", "hint")

            # Clickable HTML link that opens the folder in Explorer.
            # Uses href="folder" as a sentinel; linkActivated fires the real open.
            self._data_folder_label = QLabel(
                f'Data folder: <a href="folder" style="color: inherit;">{data_folder}</a>'
            )
            self._data_folder_label.setProperty("role", "hint")
            self._data_folder_label.setTextFormat(Qt.TextFormat.RichText)
            self._data_folder_label.linkActivated.connect(self._on_data_folder_clicked)

            self._repo_link_label = QLabel(
                f'<a href="{github_repo_url}" style="color: inherit;">GitHub repo</a>'
            )
            self._repo_link_label.setOpenExternalLinks(True)
            self._repo_link_label.setProperty("role", "hint")

        # ─── Layout ─────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        if mode == "welcome":
            intro = QLabel(
                "Let's get you set up. You can change these later in Settings."
            )
            intro.setWordWrap(True)
            root.addWidget(intro)

        root.addWidget(self._field_block("Company name", self._company_input, self._company_error))
        root.addWidget(self._api_key_block())
        root.addWidget(self._field_block("Contact email", self._email_input, self._email_error))

        if mode == "settings":
            # Read-only info block above the buttons.
            root.addStretch(1)
            info = QVBoxLayout()
            assert self._version_label is not None
            assert self._data_folder_label is not None
            assert self._repo_link_label is not None
            info.addWidget(self._version_label)
            info.addWidget(self._data_folder_label)
            info.addWidget(self._repo_link_label)
            info_container = QWidget()
            info_container.setLayout(info)
            root.addWidget(info_container)

        # Button row
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        if self._cancel_button is not None:
            button_row.addWidget(self._cancel_button)
        button_row.addWidget(self._save_button)
        root.addLayout(button_row)

    # ─── Helpers ──────────────────────────────────────────────────────

    def _make_error_label(self) -> QLabel:
        label = QLabel("")
        label.setProperty("role", "hint")
        label.setProperty("statRole", "delayed")  # muted rust for error text
        label.hide()
        return label

    def _field_block(self, label_text: str, input_widget: QLineEdit, error_label: QLabel) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        # HTML <b> is rendered by QLabel's default AutoText textFormat.
        # Avoids adding a new QSS role just for field labels.
        label = QLabel(f"<b>{label_text}</b>")
        layout.addWidget(label)
        layout.addWidget(input_widget)
        layout.addWidget(error_label)
        return container

    def _api_key_block(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel("<b>ShipsGo API key</b>")
        layout.addWidget(label)
        layout.addWidget(self._api_key_input)
        layout.addWidget(self._api_key_hint)
        layout.addWidget(self._api_key_error)
        return container

    # ─── Qt lifecycle ─────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._mode == "welcome":
            # × on welcome mode quits the app (spec §5.3).
            from PySide6.QtWidgets import QApplication
            logger.info("Welcome dialog closed via × — quitting app")
            super().closeEvent(event)
            instance = QApplication.instance()
            if instance is not None:
                instance.quit()
        else:
            super().closeEvent(event)

    # ─── Data folder click handler (settings mode) ────────────────────

    def _on_data_folder_clicked(self, href: str) -> None:
        """Open the data folder in Windows Explorer (or platform equivalent)."""
        import os
        import subprocess
        import sys
        path = self._data_folder_path
        logger.info("Opening data folder: %s", path)
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            logger.info("Failed to open data folder: %s", exc)
