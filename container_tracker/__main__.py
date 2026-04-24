"""Container Tracker entry point.

Run with: ``python -m container_tracker``. PyInstaller's `.spec` points at
this same module. Ownership of QApplication lifetime lives here.

At end of Phase 1 this does NOT construct a window — it bootstraps the
application, logs a startup line, and exits. Windows come in Checkpoint C.
"""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from container_tracker.__version__ import __version__
from container_tracker.core.persistence import (
    get_api_token,
    is_first_run,
    load_config,
    log_path,
)
from container_tracker.ui.widgets import QtLogHandler


_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def _configure_logging() -> QtLogHandler:
    """Attach FileHandler + QtLogHandler to the root logger. Returns the QtLogHandler.

    Third-party library noise (requests, urllib3) is suppressed at WARNING.
    This function is idempotent-safe to call once; do not call twice.
    """
    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = logging.FileHandler(log_path(), encoding="utf-8")
    file_handler.setFormatter(formatter)

    qt_handler = QtLogHandler()
    qt_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(qt_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    return qt_handler


def main() -> int:
    qt_handler = _configure_logging()
    logger = logging.getLogger(__name__)

    app = QApplication(sys.argv)
    app.setApplicationName("Container Tracker")
    app.setOrganizationName("Michael Cohen")

    logger.info("Container Tracker v%s starting", __version__)

    config = load_config()
    logger.info(
        "config loaded: company=%r, excel_path=%r, dark_mode=%s",
        config.get("company_name"),
        config.get("excel_path"),
        config.get("dark_mode"),
    )

    # Apply the theme BEFORE any widget is constructed so dialogs inherit it.
    from container_tracker.ui.theme import apply_theme
    apply_theme(is_dark=bool(config.get("dark_mode", False)))

    first_run = is_first_run(config)
    api_token_present = bool(get_api_token())
    logger.info("first-run=%s, api-token-present=%s", first_run, api_token_present)

    if first_run:
        logger.info("First run — showing Welcome dialog")
        from container_tracker.core.persistence import save_config, set_api_token
        from container_tracker.ui.dialogs import SetupDialog
        dialog = SetupDialog(mode="welcome")
        result = dialog.exec()
        if result != dialog.DialogCode.Accepted:
            # User closed via × (which triggered QApplication.quit via closeEvent)
            # or some other reject path. Either way, don't show the main window.
            logger.info("user cancelled first-run setup; exiting")
            return 0
        values = dialog.get_values()
        config["company_name"] = values["company"] or ""
        config["contact_email"] = values["email"] or ""
        save_config(config)
        if values["api_key"]:
            set_api_token(values["api_key"])
        logger.info(
            "Welcome-save complete: company=%r, email=%r, api-token-present=%s",
            values["company"], values["email"], bool(values["api_key"]),
        )

    from container_tracker.ui.main_window import MainWindow
    window = MainWindow(config, qt_handler)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
