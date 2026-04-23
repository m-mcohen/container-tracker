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


from container_tracker.ui.theme import build_stylesheet


class TestBuildStylesheet:
    def test_returns_non_empty_string(self) -> None:
        assert len(build_stylesheet(LIGHT_PALETTE)) > 500  # sanity: it's a real stylesheet

    def test_contains_widget_base_rule(self) -> None:
        qss = build_stylesheet(LIGHT_PALETTE)
        assert "QWidget" in qss

    def test_contains_all_button_variants(self) -> None:
        qss = build_stylesheet(LIGHT_PALETTE)
        assert 'QPushButton[variant="primary"]' in qss
        assert 'QPushButton[variant="secondary"]' in qss
        assert 'QPushButton[variant="destructive"]' in qss

    def test_contains_button_hover_states(self) -> None:
        qss = build_stylesheet(LIGHT_PALETTE)
        assert 'QPushButton[variant="primary"]:hover' in qss
        assert 'QPushButton[variant="secondary"]:hover' in qss

    def test_contains_input_selectors(self) -> None:
        qss = build_stylesheet(LIGHT_PALETTE)
        assert "QLineEdit" in qss
        assert "QComboBox" in qss
        assert "QLineEdit:focus" in qss

    def test_contains_table_selectors(self) -> None:
        qss = build_stylesheet(LIGHT_PALETTE)
        assert "QTableView" in qss
        assert "QHeaderView::section" in qss

    def test_contains_card_role_selectors(self) -> None:
        qss = build_stylesheet(LIGHT_PALETTE)
        assert 'QFrame[role="card"]' in qss
        assert 'QFrame[role="stat-card"]' in qss

    def test_contains_activity_log_selector(self) -> None:
        qss = build_stylesheet(LIGHT_PALETTE)
        assert "QPlainTextEdit" in qss

    def test_light_palette_colors_are_embedded(self) -> None:
        qss = build_stylesheet(LIGHT_PALETTE)
        assert LIGHT_PALETTE["surface_base"] in qss          # #FAF8F3
        assert LIGHT_PALETTE["accent"] in qss                # #1E3A5F
        assert LIGHT_PALETTE["status_delayed"] in qss        # #B05A4D

    def test_dark_palette_colors_are_embedded(self) -> None:
        qss = build_stylesheet(DARK_PALETTE)
        assert DARK_PALETTE["surface_base"] in qss           # #15171C
        assert DARK_PALETTE["accent"] in qss                 # #6B9DD4
        assert DARK_PALETTE["status_delayed"] in qss         # #D48276

    def test_light_and_dark_produce_different_output(self) -> None:
        assert build_stylesheet(LIGHT_PALETTE) != build_stylesheet(DARK_PALETTE)

    def test_pure_red_is_not_present_in_light(self) -> None:
        """Spec §5.1: the v1.0.0 pure-red #D32F2F bug is fixed in v1.1.0."""
        qss = build_stylesheet(LIGHT_PALETTE)
        assert "#D32F2F" not in qss
        assert "#d32f2f" not in qss

    def test_cta_pill_radius_appears(self) -> None:
        """Primary CTA button must be pill-shaped (radius 19)."""
        from container_tracker.ui.theme import RADIUS
        qss = build_stylesheet(LIGHT_PALETTE)
        # The primary-button rule should reference the CTA pill radius.
        # Look for "19px" in the primary-button section specifically.
        primary_section_start = qss.find('QPushButton[variant="primary"]')
        primary_section_end = qss.find('}', primary_section_start)
        assert str(RADIUS["cta_pill"]) + "px" in qss[primary_section_start:primary_section_end]

    def test_font_family_embedded(self) -> None:
        from container_tracker.ui.theme import FONT_FAMILY_MONO, FONT_FAMILY_PRIMARY
        qss = build_stylesheet(LIGHT_PALETTE)
        # Segoe UI Variable should appear somewhere (on QWidget or body text).
        assert "Segoe UI" in qss
        # Mono font should appear on QPlainTextEdit.
        assert "Cascadia Code" in qss


class TestApplyTheme:
    """apply_theme mutates QApplication state, so we smoke-test with a real QApplication."""

    def test_apply_theme_runs_without_error_for_both_modes(self) -> None:
        import sys
        from PySide6.QtWidgets import QApplication
        from container_tracker.ui.theme import apply_theme

        # Construct QApplication if one doesn't exist (pytest may have skipped that).
        app = QApplication.instance() or QApplication(sys.argv)
        apply_theme(is_dark=False)
        light_qss = app.styleSheet()
        assert len(light_qss) > 500
        assert LIGHT_PALETTE["surface_base"] in light_qss

        apply_theme(is_dark=True)
        dark_qss = app.styleSheet()
        assert DARK_PALETTE["surface_base"] in dark_qss

        # Restore light for any downstream tests.
        apply_theme(is_dark=False)
