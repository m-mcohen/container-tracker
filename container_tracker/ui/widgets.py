"""Reusable UI widgets and utilities. At the end of Phase 1, only QtLogHandler lives here.

Later phases add: StatCard, UpdateBanner, ActivityLog, LinkedSpreadsheetCard.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, Signal


class QtLogHandler(QObject, logging.Handler):
    """A logging handler that emits each formatted record as a Qt signal.

    Connect the `log_emitted` signal to a slot on the UI thread (e.g. the
    activity-log widget's append method) using the default QueuedConnection.
    Worker threads call `logger.info(...)`, the record flows through this
    handler's `emit()`, and the signal delivers the text on the UI thread.
    """

    log_emitted = Signal(str)

    def __init__(self) -> None:
        QObject.__init__(self)
        logging.Handler.__init__(self)

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        # Signature collision is expected: QObject.emit (the raw signal emitter)
        # vs logging.Handler.emit(record) under multiple inheritance. Runtime is
        # correct — logging dispatches records via self.emit(record), and we
        # fire the signal via self.log_emitted.emit(message), not self.emit.
        try:
            message = self.format(record)
        except Exception:
            self.handleError(record)
            return
        self.log_emitted.emit(message)


from typing import Literal

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


StatColorRole = Literal["sailing", "arrived", "delayed"]
_VALID_COLOR_ROLES = {"sailing", "arrived", "delayed"}


class StatCard(QFrame):
    """Outlined stat card: label above, large number below.

    `color_role` tints the number per bucket; None / omitted falls back to
    default text color. Wiring is pure QSS property selectors — no per-widget
    setStyleSheet.
    """

    def __init__(
        self,
        label: str,
        number: int | str,
        color_role: StatColorRole | None = None,
    ) -> None:
        super().__init__()
        if color_role is not None and color_role not in _VALID_COLOR_ROLES:
            raise ValueError(
                f"color_role must be one of {_VALID_COLOR_ROLES} or None; got {color_role!r}"
            )
        self.setProperty("role", "stat-card")

        self._label = QLabel(label)
        self._label.setProperty("role", "secondary")

        self._number = QLabel(str(number))
        self._number.setProperty("role", "display")
        if color_role is not None:
            self._number.setProperty("statRole", color_role)

        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._number)

    def set_number(self, value: int | str) -> None:
        """Update the displayed number without reconstructing the widget."""
        self._number.setText(str(value))

    def label_text(self) -> str:
        return self._label.text()

    def number_text(self) -> str:
        return self._number.text()

    def number_label_property(self, key: str) -> object:
        """Return a Qt property set on the number QLabel (used by tests)."""
        return self._number.property(key)


from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class UpdateBanner(QFrame):
    """Non-blocking banner at the top of MainWindow announcing a newer release.

    Hidden by default. Call `show_update(version, url)` to reveal. The banner
    exposes two signals:

    - `dismissed` — the × button was clicked; MainWindow should hide the banner.
    - `open_url_requested(str)` — the body area was clicked; MainWindow should
      open the URL in the default browser via webbrowser.open().
    """

    dismissed = Signal()
    open_url_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("role", "card")  # reuses outlined-card stylesheet
        self._shown = False
        self._url = ""

        self._body_button = QPushButton("")
        self._body_button.setFlat(True)
        self._body_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._body_button.clicked.connect(self._on_body_clicked)

        self._dismiss_button = QPushButton("×")
        self._dismiss_button.setFixedSize(28, 28)
        self._dismiss_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dismiss_button.clicked.connect(self._on_dismiss_clicked)

        layout = QHBoxLayout(self)
        layout.addWidget(self._body_button, stretch=1)
        layout.addWidget(self._dismiss_button)

        self.hide()

    def show_update(self, version: str, url: str) -> None:
        """Reveal the banner with version text and a click-target URL."""
        self._url = url
        self._body_button.setText(f"Version {version} available — click to download")
        self._shown = True
        self.show()

    def message_text(self) -> str:
        return self._body_button.text()

    def is_shown(self) -> bool:
        return self._shown

    def _on_body_clicked(self) -> None:
        if self._url:
            self.open_url_requested.emit(self._url)

    def _on_dismiss_clicked(self) -> None:
        self._shown = False
        self.hide()
        self.dismissed.emit()


class LinkedSpreadsheetCard(QFrame):
    """Linked-spreadsheet card: label, current path, three buttons.

    Buttons emit signals (browse_requested, create_requested, open_requested).
    Phase 3 does not wire them — Phase 5 connects them to file dialogs and
    the Excel backend.
    """

    browse_requested = Signal()
    create_requested = Signal()
    open_requested = Signal(str)

    _PLACEHOLDER = "No file linked"

    def __init__(self, initial_path: str = "") -> None:
        super().__init__()
        self.setProperty("role", "card")
        self._path = initial_path

        heading = QLabel("Linked spreadsheet")
        heading.setProperty("role", "secondary")

        self._path_label = QLabel(self._display_path())

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)

        self._browse_button = QPushButton("Browse…")
        self._browse_button.setProperty("variant", "secondary")
        self._browse_button.clicked.connect(self.browse_requested.emit)

        self._create_button = QPushButton("Create Template")
        self._create_button.setProperty("variant", "secondary")
        self._create_button.clicked.connect(self.create_requested.emit)

        self._open_button = QPushButton("Open in Excel")
        self._open_button.setProperty("variant", "secondary")
        self._open_button.clicked.connect(self._on_open_clicked)
        self._open_button.setEnabled(bool(self._path))

        for btn in (self._browse_button, self._create_button, self._open_button):
            button_layout.addWidget(btn)
        button_layout.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(self._path_label)
        layout.addWidget(button_row)

    def set_path(self, path: str) -> None:
        """Update the displayed path and enable/disable the Open button."""
        self._path = path
        self._path_label.setText(self._display_path())
        self._open_button.setEnabled(bool(path))

    def path_text(self) -> str:
        return self._path_label.text()

    def _display_path(self) -> str:
        return self._path or self._PLACEHOLDER

    def _on_open_clicked(self) -> None:
        if self._path:
            self.open_requested.emit(self._path)


from PySide6.QtWidgets import QCheckBox


class HeaderRow(QWidget):
    """Top header row: title + subtitle on the left, settings gear + dark-mode toggle on the right."""

    settings_clicked = Signal()
    dark_mode_toggled = Signal(bool)

    def __init__(self, title: str, subtitle: str, is_dark: bool = False) -> None:
        super().__init__()

        self._title = QLabel(title)
        self._title.setProperty("role", "heading")

        self._subtitle = QLabel(subtitle)
        self._subtitle.setProperty("role", "secondary")

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(2)
        left.addWidget(self._title)
        left.addWidget(self._subtitle)

        self._settings_button = QPushButton("⚙")
        self._settings_button.setFixedSize(32, 32)
        self._settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_button.setToolTip("Settings")
        self._settings_button.clicked.connect(self.settings_clicked.emit)

        self._dark_mode_toggle = QCheckBox("Dark mode")
        self._dark_mode_toggle.setChecked(is_dark)
        self._dark_mode_toggle.stateChanged.connect(self._on_toggle_changed)

        layout = QHBoxLayout(self)
        layout.addLayout(left)
        layout.addStretch(1)
        layout.addWidget(self._settings_button)
        layout.addWidget(self._dark_mode_toggle)

    def title_text(self) -> str:
        return self._title.text()

    def subtitle_text(self) -> str:
        return self._subtitle.text()

    def set_subtitle(self, text: str) -> None:
        self._subtitle.setText(text)

    def _on_toggle_changed(self, state: int) -> None:
        self.dark_mode_toggled.emit(state == Qt.CheckState.Checked.value)
