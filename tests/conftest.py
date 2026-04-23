"""Shared pytest fixtures for the Container Tracker test suite."""
from __future__ import annotations

import sys
from typing import Iterator

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> Iterator[QApplication]:
    """Session-scoped QApplication. One instance shared by all widget/model tests."""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app  # type: ignore[misc]
    # No teardown — pytest-qt-style session lifetime.
