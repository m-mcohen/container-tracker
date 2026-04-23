from container_tracker.core.status import (
    StatusBucket,
    bucket_counts,
    compute_delay_days,
    normalize_status,
)


class TestNormalizeStatus:
    def test_sailing_variants(self) -> None:
        assert normalize_status("SAILING") == StatusBucket.SAILING
        assert normalize_status("sailing") == StatusBucket.SAILING
        assert normalize_status("EN_ROUTE") == StatusBucket.SAILING
        assert normalize_status("en_route") == StatusBucket.SAILING

    def test_arrived_variants(self) -> None:
        assert normalize_status("ARRIVED") == StatusBucket.ARRIVED
        assert normalize_status("DISCHARGED") == StatusBucket.ARRIVED
        assert normalize_status("DELIVERED") == StatusBucket.ARRIVED
        assert normalize_status("GATE_OUT") == StatusBucket.ARRIVED
        assert normalize_status("gate_out") == StatusBucket.ARRIVED

    def test_pending_variants(self) -> None:
        assert normalize_status("BOOKED") == StatusBucket.PENDING
        assert normalize_status("NEW") == StatusBucket.PENDING
        assert normalize_status("") == StatusBucket.PENDING

    def test_unknown(self) -> None:
        assert normalize_status("GARBAGE") == StatusBucket.UNKNOWN
        assert normalize_status("loaded-on-vessel") == StatusBucket.UNKNOWN


class TestComputeDelayDays:
    def test_on_time(self) -> None:
        assert compute_delay_days("2026-05-01", "2026-05-01") == 0

    def test_delayed(self) -> None:
        assert compute_delay_days("2026-05-01", "2026-05-04") == 3

    def test_early(self) -> None:
        assert compute_delay_days("2026-05-10", "2026-05-07") == -3

    def test_tolerates_iso_with_time(self) -> None:
        # ShipsGo sometimes returns ISO timestamps. Only the date portion matters.
        assert compute_delay_days("2026-05-01T00:00:00Z", "2026-05-03T14:20:00Z") == 2

    def test_missing_original_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            compute_delay_days("", "2026-05-01")

    def test_missing_current_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            compute_delay_days("2026-05-01", "")

    def test_unparseable_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            compute_delay_days("not-a-date", "2026-05-01")


class TestBucketCounts:
    def test_empty_db(self) -> None:
        assert bucket_counts({}) == {"total": 0, "sailing": 0, "arrived": 0, "delayed": 0}

    def test_mixed_db(self) -> None:
        db = {
            "AAAA0000001": {"status": "SAILING", "delay_days_int": 0},
            "AAAA0000002": {"status": "SAILING", "delay_days_int": 3},   # counts as delayed
            "AAAA0000003": {"status": "ARRIVED", "delay_days_int": 5},   # not delayed (arrived)
            "AAAA0000004": {"status": "DELIVERED", "delay_days_int": 0},
            "AAAA0000005": {"status": "", "delay_days_int": None},
        }
        assert bucket_counts(db) == {"total": 5, "sailing": 2, "arrived": 2, "delayed": 1}

    def test_delayed_requires_sailing(self) -> None:
        # Per spec decision: delay-while-sailing only. Arrived-with-delay is not actionable.
        db = {"X": {"status": "ARRIVED", "delay_days_int": 7}}
        assert bucket_counts(db)["delayed"] == 0

    def test_missing_delay_field_does_not_count(self) -> None:
        db = {"X": {"status": "SAILING"}}
        assert bucket_counts(db)["delayed"] == 0
