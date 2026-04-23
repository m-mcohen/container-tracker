# Phase 5.5 — Polish Backlog

Items deferred during earlier phases. Not blockers; pick these up in a dedicated polish pass after Phase 5 (functionality wiring) and before Phase 7 (packaging).

---

## 1. Ghost-button disabled state is invisible in QSS

**Discovered:** Phase 4 Checkpoint A review.

**Symptom:** `QPushButton[variant="secondary"]` (the "ghost" variant — transparent bg, accent border, accent text) shows no visual change when `setEnabled(False)`. Browse / Create Template / Open in Excel are programmatically disabled (clicks do nothing — verified) but look identical to enabled ghost buttons. Users have no signal that the button is off.

**Cause:** `container_tracker/ui/theme.py` `build_stylesheet` defines `QPushButton[variant="secondary"]` and `QPushButton[variant="secondary"]:hover`, but no `:disabled` pseudo-state. The base `QPushButton:disabled` rule (`color: text_tertiary`, `border-color: border_subtle`) doesn't apply because the variant selector is more specific.

**Fix:** Add a `QPushButton[variant="secondary"]:disabled` rule to `build_stylesheet` that mirrors the disabled palette — muted border, muted text, no hover effect. Likely also worth adding `QPushButton[variant="primary"]:disabled` and `QPushButton[variant="destructive"]:disabled` for consistency, even though primary's disabled state already reads as "off" via the existing `QPushButton:disabled` cascade.

**Verification:** launch `python -m container_tracker`. The three LinkedSpreadsheetCard buttons (Browse, Create Template, Open in Excel) should look visibly off at rest, with no hover effect on mouseover.

---

## 2. Table column widths exceed viewport with long cell content

**Discovered:** Phase 4 Checkpoint A review.

**Symptom:** Vessel and Transit % columns are cut off; horizontal scroll appears. The Phase 4 Checkpoint A spot-check measured 979 px total width — that included sample data with short names. Real-world data with longer port names or vessel names blows past the 1004-px content area.

**Cause:** `QHeaderView::ResizeMode.ResizeToContents` sizes each column to fit the widest cell. With long sample strings like "Shanghai, China → Los Angeles, USA" (Route) or "MV PACIFIC STAR" (Vessel), columns expand past the viewport.

**Fix options:**

1. **Capped widths per column.** Apply explicit `header.resizeSection(i, max_width_for_col_i)` after `ResizeToContents` runs. Keeps the auto-sizing benefit but prevents overflow.
2. **Stretch a non-Route column to fill remaining space, truncate Route with ellipsis.** Set Route to `Interactive` with a fixed width and `setTextElideMode(Qt.ElideRight)` on the table.
3. **Switch the entire header to `Stretch` mode.** All columns share width equally — simple but doesn't respect content density.
4. **Hybrid:** `ResizeToContents` for narrow columns (Container #, Status, Delay, Transit %) + `Stretch` for the variable-width columns (Route, Vessel) so they share leftover space.

**Recommended:** option 4. Phase 5.5 implementer should confirm with sample data that includes both short and long values.

---

## 3. Dark-mode primary CTA color philosophy needs review

**Discovered:** Phase 4 Checkpoint A review.

**Current state (post-Checkpoint A swap):** dark-mode accent moved from `#6B9DD4` (washed-out pale blue) to `#3E74B8` (saturated navy). User feedback: "marginal improvement, acceptable for now." The buttons still don't fully feel like the same component as light-mode CTAs.

**Hypothesis:** dark-mode primary CTAs may need to be **lighter than the surrounding surface**, not darker. Light-mode convention puts dark navy on warm-bone surface — the CTA "comes forward" because it's darker. Inverting that for dark mode (saturated navy on near-black) makes the CTA "recede" because it's only marginally lighter than the surface.

**Alternative philosophy:** dark-mode primary CTAs use a **light, saturated accent that contrasts up** against the dark surface — e.g., a brighter teal or off-white pill with dark text. The "primary action" cue then reads as "the brightest thing on screen." This is how many modern dark-mode UIs (e.g., GitHub, Linear, Notion) handle CTAs.

**Fix scope:** larger than a single hex swap. Phase 5.5 implementer should:

1. Mock up 2–3 dark-mode CTA candidates (e.g., light-text-on-saturated-navy, dark-text-on-bright-cream, a fully inverted "off-white pill with charcoal text").
2. Compare via `theme_preview.py` harness side-by-side with light mode.
3. Pick one that holds visual weight as the dominant call-to-action against `#15171C`.
4. Adjust `DARK_PALETTE["accent"]` and any related rules accordingly.

**Don't fix in isolation:** the choice affects ghost-button text color (still uses `accent`) and the update banner accent. Whichever path is chosen needs to flow through the QSS rules consistently.

---

## When to address

After Phase 5 (functionality complete) and before Phase 7 (packaging). A dedicated Phase 5.5 polish pass keeps these from delaying functional milestones while ensuring they ship in v1.1.0.
