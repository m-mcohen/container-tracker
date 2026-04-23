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
