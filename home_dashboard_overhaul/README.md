# Home Screen Dashboard 1.8.6

Home Screen Dashboard is a calendar-first Deck Browser dashboard for Anki
Desktop 26.8. It combines study history, due work, local events, stable study
metrics, and a rotating Bible verse without patching Anki's private Deck
Browser or statistics classes.

## What changed in 1.8.6

- Every study-derived value is computed from one scheduler-authoritative
  snapshot. Today uses `[next rollover − 86,400 seconds, next rollover)`, and
  calendar/streak history uses matching rollover-relative day indexes instead
  of civil-midnight arithmetic.
- Last 7 Days and All Time Retention mirror Anki 26.8.1 native eligible-review
  retention. Review-kind answers qualify, as do learning/relearning answers
  whose prior interval is at least one day; Again fails and Hard/Good/Easy
  pass. The visible integer Retention is rounded half-up once and Again is
  displayed as `100 − Retention`.
- Today’s Progress uses Anki's limited due tree plus its built reviewer queue
  and dashboard deck exclusions. New, Learning, and Review are disjoint,
  `Total remaining` is enforced as their sum, and a future intraday learning
  card outside learn-ahead is never inferred to be buried.
- Today’s Session counts rated answer events and elapsed review time in the
  active scheduler period, distinct qualifying new introductions, and cards
  presently in explicit buried queues. Pace remains seconds per answer and
  ETA keeps the existing empirical policy with a whole-minute ceiling.
- Calendar forecasting matches Anki's non-new, non-suspended future-due logic,
  including filtered-deck original due dates and future buried cards while
  excluding buried work due in the active day. Tooltips and selected-day
  details consume the same canonical history records as the metric cards.
- Initial HTML, live refresh, Month/Year 2×2, intermediate, narrow, Settings
  Preview, and restart states are checked for identical metric values. Schema
  8, all existing labels/order/JSON/DOM keys, and bridge commands are unchanged.

- Settings has one native Qt widget tree at every size: a compact global
  header, fixed 152 px text rail, one page scroller, one shared optional
  Preview dock, and a true final-row footer. On a physically smaller screen,
  the same dock becomes a layout-managed overlay.
- Dashboard, Events, Bible verse, and About use compact shared rows and
  content-sized controls. Preview starts open each Dashboard, Events, and
  Bible session, is omitted on About, and is not persisted.
- Preview uses the production renderer for Section/Full dashboard and
  Fit/100%, reflects all staged state, and writes nothing until Save.
- Month is always 42 cells. Year always uses one responsive 53-week tree that
  stays inside the dashboard without horizontal scrolling at 480 px and above;
  only the heatmap may scroll below that boundary. Calendar legend and
  event-summary groups disappear when their features are disabled.
- The production root is transparent and in normal document flow at a 1,120 px
  maximum. It measures Anki's visible fixed/sticky bottom action container and
  maintains a 24 px clearance, using 60 px only as the missing-height fallback.
- The 16 existing completion-palette IDs now resolve to distinct, separately
  authored light and dark ladders.
- `events.sort` additionally accepts `name`, ordered case-insensitively by
  name, date, and stable ID. Schema remains 8 and all other keys retain their
  meanings.
- Saving prepares both config and manual-verse writes, replaces atomically
  where supported, and rolls back best-effort if only one succeeds. Errors are
  specific and inline, and the dialog remains open.
- New, Learning, and Reviews remaining use Anki's scheduler-authoritative due
  tree with scoped deck exclusions, then reconcile the selected subtree with
  Anki's built queue so buried/hidden siblings are not actionable. Learning
  includes both learning and relearning, matching Anki's native counter. Total
  remaining, ETA, and completion consume those same reconciled values.

## Dashboard

Month and Year share one persistent controller-owned view. Today's Progress
contains New, Learning, Reviews, and Total remaining. Today's Session contains
Cards studied, New cards studied, Cards buried, Time spent, Pace, and ETA. Last
7 Days and All Time use Anki-native eligible retention over their exact
scheduler periods. The configured Bible verse is rendered at its exact font,
size, and color.

The compact calendar footer retains date selection, tooltip, Browser routing,
event edit/add, and Most Missed behavior. Due and event legend/summary groups
are omitted when their corresponding features are disabled.

## Themes, settings, and persistence

Open settings from Anki's Tools menu or the calendar gear. Changes stay staged
until **Save changes**. **Revert changes** returns every staged field to the
saved baseline. The baseline updates only after a completely successful save.

The Settings chrome derives its colors solely from Anki's light/dark
appearance. Dashboard themes affect only swatches and production-rendered
preview content. Settings opens as an ordinary, parented, non-modal QDialog at
a fixed 1200×800 size, clamped for smaller screens instead of restoring a saved
size. On macOS, opening additionally verifies that the dialog is a native child
of Anki's window so it stays in Anki's active full-screen Space; attachment
failure is reported and the dialog does not open ambiguously.

The dashboard remains inactive while a legacy source add-on is enabled, which
prevents duplicate panels and load-order conflicts. External-calendar source
work remains deferred and is not packaged.

## Install

Install `home-dashboard-overhaul-1.8.6.ankiaddon` through **Tools → Add-ons →
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
is installed into one fresh sync-disabled Anki 26.8 profile for an initial pass
and a controlled restart. Native acceptance follows the current contract: 102
captures spanning production, Settings, and restart states, with validated
contact-sheet coverage and direct Anki Graphs/Scheduler parity.

VoiceOver, Windows, Linux, forced colors, DPR 1, and OS-level display-scaling
acceptance remain deferred and unclaimed unless separately run.

Copyright 2026. Licensed under AGPL-3.0-or-later. See
`THIRD_PARTY_NOTICES.md` for Scripture and upstream notices.
