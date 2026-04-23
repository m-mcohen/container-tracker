import pytest

from container_tracker.ui.theme import DARK_PALETTE, LIGHT_PALETTE


_REQUIRED_PALETTE_KEYS = {
    "surface_base", "surface_card", "surface_subtle",
    "border", "border_subtle",
    "text_primary", "text_secondary", "text_tertiary",
    "accent", "accent_hover", "accent_subtle",
    "status_sailing", "status_arrived", "status_delayed",
}


class TestPalettes:
    @pytest.mark.parametrize("palette_name,palette", [
        ("LIGHT_PALETTE", LIGHT_PALETTE),
        ("DARK_PALETTE", DARK_PALETTE),
    ])
    def test_palette_has_all_required_keys(self, palette_name: str, palette: dict[str, str]) -> None:
        missing = _REQUIRED_PALETTE_KEYS - set(palette.keys())
        assert not missing, f"{palette_name} missing keys: {missing}"

    @pytest.mark.parametrize("palette_name,palette", [
        ("LIGHT_PALETTE", LIGHT_PALETTE),
        ("DARK_PALETTE", DARK_PALETTE),
    ])
    def test_palette_values_are_valid_hex(self, palette_name: str, palette: dict[str, str]) -> None:
        import re
        hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
        for key, value in palette.items():
            assert hex_pattern.match(value), (
                f"{palette_name}[{key!r}] = {value!r} is not a valid 6-digit hex color"
            )

    def test_light_delayed_is_muted_rust_not_pure_red(self) -> None:
        """Spec §5.1 treats pure red #D32F2F as a v1.0.0 bug; v1.1.0 uses muted rust."""
        assert LIGHT_PALETTE["status_delayed"].upper() != "#D32F2F"
        # Spec requires specifically muted rust #B05A4D in light mode.
        assert LIGHT_PALETTE["status_delayed"].upper() == "#B05A4D"

    def test_palettes_differ(self) -> None:
        """Sanity: dark mode is actually different from light mode."""
        assert LIGHT_PALETTE["surface_base"] != DARK_PALETTE["surface_base"]
        assert LIGHT_PALETTE["text_primary"] != DARK_PALETTE["text_primary"]


from container_tracker.ui.theme import (
    FONT_FAMILY_MONO,
    FONT_FAMILY_PRIMARY,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)


class TestTypography:
    def test_required_keys(self) -> None:
        required = {"display", "heading", "subheading", "body", "body_bold",
                    "caption", "hint", "mono"}
        assert required <= set(TYPOGRAPHY.keys()), (
            f"missing: {required - set(TYPOGRAPHY.keys())}"
        )

    def test_specific_sizes_match_spec(self) -> None:
        assert TYPOGRAPHY["display"]["size"] == 28
        assert TYPOGRAPHY["heading"]["size"] == 18
        assert TYPOGRAPHY["subheading"]["size"] == 13
        assert TYPOGRAPHY["body"]["size"] == 12
        assert TYPOGRAPHY["caption"]["size"] == 11
        assert TYPOGRAPHY["hint"]["size"] == 10
        assert TYPOGRAPHY["mono"]["size"] == 11

    def test_display_is_bold(self) -> None:
        assert TYPOGRAPHY["display"]["weight"] == "bold"

    def test_mono_uses_mono_family(self) -> None:
        assert TYPOGRAPHY["mono"]["family"] == FONT_FAMILY_MONO

    def test_body_uses_primary_family(self) -> None:
        assert TYPOGRAPHY["body"]["family"] == FONT_FAMILY_PRIMARY

    def test_primary_family_is_segoe(self) -> None:
        # "Segoe UI Variable, Segoe UI" — primary, then fallback for Win10.
        assert "Segoe UI" in FONT_FAMILY_PRIMARY

    def test_mono_family_is_cascadia(self) -> None:
        # "Cascadia Code, Consolas" — fallback chain.
        assert "Cascadia Code" in FONT_FAMILY_MONO
        assert "Consolas" in FONT_FAMILY_MONO


class TestSpacing:
    def test_scale_values(self) -> None:
        assert SPACING == {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}


class TestRadius:
    def test_values(self) -> None:
        assert RADIUS == {"input": 8, "btn": 8, "card": 12, "cta_pill": 19}
