# Home Screen Dashboard 1.8.0

Home Screen Dashboard is a calendar-first Deck Browser dashboard for Anki
Desktop 26.8. It combines study history, due work, local events, progress
metrics, and a rotating Bible verse without patching Anki's private Deck
Browser or statistics classes.

## What changed in 1.8.0

- Rebuilt all four light/dark themes around shared semantic roles for canvas,
  surfaces, text, controls, study states, calendar overlays, and progress.
- Made New, Learning, Review, Buried, Success, Danger, and Event colors stable
  across themes while keeping each theme's accent and surface identity.
- Replaced opacity-derived calendar heat colors with explicit completion and
  Reviews Due scales, including readable date text and a fixed-height due
  marker that does not depend on hue alone.
- Strengthened the shared Month/Year layout, responsive metric rail, calendar
  footer, interaction states, typography, and full-viewport theme painting.
- Added automated hardcoded-color and contrast audits for production surfaces.

## Dashboard

Month and Year share one persistent shell. At wide widths the calendar sits to
the left of a fixed-order insight rail containing Today's Progress, Today's
Session, Last 7 Days, All Time, and the Bible verse. At smaller widths the rail
moves below the calendar without changing its order.

The integrated calendar footer contains the Completion, Reviews Due, and Event
legends; the selected date; the next upcoming event and edit action; and an
exact Reviewed or Due Browser action when matching cards exist. Most missed is
available only after an eligible Again answer. Card previews, a separate event
column, due-deck lists, and the old selected-date details panel are not rendered.

Completion uses six explicit opaque levels. Future Reviews Due uses five soft
violet levels plus a stronger fixed-height bottom marker. Today, selection,
keyboard focus, adjacent-month dates, and event diamonds remain independent so
combined states keep their meaning.

## Themes and responsive behavior

The themes are Sapphire Glass, Graphite, Emerald, and High Contrast. Existing
saved theme and heatmap identifiers remain compatible and resolve to their
theme's canonical completion scale. The active theme paints the full WebView
canvas, including unused and overscrolled space, and publishes matching browser
color-scheme and scrollbar colors.

At 940 CSS pixels and wider, Month and Year place the 2×2 metric grid and Bible
verse beside the calendar. From 440–939 pixels the rail follows the calendar
while retaining two metric columns. Below 440 pixels the metric cards use one
column. The Year heatmap remains complete and scrolls internally only below its
minimum readable width.

## Settings and persistence

Open settings from Anki's Tools menu or the calendar gear. The four pages are
Dashboard, Events, Bible verse, and About & support. Settings remain staged
until **Save changes**; section resets are undoable, event actions stay attached
to their rows, and the Dashboard and Bible previews use the production renderer.

Configuration schema 6 removes retired layout slots while preserving unrelated
keys, events, verse data, saved theme identifiers, and supported preferences.
The dashboard remains inactive while a legacy source add-on is enabled, which
prevents duplicate panels and load-order conflicts. External-calendar source
work remains deferred and is not packaged.

## Install

Install `home-dashboard-overhaul-1.8.0.ankiaddon` through **Tools → Add-ons →
Install from file**, restart Anki, and disable any legacy source add-ons named by
the activation card. The manifest is pinned to Anki Desktop 26.8.

## Build and offline validation

From the repository root, use Python 3.10 or newer:

```sh
python3 -m unittest discover -s home_dashboard_overhaul/tests -p 'test_*.py' -v
node home_dashboard_overhaul/tests/calendar_model_test.js
python3 home_dashboard_overhaul/qa/validate_revised_ui_contract.py
python3 home_dashboard_overhaul/qa/color_system_audit.py --output home_dashboard_overhaul/dist/color-audit
python3 home_dashboard_overhaul/tools/build_ankiaddon.py
```

The deterministic builder creates a 24-file allowlisted archive under `dist/`,
checks safe paths and fixed timestamps, and verifies every packaged byte against
the source tree. QA tools, deferred modules, local user data, and generated
evidence are excluded.

The 1.8.0 release gate is intentionally offline: source, contract, color,
package-integrity, and source/archive-parity checks are required, but live Anki,
restart persistence, spoken VoiceOver, Windows/Linux rendering, forced colors,
and device-specific display scaling are not claimed.

Copyright 2026. Licensed under AGPL-3.0-or-later. See
`THIRD_PARTY_NOTICES.md` for Scripture and upstream notices.
