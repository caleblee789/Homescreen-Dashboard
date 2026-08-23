# Home Screen Dashboard 1.7.0

Home Screen Dashboard is a calendar-first Deck Browser dashboard for Anki
Desktop 26.8. Its production hierarchy is deliberately fixed:

1. Study Calendar with Month/Year controls, one shared calendar grid, separate
   completion and due legends, and a compact context bar.
2. Today’s Progress, Today’s Session, Last 7 Days, and All Time.
3. A full-width Bible verse.

The calendar context bar explicitly distinguishes the selected date, an event
on that date, and the globally calculated next event. An event on the selected
date opens that exact record for editing. Past/current dates expose Reviewed;
future dates expose Due. Those date-appropriate Browser actions stay visible
but disabled with an explanatory tooltip when no exact card set exists, while
Most missed appears only after an eligible Again answer is confirmed. The
dashboard does not render card previews, a selected-date details panel, a
due-deck list, or a separate events column.

Calendar cells use one visual responsibility per state: completion volume is the
authored heatmap fill, relative due volume is a quiet bottom band, an event is a
diamond, Today is a compact date-number badge, selection is a 2 px border,
keyboard focus is an external ring, and outside-month dates use muted text with
a dashed border. Month and Year share the same day model and full-horizon due
normalization. The due reference is the 90th percentile of positive forecast
counts; square-root scaling maps load to low, medium, and high density/opacity
without letting one outlier flatten the forecast.

The four dashboard themes are Sapphire Glass, Graphite, Emerald, and High
Contrast. Calendar & data provides four independently saved completion ramps
for each theme. Every ramp has authored light/dark empty, five-level, foreground,
and outside-month tokens; the levels are not opacity variants of one accent.

Metric values are locale-formatted, tabular, right-aligned, and omitted when
unsupported. At 1,320 px and wider, Month places a 2×2 metric rail beside the
calendar. Intermediate layouts place the 2×2 grid below the calendar, narrow
layouts use one card per row, and Year remains full width with fixed square
cells and visible month labels. Last 7 Days includes New cards studied
immediately after Cards studied. Today’s Progress uses a count-derived
four-segment workload bar; buried cards remain outside the workload. ETA remains
neutral, while retention uses the configured target to choose its semantic
state.

Open settings from Anki’s Tools menu or the calendar gear. The editor has four
pages: Dashboard, Events, Bible verse, and About & support. Dashboard combines
Appearance, Content & study metrics, and Calendar & data in three scoped areas;
visibility and study calculations are separated inside the middle area. At
1,180 px and wider, Settings shows a vertical rail and contextual Dashboard or
Bible preview; from 760–1,179 px it uses horizontal tabs with the preview behind
Preview; below 760 px it uses a four-item selector. Events
and About & support always use the full editor width. The production renderer
powers the staged preview, with Current section / Full dashboard and Fit /
Actual size controls. The preview is content-sized, Bible uses the selected
staged verse, and only collection-backed Dashboard fallback data receives a
Sample data badge. Events attach Edit, Archive/Restore, and Delete to each row's
overflow menu and use a centered empty state when no events exist.
Staged changes do not affect Home until Save.

Bible color editing uses an explicit Theme color / Custom color choice, a
validated #RRGGBB field, a swatch, and an inline contrast warning. Theme color
hides and removes the custom controls from focus without discarding the stored value. Card-header
resets are staged and offer Undo. The non-overlay footer shows Close or Discard
changes alongside Save changes, while the header announces dirty, saving,
saved, and failure states.

Dashboard loading begins with component-shaped skeletons, announces a delayed
state after 2.5 seconds, and becomes a retryable failure with a diagnostics path
after 12 seconds. Release restart evidence waits for the fully rendered
dashboard and reads saved values back in both Home and Settings.

Configuration schema 6 removes legacy selected-details and dashboard-preview
slots, places summary metrics before the Bible, adds a retention target, and
stores one heatmap preset per theme. Migration is idempotent and preserves
unrelated settings and relative ordering.

Buried counts follow the scheduler-relevant Progressbar method: only queues -2
and -3 are included; suspended cards are excluded; New counts type 0; Learning
counts types 1/3 only when due by the scheduler day or rollover cutoff according
to the due representation; Review counts type 2 only when due by today.

The unified dashboard remains inactive while a legacy source add-on is enabled,
preventing duplicate information and load-order conflicts. External-calendar
source work remains deferred and is not packaged.

Copyright 2026. Licensed under AGPL-3.0-or-later. See
`THIRD_PARTY_NOTICES.md` for Scripture and upstream notices.
