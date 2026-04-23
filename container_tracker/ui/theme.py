"""Design-system theme: palette, typography, spacing, radius + QSS generator.

Pure constants and pure functions. No Qt state mutation here — the caller
(usually __main__.py on startup, or MainWindow.toggle_dark_mode at runtime)
applies the generated stylesheet via QApplication.instance().setStyleSheet.
"""
from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────────
# Palettes
# ─────────────────────────────────────────────────────────────────────────

LIGHT_PALETTE: dict[str, str] = {
    "surface_base":    "#FAF8F3",  # warm bone — window background
    "surface_card":    "#FFFFFF",  # cards (outlined, used sparingly — dropdown popups etc.)
    "surface_subtle":  "#F1EDE4",  # log pane / table header (slightly darker than base)
    "border":          "#D8D2C4",  # card / divider border (warm neutral)
    "border_subtle":   "#E7E2D6",  # hairline separators
    "text_primary":    "#1C1B17",  # deep warm charcoal
    "text_secondary":  "#5A5850",  # mid warm gray
    "text_tertiary":   "#8F8B82",  # hint / caption
    "accent":          "#1E3A5F",  # mid-dark navy — primary brand
    "accent_hover":    "#2A4D7A",  # lighter navy for button hover
    "accent_subtle":   "#E8EEF5",  # very light navy wash — ghost button hover fill, banner bg
    "status_sailing":  "#4A7BA0",  # muted teal-blue
    "status_arrived":  "#5C8A5C",  # muted green
    "status_delayed":  "#B05A4D",  # muted rust (NOT pure red — v1.0.0 bug fixed here)
}

DARK_PALETTE: dict[str, str] = {
    "surface_base":    "#15171C",  # deep charcoal
    "surface_card":    "#1E2127",
    "surface_subtle":  "#191B20",
    "border":          "#383D48",  # nudged brighter so card edges stay visible
    "border_subtle":   "#2E323B",
    "text_primary":    "#F0EDE5",  # warm off-white
    "text_secondary":  "#A8A59D",
    "text_tertiary":   "#6E6C66",
    "accent":          "#6B9DD4",  # brightened navy for dark-mode contrast
    "accent_hover":    "#84B0E0",
    "accent_subtle":   "#1C2836",
    "status_sailing":  "#6B9DD4",
    "status_arrived":  "#7FA87F",
    "status_delayed":  "#D48276",
}


# ─────────────────────────────────────────────────────────────────────────
# Typography
# ─────────────────────────────────────────────────────────────────────────

# Font families use CSS-style fallback chains so QSS resolves the first
# available face. Segoe UI Variable ships with Windows 11; Segoe UI is the
# Win10 fallback. Cascadia Code ships with modern Windows; Consolas is the
# universal fallback.
FONT_FAMILY_PRIMARY = '"Segoe UI Variable", "Segoe UI"'
FONT_FAMILY_MONO = '"Cascadia Code", "Consolas"'


TYPOGRAPHY: dict[str, dict[str, str | int]] = {
    "display":    {"family": FONT_FAMILY_PRIMARY, "size": 28, "weight": "bold"},    # stat-card numbers
    "heading":    {"family": FONT_FAMILY_PRIMARY, "size": 18, "weight": "bold"},    # app title / section heading
    "subheading": {"family": FONT_FAMILY_PRIMARY, "size": 13, "weight": "bold"},    # CTA button text, dialog labels
    "body":       {"family": FONT_FAMILY_PRIMARY, "size": 12, "weight": "normal"},  # default
    "body_bold":  {"family": FONT_FAMILY_PRIMARY, "size": 12, "weight": "bold"},
    "caption":    {"family": FONT_FAMILY_PRIMARY, "size": 11, "weight": "normal"},
    "hint":       {"family": FONT_FAMILY_PRIMARY, "size": 10, "weight": "normal"},  # footer / inline help
    "mono":       {"family": FONT_FAMILY_MONO,    "size": 11, "weight": "normal"},  # activity log
}


# ─────────────────────────────────────────────────────────────────────────
# Spacing (px). Apply via SPACING[key], never ad-hoc numbers.
# ─────────────────────────────────────────────────────────────────────────

SPACING: dict[str, int] = {
    "xs":  4,
    "sm":  8,
    "md":  12,
    "lg":  16,
    "xl":  24,
    "xxl": 32,
}


# ─────────────────────────────────────────────────────────────────────────
# Corner radius (px).
# ─────────────────────────────────────────────────────────────────────────

RADIUS: dict[str, int] = {
    "input":    8,    # entries, combo boxes
    "btn":      8,    # secondary / ghost buttons
    "card":    12,    # outlined cards
    "cta_pill": 19,   # primary CTAs (38px height / 2)
}
