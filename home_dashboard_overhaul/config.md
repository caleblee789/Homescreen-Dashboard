# Home Screen Dashboard settings

Open Settings from **Tools → Home Screen Dashboard settings**. The calendar
gear opens Calendar. Settings is organized into Dashboard, Appearance, Calendar,
Events, Bible verse, and About & support. Bible verse opens to Library; its
Display & rotation tab owns typography, color, and rotation. Changes remain
staged until Save changes.

Schema 8 keeps exactly three layout roles: `study_calendar`,
`summary_metrics`, and `bible_verse`. Legacy selected-date, due-deck, and card
preview roles are removed during normalization and never recreated. Unknown
unrelated keys are retained.

## Appearance and layout

`appearance.preset` accepts `Sapphire Glass`, `Graphite`, `Emerald`, or `High
Contrast`. `appearance.mode` accepts `auto`, `light`, or `dark`.
`appearance.opacity` accepts 94–100 and defaults to 96; `appearance.blur`
accepts 0–16 px and defaults to 12 px. Both controls apply only to Sapphire
Glass and are hidden for other themes while retaining their staged and stored
values. `appearance.text_scale` accepts 90–150.

The production dashboard uses a transparent centered normal-flow root with the
width rule `min(1160px, calc(100% - 32px))` and one 30 px top margin. At a root
width of 1,009 px or more, Calendar sits beside a fixed 360 px insight rail
with a 14 px column gap. At 1,008 px and below the rail stacks; summary metrics
remain two columns through 589 px and become one column at 588 px. Month is
always a six-week, 42-cell grid. Year always uses one 53-week tree with 10 px
square cells at the wide reference and fluid square cells when narrower, with
no minimum-width floor or internal horizontal scrolling. A measured visible
normal, fixed, or sticky Anki bottom-action container supplies root and document
scroll padding equal to its height plus 24 px; 60 px is the height fallback.

## Completion palettes

`heatmap.presets_by_theme` stores an independent completion ramp for every
dashboard theme. The IDs are stable:

- Sapphire Glass: Sapphire, Amethyst, Glacier, Sea Glass
- Graphite: Slate, Steel, Plum, Mint
- Emerald: Emerald, Jade, Moss, Lagoon
- High Contrast: Cyan, Gold, Magenta, Monochrome

Every ID has separately authored light and dark ladders. An unknown or legacy
value resets only that theme to its first preset. Switching themes restores the
last valid ramp saved for that theme. Study semantics share one baseline across
themes except the audited Sapphire Glass dark override, where Learning is red
and Review is green.

## Calendar, study, and events

`heatmap.calendar_view` accepts `month` or `year`; `week_start` accepts 0–6.
History, forecast, manual-reschedule, deleted-card, and deck-exclusion options
form one scope shared by calendar counts and exact Browser targets.
`forecast_days: 0` or `show_due_forecast: false` retains Today's due value but
omits unsupported future due rows and actions.

`events.sort` accepts `ascending`, `descending`, or `name`. The first two keep
their date meanings. `name` sorts case-insensitively by event name, then date,
then stable ID.

`study.retention_target` accepts 50–100 and defaults to 80. It affects only the
semantic presentation of available retention values. ETA remains permanent.
Schema 8 drops retired `study.show_eta`, `study.show_estimate`, and
`visibility.buried` keys while retaining unrelated unknown keys.

The compact calendar footer always belongs to the calendar card. Due and event
legend groups and event summaries are conditional on their feature settings.
Date selection, tooltip, exact Browser routing, event edit/add, and Most Missed
behavior retain their existing semantics.

## Statistics calculations

Today is the exact scheduler period `[next rollover − 86,400 seconds, next
rollover)`. Cards studied counts rated answer events in that period after the
configured analytics scope; Time spent sums their recorded review time; Pace
is seconds per answer. New cards studied counts distinct qualifying
introductions, with `new_cards.include_rescheduled` controlling whether a
reset/reintroduced card may count again.

The scope is collection-wide minus configured excluded decks and every
descendant. Both current deck IDs and filtered-deck original IDs are checked.
Suspending or burying a card removes it from current actionable workload, and
suspension also removes it from future forecasts. Neither state retroactively
erases rated historical answers, matching Anki.

New, Learning, and Reviews remaining come from Anki's limited due tree. Each
included top-level head is capped independently after scoped raw candidates are
classified by scheduler queue: queue `0` is New, queues `1`, `3`, and `4` are
Learning, and queue `2` is Review regardless of card type. Suspended `-1` and
buried `-2`/`-3` queues are excluded. The selected deck is not consulted, and
Total is always the exact sum of the three categories. Cards buried reports
only scoped cards currently in queues `-2` or `-3` that are New or currently
due/overdue. Future Learning and Review cards and transient queue-hidden
siblings are excluded. While work remains, the active progress presentation
places `N% complete` inside the filled bar. Initial cards due is the same
denominator used by that bar: Cards studied today plus Total remaining. The
visible order is Initial cards due, Total remaining, New remaining, Learning
remaining, and Reviews remaining.

Last 7 Days spans the seven fixed scheduler periods ending at the next
rollover, and Time spent sums recorded review time from those same scoped
rows. All Time spans the complete configured analytics scope. Retention
matches Anki 26.8.1 true-retention eligibility: `ease > 0`, excluding
`type = 3 AND factor = 0`, and requiring `type = 1` or a prior interval of at
least one day. Again fails and Hard, Good, and Easy pass. Raw pass and eligible
counts are aggregated before Retention is rounded half-up to the existing whole
percentage once. Again remains an internal retention-parity calculation but is
not displayed. Last 7 Days Avg cards/day divides its answer total by all seven
fixed scheduler periods, including zero-activity days, and rounds half-up to a
whole card. All Time Avg cards/day divides answer events by active scheduler
days, and streaks count consecutive active scheduler days.

Calendar history and selected-day details use the same rollover-relative
records. Forecasting follows Anki's non-new, non-suspended future-due logic,
uses filtered-deck original due dates, includes future buried cards, and
excludes buried backlog/work due in the active scheduler day.

## Settings

Settings is a normal movable `QDialog(mw)` matching Progress Bar and
PronounceIt. It starts at 1080×760 logical pixels, has an 860×640 normal
minimum, remains resizable, uses default window flags, and opens through a
local `exec()` call. The UI-only `settings_dialog_geometry/v4` record preserves
logical geometry, screen identity, available bounds, and informational DPR;
invalid, disconnected, undersized, maximized, or full-screen records are
rejected before the dialog is shown.

The native shell has a fixed header, one active-page scroller, and a final-row
footer with a 56 px minimum. The centered shell is capped at 1,264 px, ordinary
pages at 1,080 px, and the sidebar rail is 184 px. A synchronized compact top
navigation replaces the rail at the supported 860 px minimum. The Dashboard
page keeps Deck exclusions and filters as a visible independently resettable
card, and Events refits its native tab height after styling so empty states do
not clip. Settings never hides Anki's backing views, forces lifecycle focus, or
contains an `AnkiWebView`; the heatmap and Bible appearance previews are native
Qt widgets derived from the staged draft.

Settings colors derive only from Anki's light/dark appearance; dashboard themes
affect production rendering. Staged display, event, heatmap, and Bible changes
update the draft synchronously but write nothing until Save. Navigation changes
only select a native stacked page. Discard changes restores the complete saved
baseline.
Saving validates all staged state, prepares both config and manual-verse
writes, replaces atomically where supported, and rolls back best-effort on a
partial failure before reporting a specific inline error.

When `bible.theme_aware_color` is enabled, stored `bible.font_color` is
preserved while its input and swatch are disabled. Rotation accepts existing
supported values and invalid/missing rotation normalizes to `daily`. Stored
verse content is unchanged; Settings parses it only for reference/excerpt
presentation.

The add-on performs a one-time source migration and remains paused while any
legacy source add-on is enabled. Direct JSON editing remains available for
recovery; values are normalized on load and save.
