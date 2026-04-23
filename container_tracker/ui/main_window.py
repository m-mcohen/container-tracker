"""Main application window.

At end of Phase 1 this is an empty QMainWindow with a title and an initial
size. Phase 3 adds header, stat cards, table, activity log, and footer.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QSize
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow

from container_tracker.__version__ import __version__


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Container Tracker v{__version__}")
        self.resize(QSize(1100, 720))
        logger.info("MainWindow constructed")

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        logger.info("MainWindow shown")
        super().showEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        logger.info("MainWindow closing")
        super().closeEvent(event)
