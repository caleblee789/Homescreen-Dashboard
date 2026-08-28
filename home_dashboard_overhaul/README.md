# Home Screen Dashboard 1.8.7

Home Screen Dashboard is a calendar-first Deck Browser dashboard for Anki
Desktop 26.8. It combines study history, due work, local events, stable study
metrics, and a rotating Bible verse without patching Anki's private Deck
Browser or statistics classes.

## What changed in 1.8.7

- Settings remains a normal parented `QDialog` with default flags and a local
  `exec()` lifetime. It opens at 1080×760 logical pixels, has an 820×600 normal
  minimum, and uses 48 px normal or 24 px constrained-screen margins.
- The UI-only `settings_dialog_geometry/v4` record preserves logical geometry,
  screen identity, available bounds, and informational DPR. A valid v3 record
  migrates only when it meets the new minimum and remains at least 80% visible;
  disconnected, undersized, maximized, and full-screen records are rejected.
- The Caleb menu constructs and executes the dialog synchronously. Deck Browser
  bridge requests alone remain deferred and coalesced until their callback
  returns. The controller retains one temporary dialog reference during modal
  execution so re-entry focuses/routes the existing instance. Confirmations
  remain scrimmed child layers inside the same window.
- The retired central workspace, backing-view hiding, focus handoff/retries,
  focus restoration, application event filter, and menu-dismissal timer are
  removed. Qt manages the same dialog lifecycle as the two working add-ons.
- The corrected statistics, schema 8, configuration keys, bridge
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

- Settings has one native Qt widget tree at every size: fixed header, a body
  with one vertical scroller per page, and a true final-row footer. The
  shell is capped at 1,120 px, the sidebar is 184 px, the page header is at
  least 72 px, the footer is at least 60 px, and ordinary pages are capped at
  920 px (About at 840 px).
- Compact top navigation activates whenever retaining the sidebar would leave
  less than 680 px for the main region, so the 820 px minimum is compact. Forms and toolbars
  remain horizontally contained without rendered Settings previews.
- Dashboard groups Appearance, Dashboard sections, Study metrics, and Calendar
  display. Events uses a searchable/sortable Active/Archived list bounded to
  six naturally growing rows and a parented editor capped near 440 px. Bible verse uses a flexible
  filtered library with two-line clamped excerpts and one inline hex error.
  About groups Version and support, Privacy and legal, and Backup and recovery.
- Dirty, saving, saved, validation, and persistence feedback is action-local
  in the footer. A failed save retains all staged values, enables retry, and
  keeps technical details behind a disclosure. All controls remain native Qt
  and staged state writes nothing until Save.
- Dashboard theme and Heatmap palette share one responsive Appearance row.
  Their layout-changing staged updates run after the native combo popup closes,
  and save locking restores both selectors and their nested popup views.
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

Open settings from Anki's Tools menu or the calendar gear. Changes are applied
when you save. **Discard changes** returns every staged field to the saved
baseline, while each visible **Reset** affects only its own default scope. The
baseline updates only after a completely successful save.

The Settings chrome derives its colors solely from Anki's light/dark
appearance. Dashboard themes affect only production rendering; Settings shows
text selectors and retains the custom-color input well without preview cards.
Settings is a movable, resizable `QDialog(mw)` with a 1080×760 logical default,
820×600 normal minimum, default Qt flags, and a local `exec()` call. It resolves the
parent window's active screen, falls back to the screen containing the parent
center and then the primary screen, and applies a clamped logical geometry
before first visibility. After showing, it corrects only a decorated frame that
is genuinely outside the available screen. It never calls `winId()`, raises or
activates the window, hides Anki's central widgets, or embeds WebEngine content. Every
page remains vertically scrollable, and navigation only changes child widgets
inside the existing stack.

Responsive field grids mount every new field under its Settings card before
changing visibility or filtering layout rows. This prevents a parentless field
from being realized as a temporary native window during dialog construction.
No Dashboard card, verse card, palette, theme, or heatmap preview widget is
constructed in Settings.

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
python3 -m unittest discover -s home_dashboard_overhaul/tests -v
node home_dashboard_overhaul/tests/calendar_model_test.js
python3 home_dashboard_overhaul/qa/capture_plan.py --json
python3 home_dashboard_overhaul/qa/validate_revised_ui_contract.py
python3 home_dashboard_overhaul/qa/validate_settings_window_contract_1_8_7.py
python3 home_dashboard_overhaul/tools/build_ankiaddon.py
```

The builder creates one 24-file allowlisted archive, checks its version and
safe paths, validates the 1.8.7 release authorities, and verifies every
packaged byte against source. The canonical plan contains 94 native frames,
including exactly 41 Settings frames at 100% application font and two total
controlled-restart states. Settings presentation is capped at 11 sheets.
The focused Settings assembler additionally requires a structured exact-package
native macOS result proving that both the full-screen menu and Dashboard-gear
paths remain on Anki's full-screen Space without switching to the desktop,
while separately completing all pages, Events tabs, resize, event and verse
edits, save, close/reopen, and controlled restart through each route. Every
step records current-Space retention. This required result adds no PNG frames.

VoiceOver and forced-colors remain explicitly unrun and nonblocking. The macOS
full-screen no-switch result is mandatory for Settings acceptance. Windows,
Linux, DPR 1, and native OS display scaling remain separate release-blocking
gates and remain unclaimed until their native reports pass against one exact
package and capture-plan hash.

Copyright 2026. Licensed under AGPL-3.0-or-later. See
`THIRD_PARTY_NOTICES.md` for Scripture and upstream notices.
