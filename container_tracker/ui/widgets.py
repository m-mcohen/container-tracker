"""Reusable UI widgets and utilities. At the end of Phase 1, only QtLogHandler lives here.

Later phases add: StatCard, UpdateBanner, ActivityLog, LinkedSpreadsheetCard.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal


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
