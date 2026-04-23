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


from PySide6.QtWidgets import QHBoxLayout, QPushButton


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
