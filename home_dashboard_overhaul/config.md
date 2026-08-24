# Home Screen Dashboard settings

Open Settings from **Tools → Home Screen Dashboard settings**. The calendar
gear routes to Dashboard and settles on Calendar display after layout.

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

The production dashboard uses a transparent normal-flow root capped at
1,120 px, with a 24 px top margin and at least 20 px on each side. Month is
always a six-week, 42-cell grid. Year always uses one 53-week tree with a 28 px
weekday column and fluid week columns; its gaps and label column compact below
760 px so it remains contained without horizontal scrolling at 480 px and
above. Below 480 px, only the Year heatmap may scroll internally. A measured
visible fixed/sticky Anki bottom-action container supplies root and document
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
last valid ramp saved for that theme.

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

New, Learning, and Reviews remaining come from Anki's limited due tree and are
reconciled with its built reviewer queue. Dashboard deck exclusions remain in
force, and Total is always the exact sum of the three categories. Explicit
queues `-2` and `-3` are authoritative for cards currently buried. Only
queue-hidden New and Review siblings are inferred; a Learning difference can
be future intraday work outside learn-ahead and is not classified as buried.

Last 7 Days spans the seven fixed scheduler periods ending at the next
rollover. All Time spans the complete configured analytics scope. Retention
matches Anki 26.8.1 true-retention eligibility: a rated scheduling-affecting
entry qualifies when it is review-kind or its prior interval is at least one
day. Again fails and Hard, Good, and Easy pass. Retention is rounded half-up to
the existing whole percentage once, and visible Again is `100 − Retention`.

Calendar history and selected-day details use the same rollover-relative
records. Forecasting follows Anki's non-new, non-suspended future-due logic,
uses filtered-deck original due dates, includes future buried cards, and
excludes buried backlog/work due in the active scheduler day.

## Settings and preview

The Settings window is an ordinary, parented, non-modal QDialog at a fixed
1200×800 size. Smaller screens receive a clamped fixed size with a 32 px safety
margin. The opening size is not persisted. On macOS the dialog verifies a
native child relationship to Anki before it opens, keeping both windows in the
same active full-screen Space. It uses one compact header, 152 px rail,
active-page scroller, optional shared right Preview dock, and final-row footer.
A physically smaller screen keeps the same rail and page and places the same
Preview dock in a layout-managed overlay.

Preview is open by default for Dashboard, Events, and Bible verse each session,
is omitted on About, and is never persisted. `Section | Full dashboard` and
`Fit | 100%` use the production renderer. Fit scales a top-aligned wrapper;
100% owns Preview's secondary vertical scrollbar. Settings colors derive only
from Anki's light/dark appearance; dashboard themes affect swatches and preview
content.

Collection-backed preview figures use the most recent saved Home snapshot.
Staged display, event, heatmap, and Bible changes update Preview immediately
but write nothing until Save. Revert restores the complete saved baseline.
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
