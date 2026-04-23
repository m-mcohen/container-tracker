"""Main application window.

Owns application state per spec §3.3: config dict, is_dark flag, and in later
phases the tracking-data dict + ShipsGoClient. Phase 2 adds the theme hooks;
Phase 3 will add actual layout (stat cards, table, activity log, etc.).
"""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QSize
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow

from container_tracker.__version__ import __version__
from container_tracker.ui.theme import apply_theme


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self._config = config
        self._is_dark: bool = bool(config.get("dark_mode", False))

        self.setWindowTitle(f"Container Tracker v{__version__}")
        self.resize(QSize(1100, 720))

        logger.info("MainWindow constructed (is_dark=%s)", self._is_dark)

    @property
    def is_dark(self) -> bool:
        return self._is_dark

    def toggle_dark_mode(self) -> None:
        """Flip the theme, regenerate the app-level stylesheet, persist to config.

        No UI trigger wires into this yet — the header's dark-mode switch is
        built in Phase 3 and will call this method.
        """
        self._is_dark = not self._is_dark
        apply_theme(is_dark=self._is_dark)
        self._config["dark_mode"] = self._is_dark
        logger.info("dark mode toggled → %s", self._is_dark)

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        logger.info("MainWindow shown")
        super().showEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        logger.info("MainWindow closing")
        super().closeEvent(event)
