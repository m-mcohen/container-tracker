"""Unit tests for RefreshRunnable / AddTrackRunnable business logic."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from container_tracker.core.api import ShipsGoAuthError
from container_tracker.core.updates import UpdateInfo
from container_tracker.ui.runnables import (
    AddTrackRunnable,
    RefreshRunnable,
    UpdateCheckRunnable,
)


class TestRefreshRunnable:
    def test_successful_refresh_emits_completed_with_updated_db(self, qapp) -> None:
        client = MagicMock()
        client.list_shipments.return_value = [
            {
                "id": "ship_001",
                "container_number": "MSKU1234567",
                "status": "SAILING",
                "carrier": {"name": "MAERSK LINE"},
                "route": {
                    "port_of_loading": {"location": {"name": "Shanghai"}, "date_of_loading": "2026-04-01"},
                    "port_of_discharge": {
                        "location": {"name": "LA"},
                        "date_of_discharge": "2026-05-05",
                        "date_of_discharge_initial": "2026-05-01",
                    },
                    "transit_percentage": 42,
                },
            }
        ]
        # get_shipment returns the same shipment wrapped.
        client.get_shipment.return_value = {"shipment": client.list_shipments.return_value[0]}
        db = {"MSKU1234567": {"container_number": "MSKU1234567", "shipment_id": "ship_001"}}

        runnable = RefreshRunnable(client, db)
        received: list[dict[str, Any]] = []
        runnable.signals.completed.connect(received.append)
        runnable.run()

        assert received, "completed signal never emitted"
        new_db = received[0]
        assert "MSKU1234567" in new_db
        assert new_db["MSKU1234567"]["status"] == "SAILING"
        assert new_db["MSKU1234567"]["eta"] == "2026-05-05"

    def test_auth_error_emits_auth_error_signal(self, qapp) -> None:
        client = MagicMock()
        client.list_shipments.side_effect = ShipsGoAuthError("bad token")
        runnable = RefreshRunnable(client, {})
        auth_received: list[bool] = []
        failed_received: list[str] = []
        runnable.signals.auth_error.connect(lambda: auth_received.append(True))
        runnable.signals.failed.connect(failed_received.append)
        runnable.run()
        assert auth_received == [True]
        assert failed_received == []

    def test_generic_error_emits_failed(self, qapp) -> None:
        client = MagicMock()
        client.list_shipments.side_effect = RuntimeError("network unreachable")
        runnable = RefreshRunnable(client, {})
        failed: list[str] = []
        runnable.signals.failed.connect(failed.append)
        runnable.run()
        assert len(failed) == 1
        assert "network" in failed[0].lower()

    def test_empty_db_still_runs_cleanly(self, qapp) -> None:
        client = MagicMock()
        client.list_shipments.return_value = []
        runnable = RefreshRunnable(client, {})
        completed: list[dict[str, Any]] = []
        runnable.signals.completed.connect(completed.append)
        runnable.run()
        assert completed == [{}]


class TestAddTrackRunnable:
    def test_new_container_registered_and_refreshed(self, qapp) -> None:
        client = MagicMock()
        client.create_shipment.return_value = {"id": "ship_new"}
        client.get_shipment.return_value = {
            "shipment": {
                "id": "ship_new",
                "container_number": "MSKU9999999",
                "status": "BOOKED",
                "carrier": {"name": "MAERSK LINE"},
                "route": {},
            }
        }
        runnable = AddTrackRunnable(client, "MSKU9999999", "MAEU")
        completed: list[dict[str, Any]] = []
        runnable.signals.completed.connect(completed.append)
        runnable.run()
        assert len(completed) == 1
        record = completed[0]
        assert record["container_number"] == "MSKU9999999"
        assert record["shipment_id"] == "ship_new"

    def test_already_exists_emits_already_tracked(self, qapp) -> None:
        client = MagicMock()
        client.create_shipment.return_value = {"already_exists": True}
        runnable = AddTrackRunnable(client, "MSKU1234567", "MAEU")
        already: list[str] = []
        completed: list[dict[str, Any]] = []
        runnable.signals.already_tracked.connect(already.append)
        runnable.signals.completed.connect(completed.append)
        runnable.run()
        assert already == ["MSKU1234567"]
        assert completed == []

    def test_insufficient_credits_emits_no_credits(self, qapp) -> None:
        client = MagicMock()
        client.create_shipment.return_value = {"error": "NOT_ENOUGH_CREDITS"}
        runnable = AddTrackRunnable(client, "MSKU1234567", "MAEU")
        no_credits: list[bool] = []
        runnable.signals.no_credits.connect(lambda: no_credits.append(True))
        runnable.run()
        assert no_credits == [True]

    def test_auth_error_emits_auth_error(self, qapp) -> None:
        client = MagicMock()
        client.create_shipment.side_effect = ShipsGoAuthError("bad")
        runnable = AddTrackRunnable(client, "MSKU1234567", "MAEU")
        auth: list[bool] = []
        runnable.signals.auth_error.connect(lambda: auth.append(True))
        runnable.run()
        assert auth == [True]


class TestUpdateCheckRunnable:
    def test_newer_release_emits_update_available(self, qapp, monkeypatch) -> None:
        fake = UpdateInfo(version="1.2.0", html_url="https://github.com/m-mcohen/container-tracker/releases/v1.2.0")
        monkeypatch.setattr(
            "container_tracker.ui.runnables.check_for_update",
            lambda current_version, timeout=5.0: fake,
        )
        runnable = UpdateCheckRunnable(current_version="1.1.0")
        received: list[UpdateInfo] = []
        runnable.signals.update_available.connect(received.append)
        runnable.run()
        assert received == [fake]

    def test_no_update_emits_nothing(self, qapp, monkeypatch) -> None:
        monkeypatch.setattr(
            "container_tracker.ui.runnables.check_for_update",
            lambda current_version, timeout=5.0: None,
        )
        runnable = UpdateCheckRunnable(current_version="1.1.0")
        received: list[UpdateInfo] = []
        runnable.signals.update_available.connect(received.append)
        runnable.run()
        assert received == []

    def test_exception_fails_silently(self, qapp, monkeypatch) -> None:
        def boom(current_version: str, timeout: float = 5.0) -> None:
            raise RuntimeError("network dead")
        monkeypatch.setattr("container_tracker.ui.runnables.check_for_update", boom)
        runnable = UpdateCheckRunnable(current_version="1.1.0")
        received: list[UpdateInfo] = []
        runnable.signals.update_available.connect(received.append)
        # Must NOT raise; must NOT emit.
        runnable.run()
        assert received == []
