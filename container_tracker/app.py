"""pywebview entry point. Step 2: opens a window pointing at web/index.html.
Step 3 will swap the stub HTML for the ported mockup; Step 4 wires the bridge.
"""

from __future__ import annotations

import sys
from pathlib import Path

import webview

from container_tracker.bridge import Bridge
from container_tracker.core import config as ct_config
from container_tracker.core.constants import APP_NAME, __version__


def _web_root() -> Path:
    """Locate the bundled web/ directory.

    In a PyInstaller bundle (--add-data 'container_tracker/web;container_tracker/web')
    the assets land under ``sys._MEIPASS/container_tracker/web``. In dev they
    sit next to this file.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "container_tracker" / "web"
    return Path(__file__).parent / "web"


def main() -> None:
    # Run all v1 → v1.1 startup migrations before the UI touches anything.
    ct_config.boot()

    # Bridge exposes the Python API to JS. Step 4 ships dummy data; Step 5
    # wires real data through. The Bridge instance does not need a window
    # reference — if a later step needs window-level callbacks (native
    # dialogs etc.) that's a Step 6/7 concern.
    bridge = Bridge()

    debug = not getattr(sys, "frozen", False)

    webview.create_window(
        f"{APP_NAME} v{__version__}",
        url=str(_web_root() / "index.html"),
        width=1280,
        height=820,
        min_size=(1024, 720),
        js_api=bridge,
    )
    webview.start(debug=debug)


if __name__ == "__main__":
    main()
