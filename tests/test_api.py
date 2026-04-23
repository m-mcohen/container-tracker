from container_tracker.core.api import CARRIER_NAMES, CARRIER_SCAC_MAP, resolve_scac


class TestResolveScac:
    def test_known_carrier_by_long_name(self) -> None:
        assert resolve_scac("MAERSK LINE") == "MAEU"
        assert resolve_scac("Hapag-Lloyd") == "HLCU"

    def test_case_and_whitespace_normalized(self) -> None:
        assert resolve_scac("  maersk  ") == "MAEU"

    def test_four_letter_code_passthrough(self) -> None:
        assert resolve_scac("MSCU") == "MSCU"

    def test_unknown_returns_upper_input(self) -> None:
        assert resolve_scac("NONSENSE") == "NONSENSE"


class TestCarrierMetadata:
    def test_scac_map_covers_named_carriers(self) -> None:
        # Every long name in CARRIER_NAMES (except "OTHER") resolves to a SCAC
        for name in CARRIER_NAMES:
            if name == "OTHER":
                continue
            assert resolve_scac(name) != "", f"{name} has no SCAC mapping"

    def test_all_scacs_are_four_letters(self) -> None:
        for scac in CARRIER_SCAC_MAP.values():
            assert len(scac) == 4 and scac.isalpha(), f"bad SCAC: {scac}"
