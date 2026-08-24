# Home Screen Dashboard 1.8.4

Home Screen Dashboard is a calendar-first Deck Browser dashboard for Anki
Desktop 26.8. It combines study history, due work, local events, stable study
metrics, and a rotating Bible verse without patching Anki's private Deck
Browser or statistics classes.

## What changed in 1.8.4

- `New remaining` now uses Anki's full due tree instead of the currently
  selected deck's reviewer queue. Included head decks keep independent daily
  limits, recursive parent/child caps are applied once, and configured deck
  exclusions still remove their contribution.
- Total remaining, ETA, and completion consume that same scheduler-limited
  count. If Anki cannot provide a trustworthy due tree, Today’s Progress is
  shown as unavailable instead of falling back to uncapped inventory.
- All 1.8.3 responsive layout, footer, Year scrolling, visual polish, runtime
  states, and schema-8 behavior is retained unchanged.

- The dashboard now uses Anki's real document scroller, a 1,240 px maximum,
  and 66 px of bottom clearance for the 42 px native controls plus a 24 px gap.
  The host canvas, Deck Browser background, and external compatibility
  backgrounds remain untouched.
- Calendar and rail stay side by side from 1,040 px with a rail at least 372 px
  wide. Below that they stack, metrics auto-fit around a 180 px minimum, and
  the narrow density begins below 420 px.
- The calendar footer has separate date, event, and action regions with one,
  two, or three rows at the 760 and 420 px thresholds. `Next event`, `On this
  date`, and `No event on this date` now have distinct meanings, and the event
  action switches between `Edit event` and `Add event`.
- Year remains fully visible from 480 px. Below 480 px it alone gains a
  restrained internal scroller; January, the current month, and December stay
  reachable, initial/Today centering is deliberate, and manual scroll position
  survives rerenders.
- Metric labels stay readable, values remain tabular and right-aligned, and the
  larger completion bar keeps its percentage readable over both filled and
  unfilled portions. Month due strips and event markers retain safe insets.
- Graphite interactions now use slate accents, Emerald Dark uses the corrected
  neutral-green surfaces, and the light level-one heat colors are stronger.
  High Contrast remains opaque.
- Loading skeletons are clearer, the initial failure panel is more compact, and
  a retained-data refresh failure uses one full-width banner with one last
  updated timestamp.
- Configuration schema remains 8. No setting, migration, or public API was
  added.

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

Install `home-dashboard-overhaul-1.8.4.ankiaddon` through **Tools -> Add-ons ->
Install from file**, restart Anki, and disable any legacy source add-ons named
by the activation card. The manifest is pinned to Anki Desktop 26.8.

## Build and validation

From the repository root, use Python 3.10 or newer:

```sh
python3 -m unittest discover -s home_dashboard_overhaul/tests -p 'test_*.py' -v
node home_dashboard_overhaul/tests/calendar_model_test.js
python3 home_dashboard_overhaul/qa/validate_revised_ui_contract.py
python3 home_dashboard_overhaul/tools/build_ankiaddon.py
```

The builder creates one 24-file allowlisted archive, checks its version and
safe paths, and verifies every packaged byte against source. That exact archive
is installed in one fresh sync-disabled Anki 26.8 profile for a bounded smoke
pass and one restart. Native acceptance requires 56 captures at 100%, one
overview, 15 readable detail sheets, and passed Year-view persistence.

VoiceOver, Windows/Linux, forced colors, OS-level scaling, and non-100% visual
acceptance remain deferred and unclaimed.

Copyright 2026. Licensed under AGPL-3.0-or-later. See
`THIRD_PARTY_NOTICES.md` for Scripture and upstream notices.
