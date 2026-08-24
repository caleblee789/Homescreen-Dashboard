# Home Screen Dashboard 1.8.2

Home Screen Dashboard is a calendar-first Deck Browser dashboard for Anki
Desktop 26.8. It combines study history, due work, local events, stable study
metrics, and a rotating Bible verse without patching Anki's private Deck
Browser or statistics classes.

## What changed in 1.8.2

- Rebuilt the 100% layout around a 1,320 px maximum dashboard, 16 px minimum
  side margins, 22 px top spacing, 12 px component gaps, and 72 px native
  footer clearance. Calendar and rail heights are independent.
- Replaced the old responsive thresholds with container breakpoints at 940 and
  440 px. The calendar and rail sit side by side at 940 px and above; below
  that, the rail follows as a 2x2 metric grid until 440 px, then becomes one
  column. Only the Year heatmap scrolls horizontally below 320 px.
- Corrected the Month and continuous 53-column Year presentations, including
  neutral future cells, three-level due strips, deterministic state layering,
  compact event counts, an integrated footer, adjacent event editing, a tonal
  card action, and a collision-aware 190-220 px tooltip.
- Replaced the segmented workload display with one 14 px completion bar. Its
  states distinguish `No cards scheduled`, `All clear`, `100% complete`, an
  active percentage, and unavailable data without fabricating a value.
- Finalized the metric rows. Today's Session now includes the scheduler-current
  `Cards buried` total and `Time spent`; Buried is no longer an independent
  configurable dashboard surface.
- Added compact time and ETA values, stable large-number behavior,
  content-driven Bible sizing, deliberate fresh/empty/complete states, and
  retained-data refresh failures with Retry.
- Centralized semantic themes. Sapphire Glass alone uses component-level
  translucency and backdrop blur; Graphite, Emerald, and High Contrast are
  opaque, and High Contrast has no decorative shadows or transparency. The
  wallpaper and all surrounding Anki chrome remain untouched.
- Upgraded configuration to schema 8. Sapphire opacity is clamped to 94-100
  (default 96), blur to 0-16 px (default 12), and those controls are disabled
  for opaque themes. Schema-7 migration preserves valid Month/Year choice and
  unrelated settings while removing `visibility.buried`.

## Dashboard

Month and Year share one persistent controller-owned view. At wide widths the
calendar sits to the left of a fixed-order rail:

```text
Today's Progress | Today's Session
Last 7 Days      | All Time
Bible verse across both rail columns
```

Today's Progress contains New remaining, Learning remaining, Reviews
remaining, and Total remaining. Today's Session contains Cards studied, New
cards studied, Cards buried, Time spent, Pace, and ETA. Last 7 Days contains
Cards studied, New cards studied, Retention, and Again rate. All Time contains
Avg cards/day, Current streak, Longest streak, Retention, and Cards studied.

The integrated calendar footer contains the corrected Completion, Reviews due,
and Event legend; date context; the selected or next event with an adjacent
pencil; and only the exact Browser action supported by that date.

## Themes, settings, and persistence

Open settings from Anki's Tools menu or the calendar gear. Changes remain
staged until **Save changes**. Theme, light/dark mode, completion palette,
visibility, glass settings, week start, and Month/Year view persist across
refreshes and restarts. Loading, Retry, theme changes, settings saves, and live
updates all reuse the same saved calendar view.

The dashboard remains inactive while a legacy source add-on is enabled, which
prevents duplicate panels and load-order conflicts. External-calendar source
work remains deferred and is not packaged.

## Install

Install `home-dashboard-overhaul-1.8.2.ankiaddon` through **Tools -> Add-ons ->
Install from file**, restart Anki, and disable any legacy source add-ons named
by the activation card. The manifest is pinned to Anki Desktop 26.8.

## Build and validation

From the repository root, use Python 3.10 or newer:

```sh
python3 -m unittest discover -s home_dashboard_overhaul/tests -p 'test_*.py' -v
node home_dashboard_overhaul/tests/calendar_model_test.js
python3 home_dashboard_overhaul/qa/validate_revised_ui_contract.py
python3 home_dashboard_overhaul/qa/color_system_audit.py --output home_dashboard_overhaul/dist/color-audit-1.8.2
python3 home_dashboard_overhaul/tools/build_ankiaddon.py
```

The deterministic builder creates a 24-file allowlisted archive, checks safe
paths and fixed timestamps, and verifies every packaged byte against source.
The 1.8.2 release gate rebuilds twice, verifies identical SHA-256, archive
integrity, imports, source parity, and then installs that exact archive in a
fresh sync-disabled Anki 26.8.1 profile. Native acceptance requires 48 captures
at 100%, an overview, 13 readable detail sheets, and a passed hard-restart
persistence frame.

Spoken screen-reader review, Windows/Linux, forced colors, OS-level scaling,
and dedicated 125%/150% visual acceptance remain deferred and unclaimed.

Copyright 2026. Licensed under AGPL-3.0-or-later. See
`THIRD_PARTY_NOTICES.md` for Scripture and upstream notices.
