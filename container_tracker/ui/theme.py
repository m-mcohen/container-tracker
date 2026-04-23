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


# ─────────────────────────────────────────────────────────────────────────
# QSS generator
# ─────────────────────────────────────────────────────────────────────────


def build_stylesheet(palette: dict[str, str]) -> str:
    """Return a complete Qt stylesheet built from `palette`.

    Theme swap is done by calling this function with a different palette and
    passing the result to `QApplication.instance().setStyleSheet(...)`. No
    per-widget styling; everything flows through the app-level stylesheet.
    """
    p = palette
    r = RADIUS
    s = SPACING
    fp = FONT_FAMILY_PRIMARY
    fm = FONT_FAMILY_MONO

    return f"""
/* ─── Base ─────────────────────────────────────────────────────────── */
QWidget {{
    background-color: {p["surface_base"]};
    color: {p["text_primary"]};
    font-family: {fp};
    font-size: {TYPOGRAPHY["body"]["size"]}pt;
}}

QMainWindow, QDialog {{
    background-color: {p["surface_base"]};
}}

/* ─── Labels ───────────────────────────────────────────────────────── */
QLabel {{
    background-color: transparent;
    color: {p["text_primary"]};
}}

QLabel[role="secondary"] {{
    color: {p["text_secondary"]};
}}

QLabel[role="hint"] {{
    color: {p["text_tertiary"]};
    font-size: {TYPOGRAPHY["hint"]["size"]}pt;
}}

QLabel[role="heading"] {{
    font-size: {TYPOGRAPHY["heading"]["size"]}pt;
    font-weight: bold;
}}

QLabel[role="display"] {{
    font-size: {TYPOGRAPHY["display"]["size"]}pt;
    font-weight: bold;
}}

/* Stat-card number colors — role-based tint applied to the number QLabel. */
QLabel[statRole="sailing"] {{
    color: {p["status_sailing"]};
}}

QLabel[statRole="arrived"] {{
    color: {p["status_arrived"]};
}}

QLabel[statRole="delayed"] {{
    color: {p["status_delayed"]};
}}

/* ─── Buttons ──────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {p["surface_base"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: {r["btn"]}px;
    padding: {s["xs"]}px {s["md"]}px;
    font-family: {fp};
    font-size: {TYPOGRAPHY["body"]["size"]}pt;
    min-height: 28px;
}}

QPushButton:hover {{
    background-color: {p["surface_subtle"]};
}}

QPushButton:disabled {{
    color: {p["text_tertiary"]};
    border-color: {p["border_subtle"]};
}}

/* Primary CTA — solid accent fill, pill-shaped */
QPushButton[variant="primary"] {{
    background-color: {p["accent"]};
    color: #FFFFFF;
    border: 1px solid {p["accent"]};
    border-radius: {r["cta_pill"]}px;
    padding: {s["sm"]}px {s["xl"]}px;
    font-size: {TYPOGRAPHY["subheading"]["size"]}pt;
    font-weight: bold;
    min-height: 38px;
}}

QPushButton[variant="primary"]:hover {{
    background-color: {p["accent_hover"]};
    border-color: {p["accent_hover"]};
}}

QPushButton[variant="primary"]:disabled {{
    background-color: {p["text_tertiary"]};
    border-color: {p["text_tertiary"]};
    color: #FFFFFF;
}}

/* Secondary / ghost — transparent bg, accent border + text */
QPushButton[variant="secondary"] {{
    background-color: transparent;
    color: {p["accent"]};
    border: 1px solid {p["accent"]};
    border-radius: {r["btn"]}px;
    padding: {s["xs"]}px {s["md"]}px;
    font-weight: bold;
}}

QPushButton[variant="secondary"]:hover {{
    background-color: {p["accent_subtle"]};
}}

/* Destructive — muted rust fill, white text, 8px corners (not pill) */
QPushButton[variant="destructive"] {{
    background-color: {p["status_delayed"]};
    color: #FFFFFF;
    border: 1px solid {p["status_delayed"]};
    border-radius: {r["btn"]}px;
    padding: {s["xs"]}px {s["md"]}px;
    font-weight: bold;
}}

QPushButton[variant="destructive"]:hover {{
    /* Slightly darker on hover via CSS-like technique: overlay accent_hover is navy
       and wrong here; keep the rust but lift with a subtle border tint. */
    background-color: {p["status_delayed"]};
    border-color: {p["accent_hover"]};
}}

/* ─── Inputs ───────────────────────────────────────────────────────── */
QLineEdit, QComboBox {{
    background-color: {p["surface_base"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: {r["input"]}px;
    padding: {s["xs"]}px {s["sm"]}px;
    selection-background-color: {p["accent_subtle"]};
    selection-color: {p["text_primary"]};
    min-height: 28px;
}}

QLineEdit:focus, QComboBox:focus {{
    border-color: {p["accent"]};
}}

QLineEdit:disabled, QComboBox:disabled {{
    color: {p["text_tertiary"]};
    border-color: {p["border_subtle"]};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {p["surface_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    selection-background-color: {p["accent_subtle"]};
    selection-color: {p["text_primary"]};
}}

/* ─── Cards ────────────────────────────────────────────────────────── */
QFrame[role="card"] {{
    background-color: transparent;
    border: 1px solid {p["border"]};
    border-radius: {r["card"]}px;
    padding: {s["lg"]}px;
}}

QFrame[role="stat-card"] {{
    background-color: transparent;
    border: 1px solid {p["border"]};
    border-radius: {r["card"]}px;
    padding: {s["md"]}px {s["lg"]}px;
}}

/* ─── Table ────────────────────────────────────────────────────────── */
QTableView {{
    background-color: {p["surface_base"]};
    alternate-background-color: {p["surface_base"]};
    color: {p["text_primary"]};
    gridline-color: {p["border_subtle"]};
    border: 1px solid {p["border_subtle"]};
    selection-background-color: {p["accent_subtle"]};
    selection-color: {p["text_primary"]};
}}

QHeaderView::section {{
    background-color: {p["surface_subtle"]};
    color: {p["text_secondary"]};
    border: none;
    border-bottom: 1px solid {p["border"]};
    padding: {s["sm"]}px {s["md"]}px;
    font-weight: bold;
}}

QTableView::item {{
    padding: {s["xs"]}px {s["sm"]}px;
    border: none;
    border-bottom: 1px solid {p["border_subtle"]};
}}

/* ─── Activity log / plain text ────────────────────────────────────── */
QPlainTextEdit, QTextEdit {{
    background-color: {p["surface_subtle"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border_subtle"]};
    border-radius: {r["btn"]}px;
    font-family: {fm};
    font-size: {TYPOGRAPHY["mono"]["size"]}pt;
    padding: {s["sm"]}px;
}}

/* ─── Scrollbars (minimal, neutral) ────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {p["border"]};
    border-radius: 5px;
    min-height: 24px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: transparent;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}

QScrollBar::handle:horizontal {{
    background: {p["border"]};
    border-radius: 5px;
    min-width: 24px;
}}

/* ─── Menus ────────────────────────────────────────────────────────── */
QMenu {{
    background-color: {p["surface_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: {r["btn"]}px;
    padding: {s["xs"]}px 0;
}}

QMenu::item:selected {{
    background-color: {p["accent_subtle"]};
}}

/* ─── Tool-tip ─────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {p["surface_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    padding: {s["xs"]}px {s["sm"]}px;
}}
"""


# ─────────────────────────────────────────────────────────────────────────
# Convenience: apply a theme to the running QApplication
# ─────────────────────────────────────────────────────────────────────────


def apply_theme(is_dark: bool) -> None:
    """Regenerate the full stylesheet from the appropriate palette and apply it.

    Requires a running `QApplication`. Raises `RuntimeError` if none exists.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        raise RuntimeError(
            "apply_theme requires a running QApplication. Construct one first."
        )
    palette = DARK_PALETTE if is_dark else LIGHT_PALETTE
    # QApplication.instance() is typed as QCoreApplication | None; setStyleSheet
    # lives on QApplication. Runtime guarantee: __main__ constructs a QApplication,
    # so narrowing via an isinstance check would be boilerplate. Ignore the attr.
    app.setStyleSheet(build_stylesheet(palette))  # type: ignore[attr-defined]
