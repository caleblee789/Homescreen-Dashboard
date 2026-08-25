# Home Screen Dashboard 1.8.7

Home Screen Dashboard is a calendar-first Deck Browser dashboard for Anki
Desktop 26.8. It combines study history, due work, local events, stable study
metrics, and a rotating Bible verse without patching Anki's private Deck
Browser or statistics classes.

## What changed in 1.8.7

- Settings now opens as a compact centered workspace inserted into Anki's
  existing central layout. It prefers 680×620, adapts within 12-pixel host
  margins, and cannot become a separate macOS window or Space.
- The controller reuses one workspace while it is open. Menu and Deck Browser
  requests are deferred and coalesced, while primary Save and dirty-close
  confirmations use stacked layout pages instead of floating layers.
- The corrected 1.8.6 statistics, schema 8, configuration keys, bridge
  commands, and all four Settings pages remain unchanged.

- Every study-derived value is computed from one scheduler-authoritative
  snapshot. Today uses `[next rollover − 86,400 seconds, next rollover)`, and
  calendar/streak history uses matching rollover-relative day indexes instead
  of civil-midnight arithmetic.
- Last 7 Days and All Time Retention mirror Anki 26.8.1 native eligible-review
  retention. Eligible rows have `ease > 0`, exclude filtered cram rows with
  `type = 3` and `factor = 0`, and are review-kind or have a prior interval of
  at least one day. Again fails and Hard/Good/Easy pass. The visible integer
  Retention is rounded half-up once and Again is displayed as
  `100 − Retention`; later suspension or burial does not erase past answers.
- Today’s Progress is collection-wide minus excluded deck descendants. It
  applies each included top-level head's native due-tree limits independently,
  and the selected deck cannot change the result. Queue 0 is New, queues 1/3/4
  are Learning, and queue 2 is Review regardless of card type; queues -1/-2/-3
  are not remaining. `Total remaining` is enforced as the category sum.
- Today’s Session counts rated answer events and elapsed review time in the
  active scheduler period, distinct qualifying new introductions, and cards
  presently in scoped explicit buried queues -2/-3 that are New or currently
  due/overdue. Future Learning and Review cards and transient queue-hidden
  siblings are excluded. Pace remains seconds per answer and ETA keeps the
  existing empirical policy with a whole-minute ceiling.
- Calendar forecasting matches Anki's non-new, non-suspended future-due logic,
  including filtered-deck original due dates and future buried cards while
  excluding buried work due in the active day. Tooltips and selected-day
  details consume the same canonical history records as the metric cards.
- Initial HTML, live refresh, Month/Year 2×2, intermediate, narrow, and restart
  states are checked for identical metric values. Schema
  8, all existing labels/order/JSON/DOM keys, and bridge commands are unchanged.

- Settings has one native Qt widget tree at every size: a compact global
  header, fixed 152 px text rail, one page scroller, and a true final-row
  footer.
- Dashboard, Events, Bible verse, and About use compact shared rows and
  content-sized controls. All controls are native Qt and staged state writes
  nothing until Save.
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
  tree with scoped deck exclusions. Independent top-level head limits are
  summed without selected-deck reconciliation, so changing the selected deck
  cannot change the collection-wide result. Total remaining, ETA, and
  completion consume those same values.

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
appearance. Dashboard themes affect only swatches and production rendering.
Settings temporarily replaces the dashboard's slot in Anki's persistent
central layout with a centered 680×620 workspace, then restores the prior
central widgets when it closes. It creates no native Settings window, floating
overlay, manual z-order, screen coordinates, screen-geometry query, or embedded
WebEngine content. On smaller Anki windows it shrinks within 12-pixel margins;
every page remains vertically scrollable.

The dashboard remains inactive while a legacy source add-on is enabled, which
prevents duplicate panels and load-order conflicts. External-calendar source
work remains deferred and is not packaged.

## Install

Install `home-dashboard-overhaul-1.8.7.ankiaddon` through **Tools → Add-ons →
Install from file**, restart Anki, and disable any legacy source add-ons named
by the activation card. The manifest is pinned to Anki Desktop 26.8.

## Build and validation

From the repository root, use Python 3.10 or newer:

```sh
python3 -m unittest home_dashboard_overhaul.tests.test_controller_insights home_dashboard_overhaul.tests.test_settings_release_contract -v
python3 home_dashboard_overhaul/qa/validate_settings_window_contract_1_8_7.py
python3 home_dashboard_overhaul/tools/build_ankiaddon.py
```

The builder creates one 24-file allowlisted archive, checks its version and
safe paths, validates the focused 1.8.7 Settings contract, and verifies every
packaged byte against source. The full 1.8.6 statistics and 94-frame native
evidence remain frozen rather than being regenerated for this candidate.

VoiceOver, Windows, Linux, forced colors, DPR 1, and OS-level display-scaling
acceptance remain deferred and unclaimed unless separately run.

Copyright 2026. Licensed under AGPL-3.0-or-later. See
`THIRD_PARTY_NOTICES.md` for Scripture and upstream notices.
