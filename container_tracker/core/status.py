"""Status normalization, delay computation, and bucket counts.

Pure logic. No Qt, no I/O, no network.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class StatusBucket(str, Enum):
    SAILING = "SAILING"
    ARRIVED = "ARRIVED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"


_SAILING_TOKENS = {"SAILING", "EN_ROUTE"}
_ARRIVED_TOKENS = {"ARRIVED", "DISCHARGED", "DELIVERED", "GATE_OUT"}
_PENDING_TOKENS = {"BOOKED", "NEW", ""}


def normalize_status(raw: str) -> StatusBucket:
    """Map a raw ShipsGo status string to a StatusBucket.

    Matching is case-insensitive; whitespace is ignored.
    Unrecognized values return StatusBucket.UNKNOWN.
    """
    key = (raw or "").strip().upper()
    if key in _SAILING_TOKENS:
        return StatusBucket.SAILING
    if key in _ARRIVED_TOKENS:
        return StatusBucket.ARRIVED
    if key in _PENDING_TOKENS:
        return StatusBucket.PENDING
    return StatusBucket.UNKNOWN


def compute_delay_days(original_eta: str, current_eta: str) -> int:
    """Days of delay between original and current ETA. Positive = delayed.

    Accepts either plain `YYYY-MM-DD` or ISO timestamps; only the date portion
    is used. Raises ValueError if either input is missing or unparseable.
    """
    if not original_eta or not current_eta:
        raise ValueError("compute_delay_days requires both original and current ETA")
    original = _parse_date(original_eta)
    current = _parse_date(current_eta)
    return (current - original).days


def _parse_date(value: str) -> datetime:
    date_part = str(value).split("T", 1)[0]
    return datetime.strptime(date_part, "%Y-%m-%d")


def bucket_counts(db: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    """Return {"total", "sailing", "arrived", "delayed"} counts for the tracking DB.

    Delayed is defined as: status bucket == SAILING AND delay_days_int > 0.
    Records missing delay_days_int do not count as delayed.
    """
    total = len(db)
    sailing = 0
    arrived = 0
    delayed = 0
    for record in db.values():
        bucket = normalize_status(str(record.get("status", "")))
        if bucket == StatusBucket.SAILING:
            sailing += 1
            delay = record.get("delay_days_int")
            if isinstance(delay, int) and delay > 0:
                delayed += 1
        elif bucket == StatusBucket.ARRIVED:
            arrived += 1
    return {"total": total, "sailing": sailing, "arrived": arrived, "delayed": delayed}
