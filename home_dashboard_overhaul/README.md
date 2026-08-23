# Home Screen Dashboard 1.8.1

Home Screen Dashboard is a calendar-first Deck Browser dashboard for Anki
Desktop 26.8. It combines study history, due work, local events, stable study
metrics, and a rotating Bible verse without patching Anki’s private Deck
Browser or statistics classes.

## What changed in 1.8.1

- Recalibrated the native 100% dashboard to a 1,480 px maximum width, a
  430–450 px statistics rail, real 100%-scale typography, compact Month rows,
  and a much larger unframed Year heatmap.
- Added component-width responsive layouts at about 1,220, 900, and 640 px.
  Wide keeps calendar left and rail right; intermediate moves the 2×2 rail
  below; narrow uses one metric card per row without horizontal scrolling.
- Simplified calendar composition: completed reviews are the historical fill,
  today uses one capsule or Year marker, selection uses one 2 px outline, and
  due work uses three compact indicator levels that can coexist with completion
  and gold event markers.
- Stabilized all metric rows. A true empty workload reads `No cards due`;
  partial and complete workloads show only their percentage; Today’s Session
  always includes Pace and ETA; unavailable values render `—`; zeros remain
  neutral; and semantic category colors appear only for positive values.
- Improved selected-date event precedence, event counts, long-title handling,
  and exact `Reviewed cards` / `Due cards` actions.
- Preserved Bible font-size choice through a safe responsive clamp and removed
  the rail gap when the Bible card is disabled.
- Kept native/default backgrounds transparent. A page-level scrim is used only
  when an actual background image is detected.
- Upgraded configuration to schema 7. `study.show_eta`,
  `study.show_estimate`, and legacy `ShowTimeLeft` are retired; unrelated
  unknown keys and all other preferences remain preserved. ETA is permanent.

## Dashboard

Month and Year share one persistent shell. At wide widths the calendar sits to
the left of a fixed-order rail:

```text
Today’s Progress | Today’s Session
Last 7 Days      | All Time
Bible verse across both rail columns
```

The integrated footer contains the Completed reviews, Reviews due, and Event
legend groups; selected-date context; an event on that date or the true global
next event; and only the exact Browser action available for the selected date.
Card previews, a separate event column, due-deck lists, and the old large
selected-date panel remain removed.

## Themes and scale

Sapphire Glass, Graphite, Emerald, and High Contrast share one semantic token
system in light and dark modes. Cyan New, amber Learning, purple Review,
gold/orange Event, and status colors stay stable while each theme retains its
own surface and interaction identity.

The release is visually calibrated at 100% dashboard text scale. Saved 90–150%
values remain supported, but dedicated 125% and 150% captures are deferred.

## Settings and persistence

Open settings from Anki’s Tools menu or the calendar gear. Changes remain
staged until **Save changes**. Schema 7 removes only known retired fields and
preserves unrelated keys, events, verse data, saved theme/palette choices,
visibility, calendar view, week start, and supported study preferences.

The dashboard remains inactive while a legacy source add-on is enabled, which
prevents duplicate panels and load-order conflicts. External-calendar source
work remains deferred and is not packaged.

## Install

Install `home-dashboard-overhaul-1.8.1.ankiaddon` through **Tools → Add-ons →
Install from file**, restart Anki, and disable any legacy source add-ons named
by the activation card. The manifest is pinned to Anki Desktop 26.8.

## Build and validation

From the repository root, use Python 3.10 or newer:

```sh
python3 -m unittest discover -s home_dashboard_overhaul/tests -p 'test_*.py' -v
node home_dashboard_overhaul/tests/calendar_model_test.js
python3 home_dashboard_overhaul/qa/validate_revised_ui_contract.py
python3 home_dashboard_overhaul/qa/color_system_audit.py --output home_dashboard_overhaul/dist/color-audit
python3 home_dashboard_overhaul/tools/build_ankiaddon.py
```

The deterministic builder creates a 24-file allowlisted archive, checks safe
paths and fixed timestamps, and verifies every packaged byte against source.
The release workflow rebuilds twice, verifies the checksum, archive integrity,
imports and source parity, then installs that exact archive in a fresh
sync-disabled disposable Anki 26.8.1 profile for native 100% evidence and
restart/persistence readback.

Spoken screen-reader review, Windows/Linux, forced colors, OS-level scaling,
and dedicated 125%/150% visual acceptance are not claimed for 1.8.1.

Copyright 2026. Licensed under AGPL-3.0-or-later. See
`THIRD_PARTY_NOTICES.md` for Scripture and upstream notices.
