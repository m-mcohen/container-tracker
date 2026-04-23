"""Hardcoded sample tracking data for the Phase 3 visual.

Phase 5 replaces this with real data from core.persistence.load_tracking_data().
Kept as a separate module so it's easy to delete later.
"""
from __future__ import annotations

from typing import Any


def sample_tracking_db() -> dict[str, dict[str, Any]]:
    """Return a sample db with 10 containers across all status buckets."""
    records: list[dict[str, Any]] = [
        {
            "container_number": "MSKU1234567", "carrier": "MAERSK LINE",
            "status": "SAILING", "original_eta": "2026-05-01", "eta": "2026-05-05",
            "delay_days": "+4 days", "delay_days_int": 4,
            "pol": "Shanghai, China", "pod": "Los Angeles, USA",
            "vessel": "MV SEA PIONEER", "transit_pct": 42,
        },
        {
            "container_number": "MSKU2222222", "carrier": "MAERSK LINE",
            "status": "SAILING", "original_eta": "2026-04-28", "eta": "2026-04-28",
            "delay_days": "On time", "delay_days_int": 0,
            "pol": "Qingdao, China", "pod": "Oakland, USA",
            "vessel": "MV CARIBOU", "transit_pct": 65,
        },
        {
            "container_number": "CMAU7654321", "carrier": "CMA CGM",
            "status": "ARRIVED", "original_eta": "2026-03-20", "eta": "2026-03-20",
            "delay_days": "On time", "delay_days_int": 0,
            "pol": "Ningbo, China", "pod": "Long Beach, USA",
            "vessel": "MV PACIFIC STAR", "transit_pct": 100,
        },
        {
            "container_number": "CMAU3333333", "carrier": "CMA CGM",
            "status": "DISCHARGED", "original_eta": "2026-04-01", "eta": "2026-04-03",
            "delay_days": "+2 days", "delay_days_int": 2,
            "pol": "Hong Kong", "pod": "Seattle, USA",
            "vessel": "MV JADE", "transit_pct": 100,
        },
        {
            "container_number": "MSCU1111222", "carrier": "MSC",
            "status": "SAILING", "original_eta": "2026-05-10", "eta": "2026-05-10",
            "delay_days": "On time", "delay_days_int": 0,
            "pol": "Rotterdam, Netherlands", "pod": "New York, USA",
            "vessel": "MV ATLANTIC", "transit_pct": 22,
        },
        {
            "container_number": "HLCU4444555", "carrier": "HAPAG LLOYD",
            "status": "BOOKED", "original_eta": "", "eta": "",
            "delay_days": "", "delay_days_int": None,
            "pol": "", "pod": "",
            "vessel": "", "transit_pct": "",
        },
        {
            "container_number": "EGLV5555666", "carrier": "EVERGREEN",
            "status": "SAILING", "original_eta": "2026-04-15", "eta": "2026-04-22",
            "delay_days": "+7 days", "delay_days_int": 7,
            "pol": "Kaohsiung, Taiwan", "pod": "Los Angeles, USA",
            "vessel": "MV EVER GIVEN", "transit_pct": 58,
        },
        {
            "container_number": "COSU6666777", "carrier": "COSCO",
            "status": "DELIVERED", "original_eta": "2026-02-28", "eta": "2026-03-02",
            "delay_days": "+2 days", "delay_days_int": 2,
            "pol": "Shanghai, China", "pod": "Savannah, USA",
            "vessel": "MV ORIENT", "transit_pct": 100,
        },
        {
            "container_number": "ONEY7777888", "carrier": "ONE",
            "status": "SAILING", "original_eta": "2026-05-03", "eta": "2026-05-01",
            "delay_days": "-2 days (early)", "delay_days_int": -2,
            "pol": "Tokyo, Japan", "pod": "Los Angeles, USA",
            "vessel": "MV SAKURA", "transit_pct": 88,
        },
        {
            "container_number": "ZIMU8888999", "carrier": "ZIM",
            "status": "GATE_OUT", "original_eta": "2026-03-10", "eta": "2026-03-10",
            "delay_days": "On time", "delay_days_int": 0,
            "pol": "Haifa, Israel", "pod": "New York, USA",
            "vessel": "MV ZIM NORFOLK", "transit_pct": 100,
        },
    ]
    return {r["container_number"]: r for r in records}
