# Phase 2 — Theme + QSS Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the design-system theme module — palette, typography, spacing, radius constants and a QSS generator — plus wire it into `MainWindow` so the window renders with the navy-on-warm-bone palette (or its dark-mode equivalent), and ship a standalone theme preview harness for visual verification of every styled widget in both modes.

**Architecture:** Pure Python constants + a `build_stylesheet(palette) -> str` pure function in `container_tracker/ui/theme.py`. Theme toggle regenerates the full stylesheet from a palette dict and applies it via `QApplication.instance().setStyleSheet(...)` (per spec §5.1 decision — no per-widget `setStyleSheet`, no QSS property-selector theme hack). `MainWindow` owns `is_dark` state per spec §3.3 and exposes `toggle_dark_mode()`, but Phase 2 does NOT add a UI trigger (that arrives with the header row in Phase 3). A separate preview module `container_tracker/ui/theme_preview.py` renders every styled widget for hand-verification.

**Tech Stack:** Python 3.11+, PySide6 ≥ 6.6, pytest (no new deps beyond Phase 1).

**Spec:** [2026-04-23-pyside6-migration-design.md §5.1](../specs/2026-04-23-pyside6-migration-design.md)

---

## Checkpoint structure

Phase 2 has **two internal checkpoints**. Within a phase, autonomous cadence — agent verifies after each STOP and dispatches the next checkpoint without user review.

- **Checkpoint A** (Tasks 1–4): `ui/theme.py` with palette/typography/spacing/radius constants, `build_stylesheet`, `apply_theme`, and unit tests asserting the stylesheet contains expected selectors and color values. `mypy --strict` clean. `pytest` green.
- **Checkpoint B** (Tasks 5–8): `MainWindow` accepts `config`, applies theme on construction, owns `is_dark`, exposes `toggle_dark_mode()`; `__main__.py` wires it together; theme-preview harness exists and renders both modes.

---

## File Structure

Files created by end of Phase 2:

```
container_tracker/
  ui/
    theme.py            # LIGHT_PALETTE, DARK_PALETTE, TYPOGRAPHY, SPACING, RADIUS, build_stylesheet, apply_theme
    theme_preview.py    # standalone `python -m container_tracker.ui.theme_preview` — visual harness

tests/
  test_theme.py         # unit tests for palette completeness and build_stylesheet output
```

Files modified by Phase 2:

```
container_tracker/
  __main__.py           # apply_theme(config["dark_mode"]) BEFORE MainWindow construction; pass config to MainWindow
  ui/main_window.py     # accept `config: dict` arg; own `_is_dark`; add `toggle_dark_mode()` (no UI trigger yet)
```

Files untouched by Phase 2:

```
container_tracker/core/**        # backend is stable from Phase 1
container_tracker/ui/widgets.py  # QtLogHandler only; ActivityLog comes later
container_tracker_gui.py         # still alive until Phase 5
```

**Working directory:** `C:/Users/emine/OneDrive/Documents/Claude/container_tracking_build`

**Standing conventions (from Phase 1):**
- `mypy --strict container_tracker` (expanded scope) must stay clean.
- One commit per task.
- Never touch `container_tracker_gui.py`.
- Never use `--no-verify`.

---

## Task 1: Palette constants in `ui/theme.py`

**Files:**
- Create: `container_tracker/ui/theme.py`
- Create: `tests/test_theme.py`

Reference: spec §5.1. The exact hex values come from the spec; the monolith's `container_tracker_gui.py:53-84` has them too (identical).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_theme.py`:

```python
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
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_theme.py -v`
Expected: `ModuleNotFoundError: No module named 'container_tracker.ui.theme'`

- [ ] **Step 3: Implement the palette module**

Create `container_tracker/ui/theme.py`:

```python
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
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `pytest tests/test_theme.py -v`
Expected: 8 tests pass (2 × 2 parametrized + 2 standalone).

- [ ] **Step 5: Commit**

```bash
git add container_tracker/ui/theme.py tests/test_theme.py
git commit -m "theme: add LIGHT_PALETTE and DARK_PALETTE with completeness tests"
```

---

## Task 2: Typography, spacing, radius constants

**Files:**
- Modify: `container_tracker/ui/theme.py`
- Modify: `tests/test_theme.py`

- [ ] **Step 1: Append failing tests to `tests/test_theme.py`**

```python
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
```

- [ ] **Step 2: Run tests, confirm the new ones fail**

Run: `pytest tests/test_theme.py -v`
Expected: the 8 Task-1 tests still pass; the new tests fail with ImportError.

- [ ] **Step 3: Append constants to `container_tracker/ui/theme.py`**

Append below the existing palette definitions:

```python
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
```

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_theme.py -v`
Expected: all tests pass (8 from Task 1 + ~10 new).

- [ ] **Step 5: Commit**

```bash
git add container_tracker/ui/theme.py tests/test_theme.py
git commit -m "theme: add TYPOGRAPHY, SPACING, RADIUS constants with tests"
```

---

## Task 3: `build_stylesheet(palette)` QSS generator

**Files:**
- Modify: `container_tracker/ui/theme.py`
- Modify: `tests/test_theme.py`

This is the heart of Phase 2. The QSS generator takes a palette dict and produces a string covering:
- `QWidget` background and default foreground
- `QMainWindow`, `QDialog` — same as QWidget
- `QPushButton[variant="primary"]` — solid accent fill, pill shape (radius = `RADIUS["cta_pill"]`)
- `QPushButton[variant="secondary"]` — transparent bg, accent border, accent text; hover fills with accent_subtle
- `QPushButton[variant="destructive"]` — solid `status_delayed` fill
- `QLineEdit`, `QComboBox` — outlined input, border on focus
- `QTableView`, `QHeaderView::section` — subtle table, subtle header
- `QFrame[role="card"]` — outlined card, transparent fill
- `QFrame[role="stat-card"]` — same shape, used by the 4 stat cards
- `QPlainTextEdit` — activity log (mono font, subtle bg)

- [ ] **Step 1: Append failing tests to `tests/test_theme.py`**

```python
from container_tracker.ui.theme import DARK_PALETTE, LIGHT_PALETTE, build_stylesheet


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
```

- [ ] **Step 2: Run tests, confirm the new ones fail**

Run: `pytest tests/test_theme.py -v`
Expected: Task 1 + 2 tests still pass; new `TestBuildStylesheet` tests fail with ImportError.

- [ ] **Step 3: Append the QSS generator to `container_tracker/ui/theme.py`**

Append below the existing constants:

```python
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
```

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_theme.py -v`
Expected: all theme tests pass (8 from Task 1 + ~10 from Task 2 + 14 from Task 3 = ~32).

- [ ] **Step 5: Confirm mypy strict is still clean**

Run: `mypy --strict container_tracker`
Expected: `Success: no issues found in N source files` (N = 13 or 14 depending on whether theme.py is picked up).

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/theme.py tests/test_theme.py
git commit -m "theme: implement build_stylesheet QSS generator covering all widgets"
```

---

## Task 4: `apply_theme(is_dark)` convenience

**Files:**
- Modify: `container_tracker/ui/theme.py`
- Modify: `tests/test_theme.py`

This is a 3-line convenience that chooses a palette based on a bool and applies the stylesheet. Keeps callers from repeating the ternary.

- [ ] **Step 1: Append failing test**

Append to `tests/test_theme.py`:

```python
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
```

- [ ] **Step 2: Run test, confirm it fails**

Run: `pytest tests/test_theme.py::TestApplyTheme -v`
Expected: `ImportError: cannot import name 'apply_theme' from 'container_tracker.ui.theme'`

- [ ] **Step 3: Append `apply_theme` to `container_tracker/ui/theme.py`**

```python
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
    app.setStyleSheet(build_stylesheet(palette))
```

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_theme.py -v`
Expected: all tests pass.

- [ ] **Step 5: Run the full suite + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all Phase 1 + Phase 2 tests pass; mypy clean.

- [ ] **Step 6: Commit**

```bash
git add container_tracker/ui/theme.py tests/test_theme.py
git commit -m "theme: add apply_theme(is_dark) convenience atop QApplication.setStyleSheet"
```

---

## CHECKPOINT A — STOP

**What's now true:**
- `container_tracker/ui/theme.py` defines palettes, typography, spacing, radius, `build_stylesheet`, `apply_theme`.
- Tests exhaustively verify palette completeness, valid hex, spec-required selectors and palette values in generated QSS, light-vs-dark divergence, and the muted-rust-not-pure-red bug fix.
- `mypy --strict container_tracker` clean.
- `MainWindow` is untouched — it still renders with the default Qt style. Integration comes in Checkpoint B.

**Autonomous cadence:** verify, then dispatch Checkpoint B without pausing.

---

## Task 5: MainWindow accepts `config` and owns `is_dark`

**Files:**
- Modify: `container_tracker/ui/main_window.py`

The Phase 1 version was `MainWindow()` no-args. Phase 2 introduces a `config: dict[str, Any]` constructor arg because MainWindow now owns theme state (and will own more state in later phases). `toggle_dark_mode()` is defined but has no UI trigger yet — that's fine.

- [ ] **Step 1: Replace `container_tracker/ui/main_window.py` with:**

```python
"""Main application window.

Owns application state per spec §3.3: config dict, is_dark flag, and in later
phases the tracking-data dict + ShipsGoClient. Phase 2 adds the theme hooks;
Phase 3 will add actual layout (stat cards, table, activity log, etc.).
"""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QSize
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow

from container_tracker.__version__ import __version__
from container_tracker.ui.theme import apply_theme


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self._config = config
        self._is_dark: bool = bool(config.get("dark_mode", False))

        self.setWindowTitle(f"Container Tracker v{__version__}")
        self.resize(QSize(1100, 720))

        logger.info("MainWindow constructed (is_dark=%s)", self._is_dark)

    @property
    def is_dark(self) -> bool:
        return self._is_dark

    def toggle_dark_mode(self) -> None:
        """Flip the theme, regenerate the app-level stylesheet, persist to config.

        No UI trigger wires into this yet — the header's dark-mode switch is
        built in Phase 3 and will call this method.
        """
        self._is_dark = not self._is_dark
        apply_theme(is_dark=self._is_dark)
        self._config["dark_mode"] = self._is_dark
        logger.info("dark mode toggled → %s", self._is_dark)

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        logger.info("MainWindow shown")
        super().showEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        logger.info("MainWindow closing")
        super().closeEvent(event)
```

- [ ] **Step 2: Confirm module imports cleanly**

Run: `python -c "from container_tracker.ui.main_window import MainWindow; print('ok')"`
Expected: `ok` printed.

- [ ] **Step 3: Confirm mypy strict is still clean**

Run: `mypy --strict container_tracker`
Expected: clean on all source files.

- [ ] **Step 4: Commit**

```bash
git add container_tracker/ui/main_window.py
git commit -m "ui: MainWindow owns is_dark; add toggle_dark_mode (no UI trigger yet)"
```

---

## Task 6: Wire theme + config into `__main__.py`

**Files:**
- Modify: `container_tracker/__main__.py`

Two changes: (1) call `apply_theme` after `QApplication` is constructed but before `MainWindow`, based on `config["dark_mode"]`; (2) pass `config` to `MainWindow(config)`.

- [ ] **Step 1: Open `container_tracker/__main__.py` and modify `main()`**

Replace the body of `main()` with:

```python
def main() -> int:
    qt_handler = _configure_logging()
    logger = logging.getLogger(__name__)

    app = QApplication(sys.argv)
    app.setApplicationName("Container Tracker")
    app.setOrganizationName("Michael Cohen")

    logger.info("Container Tracker v%s starting", __version__)

    config = load_config()
    logger.info(
        "config loaded: company=%r, excel_path=%r, dark_mode=%s",
        config.get("company_name"),
        config.get("excel_path"),
        config.get("dark_mode"),
    )
    logger.info("first-run=%s, api-token-present=%s", is_first_run(config), bool(get_api_token()))

    # Apply the theme BEFORE constructing any widgets so they inherit from
    # the application-level stylesheet on first paint (no un-styled flash).
    from container_tracker.ui.theme import apply_theme
    apply_theme(is_dark=bool(config.get("dark_mode", False)))

    from container_tracker.ui.main_window import MainWindow
    window = MainWindow(config)
    window.show()

    _ = qt_handler  # will be connected to ActivityLog in Phase 3
    return app.exec()
```

- [ ] **Step 2: Smoke test — launch the app and verify theme applies**

Run via PowerShell tool:

```powershell
$ErrorActionPreference = "Stop"
$proc = Start-Process -FilePath "python" `
    -ArgumentList "-m", "container_tracker" `
    -WorkingDirectory "C:/Users/emine/OneDrive/Documents/Claude/container_tracking_build" `
    -PassThru
Start-Sleep -Seconds 2
$proc.Refresh()
Write-Output "PID=$($proc.Id) Title='$($proc.MainWindowTitle)' Handle=$($proc.MainWindowHandle)"
$proc.CloseMainWindow() | Out-Null
$proc.WaitForExit(5000) | Out-Null
Write-Output "Exit=$($proc.ExitCode)"
```

Expected: window shows, title `Container Tracker v1.1.0`, handle non-zero, exit 0. **Visually:** the window background should now be warm-bone (`#FAF8F3`) rather than default Qt gray — that confirms the stylesheet applied. (If `config.dark_mode=true`, background will be `#15171C` instead.)

- [ ] **Step 3: Run full tests + mypy**

Run: `pytest -v && mypy --strict container_tracker`
Expected: all tests pass, mypy clean.

- [ ] **Step 4: Commit**

```bash
git add container_tracker/__main__.py
git commit -m "main: apply theme on startup; pass config to MainWindow"
```

---

## Task 7: Theme preview harness (`container_tracker/ui/theme_preview.py`)

**Files:**
- Create: `container_tracker/ui/theme_preview.py`

A standalone module runnable via `python -m container_tracker.ui.theme_preview` that shows every styled component so a human can hand-verify the design system. Not part of the shipped app — it's a development tool. Does not need unit tests (visual verification is the contract).

- [ ] **Step 1: Create `container_tracker/ui/theme_preview.py`**

```python
"""Theme preview harness.

Standalone dev tool. Run with:
    python -m container_tracker.ui.theme_preview

Shows every styled widget the design system covers — primary/secondary/
destructive buttons, inputs, combo boxes, outlined cards, stat card,
table with headers, activity log — with a top toggle between light and
dark mode. Visual verification of spec §5.1 end-to-end.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from container_tracker.ui.theme import apply_theme


def _card(title: str, body: QWidget) -> QFrame:
    frame = QFrame()
    frame.setProperty("role", "card")
    layout = QVBoxLayout(frame)
    heading = QLabel(title)
    heading.setProperty("role", "heading")
    layout.addWidget(heading)
    layout.addWidget(body)
    return frame


def _stat_card(label: str, number: str, color_role: str) -> QFrame:
    frame = QFrame()
    frame.setProperty("role", "stat-card")
    layout = QVBoxLayout(frame)
    caption = QLabel(label)
    caption.setProperty("role", "secondary")
    number_label = QLabel(number)
    number_label.setProperty("role", "display")
    if color_role:
        # Mark the number with a role so a future QSS rule could tint it.
        # For now we stay within the palette via direct property.
        number_label.setProperty("statRole", color_role)
    layout.addWidget(caption)
    layout.addWidget(number_label)
    return frame


def _buttons_row() -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)

    primary = QPushButton("Refresh All ETAs & Update Excel")
    primary.setProperty("variant", "primary")

    secondary = QPushButton("Browse…")
    secondary.setProperty("variant", "secondary")

    destructive = QPushButton("Remove Selected")
    destructive.setProperty("variant", "destructive")

    default = QPushButton("Default (no variant)")

    for btn in (primary, secondary, destructive, default):
        layout.addWidget(btn)
    return row


def _inputs_row() -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)

    line = QLineEdit()
    line.setPlaceholderText("Container number, e.g. MSKU1234567")

    disabled_line = QLineEdit("disabled value")
    disabled_line.setDisabled(True)

    combo = QComboBox()
    combo.addItems(["MAERSK LINE", "MSC", "CMA CGM", "HAPAG LLOYD", "EVERGREEN"])

    for w in (line, disabled_line, combo):
        layout.addWidget(w)
    return row


def _stats_row() -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    for label, number, role in [
        ("Tracked", "12", ""),
        ("Sailing", "7", "sailing"),
        ("Arrived", "4", "arrived"),
        ("Delayed", "1", "delayed"),
    ]:
        layout.addWidget(_stat_card(label, number, role))
    return row


def _table_sample() -> QTableWidget:
    table = QTableWidget(3, 7)
    table.setHorizontalHeaderLabels(
        ["Container #", "Carrier", "Status", "ETA", "Delay", "Route", "Vessel"]
    )
    data = [
        ("MSKU1234567", "MAERSK LINE", "SAILING", "2026-05-05", "+4 days", "Shanghai → LA", "MV SEA PIONEER"),
        ("CMAU7654321", "CMA CGM",     "ARRIVED", "2026-03-20", "On time", "Ningbo → Long Beach", "MV PACIFIC STAR"),
        ("MSCU1111222", "MSC",         "SAILING", "2026-04-30", "",        "Rotterdam → NY", "MV ATLANTIC"),
    ]
    for row_idx, row_values in enumerate(data):
        for col_idx, value in enumerate(row_values):
            table.setItem(row_idx, col_idx, QTableWidgetItem(value))
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.verticalHeader().setVisible(False)
    return table


def _activity_log() -> QPlainTextEdit:
    log = QPlainTextEdit()
    log.setReadOnly(True)
    log.setPlainText(
        "2026-04-23 11:33:04 [INFO] Refreshing...\n"
        "2026-04-23 11:33:05 [INFO] Found 12 shipments\n"
        "2026-04-23 11:33:06 [INFO]   MSKU1234567: SAILING, ETA 2026-05-05, Shanghai → LA\n"
        "2026-04-23 11:33:06 [INFO]   CMAU7654321: ARRIVED, ETA 2026-03-20, Ningbo → Long Beach\n"
        "2026-04-23 11:33:07 [INFO] --- DONE: 12 matched, 0 unmatched, 1 delayed\n"
    )
    return log


class PreviewWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Container Tracker — Theme Preview")
        self.resize(1100, 900)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Top row — dark mode toggle.
        top = QHBoxLayout()
        heading = QLabel("Theme preview")
        heading.setProperty("role", "heading")
        top.addWidget(heading)
        top.addStretch(1)
        self._toggle = QCheckBox("Dark mode")
        self._toggle.stateChanged.connect(self._on_toggle)
        top.addWidget(self._toggle)
        root.addLayout(top)

        # Scroll area in case the harness outgrows the window.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)

        content_layout.addWidget(_card("Buttons (primary / secondary / destructive / default)", _buttons_row()))
        content_layout.addWidget(_card("Inputs (QLineEdit + QComboBox + disabled)", _inputs_row()))
        content_layout.addWidget(_card("Stat cards", _stats_row()))
        content_layout.addWidget(_card("Table", _table_sample()))
        content_layout.addWidget(_card("Activity log (QPlainTextEdit, mono)", _activity_log()))

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _on_toggle(self, state: int) -> None:
        is_dark = state == Qt.CheckState.Checked.value
        apply_theme(is_dark=is_dark)


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(is_dark=False)
    window = PreviewWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Confirm the module imports cleanly**

Run: `python -c "from container_tracker.ui.theme_preview import PreviewWindow; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Confirm mypy strict still clean**

Run: `mypy --strict container_tracker`
Expected: clean. (May surface a signature-ignore on `QCheckBox.stateChanged.connect` or similar; if so, apply the minimum-invasive fix as in Phase 1 d21d17b — `# type: ignore[...]` with a short explanatory comment.)

- [ ] **Step 4: Visual smoke test**

Run via PowerShell:

```powershell
$ErrorActionPreference = "Stop"
$proc = Start-Process -FilePath "python" `
    -ArgumentList "-m", "container_tracker.ui.theme_preview" `
    -WorkingDirectory "C:/Users/emine/OneDrive/Documents/Claude/container_tracking_build" `
    -PassThru
Start-Sleep -Seconds 2
$proc.Refresh()
Write-Output "Preview PID=$($proc.Id) Title='$($proc.MainWindowTitle)' Handle=$($proc.MainWindowHandle)"
$proc.CloseMainWindow() | Out-Null
$proc.WaitForExit(5000) | Out-Null
Write-Output "Exit=$($proc.ExitCode)"
```

Expected: title `Container Tracker — Theme Preview`, handle non-zero, clean exit. The window (if observed live) shows primary-CTA pill buttons in navy, outlined secondary buttons, rust destructive buttons, outlined cards, stat cards, a sample table, and an activity log. Toggling the "Dark mode" checkbox flips the entire palette.

- [ ] **Step 5: Commit**

```bash
git add container_tracker/ui/theme_preview.py
git commit -m "ui: add theme_preview harness for visual design-system verification"
```

---

## Task 8: Phase 2 smoke test and sign-off

**Files:** none modified.

- [ ] **Step 1: Full test run**

Run: `pytest -v`
Expected: all tests pass (Phase 1 count + Phase 2 additions).

- [ ] **Step 2: mypy strict full run**

Run: `mypy --strict container_tracker`
Expected: `Success: no issues found in N source files` (N ≥ 14: core/* + ui/theme.py + ui/theme_preview.py + ui/widgets.py + ui/main_window.py + __main__.py + __version__.py + __init__.py).

- [ ] **Step 3: Main app launch — visibility check**

Run via PowerShell:

```powershell
$ErrorActionPreference = "Stop"
$proc = Start-Process -FilePath "python" `
    -ArgumentList "-m", "container_tracker" `
    -WorkingDirectory "C:/Users/emine/OneDrive/Documents/Claude/container_tracking_build" `
    -PassThru
Start-Sleep -Seconds 2
$proc.Refresh()
if ($proc.MainWindowHandle -eq 0 -or [string]::IsNullOrEmpty($proc.MainWindowTitle)) {
    Write-Output "FAILURE: visibility regression"
    Stop-Process -Id $proc.Id -Force
    exit 1
}
Write-Output "OK: PID=$($proc.Id) Title='$($proc.MainWindowTitle)' Handle=$($proc.MainWindowHandle)"
$proc.CloseMainWindow() | Out-Null
$exited = $proc.WaitForExit(5000)
Write-Output "Exit=$($proc.ExitCode) Exited=$exited"
```

Expected: handle non-zero, title "Container Tracker v1.1.0", clean exit 0.

- [ ] **Step 4: Preview harness launch — visibility check**

Same PowerShell pattern with `-ArgumentList "-m", "container_tracker.ui.theme_preview"`. Expected: visible window titled "Container Tracker — Theme Preview", handle non-zero, clean exit.

- [ ] **Step 5: No commit** — this is a pure verification step.

---

## CHECKPOINT B — STOP — PHASE 2 COMPLETE

**What's now true:**
- `container_tracker/ui/theme.py` has the full design system (palettes, typography, spacing, radius, QSS builder, apply_theme).
- `MainWindow(config)` owns `is_dark` and can `toggle_dark_mode()` (no UI trigger yet — that's Phase 3).
- `container_tracker/__main__.py` applies the theme before showing the window; background now reads `#FAF8F3` (or dark equivalent) instead of default Qt gray.
- `container_tracker/ui/theme_preview.py` renders every styled widget for hand-verification in both modes.
- `pytest` green, `mypy --strict container_tracker` clean, Windows shell enumeration clean (no spec §9 regression).

**Ready for Phase 3** (main window layout: header, update banner, stat cards, action row, table, activity log, footer — all wired to sample data, no backend functionality yet).

---

## Self-Review

**1. Spec coverage** (§5.1 in detail):
- LIGHT_PALETTE + DARK_PALETTE with exact hex values → Task 1.
- TYPOGRAPHY, SPACING, RADIUS → Task 2.
- `build_stylesheet(palette) -> str` covering QWidget, QPushButton 3 variants, QLineEdit, QComboBox, QTableView, QHeaderView, QFrame[role="card"], QFrame[role="stat-card"], QPlainTextEdit → Task 3.
- `[variant="primary"]` QSS property-selector pattern → Task 3.
- Theme toggle regenerating stylesheet via `QApplication.setStyleSheet` (no per-widget overrides) → Task 4 (`apply_theme`) + Task 5 (`MainWindow.toggle_dark_mode`).
- Primary family `Segoe UI Variable` with `Segoe UI` fallback; mono `Cascadia Code` with `Consolas` fallback → Task 2 (`FONT_FAMILY_PRIMARY`, `FONT_FAMILY_MONO`).
- Pure-red `#D32F2F` fix (use muted rust) → Task 1 test + Task 3 test.
- Visual test harness → Task 7 (`theme_preview.py`).
- MainWindow owns `is_dark` per spec §3.3 → Task 5.

**2. Placeholder scan:** grepped the plan for "TBD", "TODO", "Similar to Task", "fill in" — none present.

**3. Type + signature consistency:**
- `apply_theme(is_dark: bool) -> None` — same signature used in Task 4 (definition), Task 5 (called from `toggle_dark_mode`), Task 6 (called from `__main__`), Task 7 (called from preview harness).
- `MainWindow.__init__(self, config: dict[str, Any])` — Task 5 defines; Task 6 calls as `MainWindow(config)`.
- `build_stylesheet(palette: dict[str, str]) -> str` — Task 3 defines; Task 4 uses.
- Palette keys referenced in build_stylesheet (`accent`, `surface_base`, etc.) all exist in both palettes per Task 1's required-keys test.

**4. No breaking changes to Phase 1 code beyond MainWindow constructor signature.** Phase 1 tests remain passing throughout.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-23-pyside6-phase2-theme-and-qss.md`.

Execution mode: same as Phase 1 — subagent-driven, one subagent per checkpoint, autonomous within-phase dispatch (no pause between Checkpoint A and B). User reviews at phase boundary only per established cadence.
