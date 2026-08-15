# Home Dashboard - Overhaul

Use **Tools → Caleb M. Add-ons Settings → Home Dashboard - Overhaul settings**.

The visual editor includes all supported settings, section-specific production
renderer previews, Month/Year controls, local event management, and staged Bible
verse management. It follows the staged dashboard preset immediately but writes
nothing until **Save changes**. Dirty-close prompts, safe section resets, and
conflict-aware three-way merges protect saved and unknown future keys. Direct
JSON editing remains available for recovery; invalid values are normalized.

The Calendar page explains date semantics: study counts and due forecasts follow
the configured rollover, while events retain their civil-calendar dates.
This explanation is intentionally kept out of the compact dashboard preview.

Schema 3 stores the last view and week start under `heatmap`, the rescheduled-card
preference under `new_cards`, and the ETA toggle under `study`. The existing
`visibility.remaining` key controls the complete Today’s Progress group; its
internal name is intentionally unchanged for compatibility. `study.show_eta`
controls only the ETA row in Today. No progress-specific key or snapshot field is
required.

The selected-date Study Insight rail reuses the existing Calendar history,
forecast, deleted-card, manual-reschedule, and excluded-deck settings. It does not
add a configuration key: today/past insights come from full scheduling-day
`revlog` data, and future insights come from the configured due forecast.

Schema 2's Introduced visibility, week start, and estimate toggle migrate
automatically; obsolete lookback, multiplier, period, and custom-summary keys are
removed. Legacy `calendar_mode` values are migrated to Year and removed on the
next save. Version 1.5.3 does not bump schema 3.

Today’s Progress is calculated at render time from current scheduling-day answers and
the actionable `queue.new`, `queue.learning`, and `queue.review` counts. Buried
counts are deliberately separate and do not contribute to the bar, percentage,
Total remaining, or ETA.

The unified dashboard remains inactive while any of the five legacy source
add-ons are enabled. This prevents duplicate information and load-order conflicts.
